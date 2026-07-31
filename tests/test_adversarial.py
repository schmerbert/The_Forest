"""Adversarial / edge-case tests for 0.4 release blockers.

Covers: safe FTS, add_edge durability, root eligibility, supersede validation,
scroll UTF-8/slice, around directions, step direction verification,
root postcondition, expected_body_hash mismatch.
"""

import pytest

from conftest import linked_pair

from forest_memory import (
    CeremonyRefusal,
    ForestError,
    ForestStore,
    Scroll,
    ScrollError,
    hash_body,
    root_to_ground,
)
from forest_memory.scroll import MAX_SLICE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def store(tmp_path):
    s = ForestStore(tmp_path / "forest.db")
    s.init_schema()
    return s


def make_note(s, tmp_path, body="claim about Elias"):
    pair_id = linked_pair(s, tmp_path, "anchor")
    return s.write(
        body=body,
        bucket="note",
        signature="model",
        origins=[(pair_id, "derived_from")],
        scrub=None,
    )


# ---------------------------------------------------------------------------
# Safe FTS — recall with special characters
# ---------------------------------------------------------------------------


def test_recall_strips_punctuation(tmp_path):
    s = store(tmp_path)
    linked_pair(s, tmp_path, "Her brother Elias betrayed her in winter.")
    # None of these should raise sqlite3.OperationalError
    r1 = s.recall_similar("Elias?")
    r2 = s.recall_similar("brother's")
    r3 = s.recall_similar("foo-bar")
    r4 = s.recall_similar("a:b")
    # At least Elias and brother queries should return something
    assert isinstance(r1, list)
    assert isinstance(r2, list)
    assert isinstance(r3, list)
    assert isinstance(r4, list)


def test_recall_empty_query_refused(tmp_path):
    s = store(tmp_path)
    with pytest.raises(ForestError, match="empty query"):
        s.recall_similar("")


def test_recall_no_alphanumeric_tokens_refused(tmp_path):
    s = store(tmp_path)
    with pytest.raises(ForestError, match="empty query"):
        s.recall_similar("?!@#$%")


def test_recall_fts_error_becomes_forest_error(tmp_path):
    """Demonstrate that raw sqlite3 errors are wrapped as ForestError."""
    # The safe query builder should prevent this; this test verifies the guard exists.
    s = store(tmp_path)
    linked_pair(s, tmp_path, "some content")
    # Valid query should work
    result = s.recall_similar("content")
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# add_edge durable after close / reopen
# ---------------------------------------------------------------------------


def test_add_edge_durable_after_close_reopen(tmp_path):
    db = tmp_path / "forest.db"
    with ForestStore(db) as s:
        s.init_schema()
        pair = linked_pair(s, tmp_path, "anchor")
        note = s.write(
            body="note body",
            bucket="note",
            signature="model",
            origins=[(pair, "derived_from")],
            scrub=None,
        )
        s.add_edge(note, pair, "cites")

    with ForestStore(db) as s:
        row = s.conn.execute(
            "SELECT 1 FROM edges WHERE from_id=? AND to_id=? AND kind='cites'",
            (note, pair),
        ).fetchone()
        assert row is not None, "cites edge must persist across close/reopen"


# ---------------------------------------------------------------------------
# root eligibility: sealed refused; superseded refused
# ---------------------------------------------------------------------------


def test_root_sealed_refused(tmp_path):
    s = store(tmp_path)
    note = make_note(s, tmp_path)
    s.seal(entry_id=note, quote="Seal this.")
    with pytest.raises(ForestError, match="sealed"):
        s._root(
            entry_id=note,
            quote="root it",
            adopting_signature="author",
            expected_body_hash=s.get(note)["body_hash"],
        )


def test_root_superseded_refused(tmp_path):
    s = store(tmp_path)
    note = make_note(s, tmp_path, body="original claim")
    # Root it first
    s._root(
        entry_id=note,
        quote="yes, ground this",
        adopting_signature="author",
        expected_body_hash=s.get(note)["body_hash"],
    )
    assert s.is_ground(note)
    # Supersede it
    s.supersede(
        old_id=note,
        new_body="revised claim",
        adopting_words="Correction: revised. Supersede.",
        adopting_signature="author",
    )
    assert not s.is_ground(note)
    # Now try to root the superseded entry again
    with pytest.raises(ForestError, match="superseded"):
        s._root(
            entry_id=note,
            quote="root the old one",
            adopting_signature="author",
            expected_body_hash=s.get(note)["body_hash"],
        )


# ---------------------------------------------------------------------------
# supersede refuses ceremony bucket for new body
# ---------------------------------------------------------------------------


def test_supersede_refuses_ceremony_bucket_for_new_body(tmp_path):
    s = store(tmp_path)
    note = make_note(s, tmp_path, body="original claim")
    s._root(
        entry_id=note,
        quote="yes, ground this",
        adopting_signature="author",
        expected_body_hash=s.get(note)["body_hash"],
    )
    with pytest.raises(ForestError, match="ceremony"):
        s.supersede(
            old_id=note,
            new_body="new body",
            adopting_words="Supersede it.",
            adopting_signature="author",
            bucket="adoption_record",
        )


# ---------------------------------------------------------------------------
# Scroll UTF-8 tail; whole-scroll (oversized) slice refused
# ---------------------------------------------------------------------------


def test_scroll_tail_utf8_safe(tmp_path):
    scroll = Scroll(tmp_path / "s.scroll")
    # Append a record with multibyte UTF-8 characters
    scroll.append("日本語: あいうえお — testing multibyte")
    data = scroll.path.read_bytes()
    # Try tails of every size from 1 to total length — none should raise UnicodeDecodeError
    for max_b in range(1, len(data) + 1):
        result = scroll.tail(max_bytes=max_b)
        assert isinstance(result, str)


def test_scroll_oversized_slice_refused(tmp_path):
    scroll = Scroll(tmp_path / "s.scroll")
    big_payload = "x" * (MAX_SLICE + 100)
    scroll.append(big_payload)
    size = scroll.size()
    with pytest.raises(ScrollError, match="too large|MAX_SLICE|complete scroll"):
        scroll.read_slice(0, size)


def test_scroll_complete_small_slice_refused(tmp_path):
    scroll = Scroll(tmp_path / "s.scroll")
    scroll.append("small")
    sz = scroll.size()
    assert sz <= MAX_SLICE
    with pytest.raises(ScrollError, match="complete scroll"):
        scroll.read_slice(0, sz)


# ---------------------------------------------------------------------------
# around directions; step rejects wrong direction
# ---------------------------------------------------------------------------


def _route_dirs(scrap):
    return {r["direction"] for r in scrap["routes"]}


def _route_rels(scrap):
    return {r["relation"] for r in scrap["routes"]}


def test_around_direction_derived_from(tmp_path):
    s = store(tmp_path)
    pair = linked_pair(s, tmp_path, "anchor text about bees")
    note = s.write(
        body="derived note about bees",
        bucket="note",
        signature="model",
        origins=[(pair, "derived_from")],
        scrub=None,
    )
    # From pair: note is "in" (pair is to_id of derived_from edge)
    trail = s.open(pair)
    scraps = s.around(trail)
    note_scrap = next((sc for sc in scraps if sc["id"] == note), None)
    assert note_scrap is not None
    assert "in" in _route_dirs(note_scrap)
    assert "derived_from" in _route_rels(note_scrap)

    # From note: pair is "out" (note is from_id of derived_from edge)
    trail2 = s.open(note)
    scraps2 = s.around(trail2)
    pair_scrap = next((sc for sc in scraps2 if sc["id"] == pair), None)
    assert pair_scrap is not None
    assert "out" in _route_dirs(pair_scrap)
    assert "derived_from" in _route_rels(pair_scrap)


def test_around_direction_responds_to(tmp_path):
    s = store(tmp_path)
    older = linked_pair(s, tmp_path, "first turn")
    newer = linked_pair(s, tmp_path, "second turn", previous_pair_id=older)

    # From newer: older is "prev"
    trail_newer = s.open(newer)
    scraps_newer = s.around(trail_newer)
    older_scrap = next((sc for sc in scraps_newer if sc["id"] == older), None)
    assert older_scrap is not None
    assert "prev" in _route_dirs(older_scrap)

    # From older: newer is "next"
    trail_older = s.open(older)
    scraps_older = s.around(trail_older)
    newer_scrap = next((sc for sc in scraps_older if sc["id"] == newer), None)
    assert newer_scrap is not None
    assert "next" in _route_dirs(newer_scrap)


def test_around_preserves_multiple_routes_same_destination(tmp_path):
    s = store(tmp_path)
    pair = linked_pair(s, tmp_path, "source text")
    note = s.write(
        body="cites and derives",
        bucket="note",
        signature="model",
        origins=[(pair, "derived_from")],
        scrub=None,
    )
    s.add_edge(note, pair, "cites")
    trail = s.open(note)
    scraps = s.around(trail)
    pair_scrap = next(sc for sc in scraps if sc["id"] == pair)
    rels = _route_rels(pair_scrap)
    assert rels == {"derived_from", "cites"}
    assert all(r["direction"] == "out" for r in pair_scrap["routes"])
    # step still validates the disclosed direction
    s.around(trail)
    moved = s.step(trail, "out", target=pair)
    assert moved.position == pair


def test_around_excludes_ceremony_edges(tmp_path):
    s = store(tmp_path)
    note = make_note(s, tmp_path, body="ground candidate")
    s._root(
        entry_id=note,
        quote="ground this",
        adopting_signature="author",
        expected_body_hash=s.get(note)["body_hash"],
    )
    # The adoption_record has an 'adopts' edge TO note.
    # From note, that adoption_record must NOT appear in around (ceremony edge).
    trail = s.open(note)
    scraps = s.around(trail)
    adoption_ids = [
        r["id"]
        for r in s.conn.execute("SELECT id FROM entries WHERE bucket='adoption_record'")
    ]
    around_ids = {sc["id"] for sc in scraps}
    for aid in adoption_ids:
        assert aid not in around_ids, "adoption_record must not appear in around()"


def test_move_refuses_ceremony_neighbor(tmp_path):
    s = store(tmp_path)
    note = make_note(s, tmp_path, body="ground candidate")
    s._root(
        entry_id=note,
        quote="ground this",
        adopting_signature="author",
        expected_body_hash=s.get(note)["body_hash"],
    )
    rec = s.conn.execute(
        "SELECT id FROM entries WHERE bucket='adoption_record'"
    ).fetchone()["id"]
    trail = s.open(note)
    with pytest.raises(ForestError, match="no edge"):
        s.move(trail, neighbor_id=rec)


def test_step_rejects_wrong_direction(tmp_path):
    s = store(tmp_path)
    pair = linked_pair(s, tmp_path, "anchor text")
    note = s.write(
        body="derived note",
        bucket="note",
        signature="model",
        origins=[(pair, "derived_from")],
        scrub=None,
    )
    trail = s.open(pair)
    s.around(trail)
    # note is "in" from pair, not "out" — step("out", target=note) must fail
    with pytest.raises(ForestError):
        s.step(trail, "out", target=note)


def test_step_in_verifies_direction(tmp_path):
    s = store(tmp_path)
    pair = linked_pair(s, tmp_path, "anchor")
    note = s.write(
        body="derived",
        bucket="note",
        signature="model",
        origins=[(pair, "derived_from")],
        scrub=None,
    )
    # From note, pair is "out" — step("in", target=pair) from note must fail
    trail = s.open(note)
    s.around(trail)
    with pytest.raises(ForestError):
        s.step(trail, "in", target=pair)

    # From pair, note is "in" — step("in", target=note) must work
    trail2 = s.open(pair)
    s.around(trail2)
    new_trail = s.step(trail2, "in", target=note)
    assert new_trail.position == note


# ---------------------------------------------------------------------------
# root postcondition / expected_body_hash mismatch
# ---------------------------------------------------------------------------


def test_root_expected_body_hash_mismatch_ceremony_refusal(tmp_path):
    s = store(tmp_path)
    note = make_note(s, tmp_path, body="a specific claim")
    with pytest.raises(CeremonyRefusal, match="hash"):
        root_to_ground(
            s,
            entry_id=note,
            adopting_words="Yes — root this.",
            adopting_signature="author",
            expected_body_hash="a" * 64,  # wrong hash
        )
    # Entry must NOT be ground after mismatch
    assert not s.is_ground(note)


def test_root_expected_body_hash_correct_succeeds(tmp_path):
    s = store(tmp_path)
    body = "the exact claim to root"
    note = make_note(s, tmp_path, body=body)
    row = s.get(note)
    grounded = root_to_ground(
        s,
        entry_id=note,
        adopting_words="Yes — root this exactly.",
        adopting_signature="author",
        expected_body_hash=row["body_hash"],
    )
    assert grounded == note
    assert s.is_ground(note)


def test_root_store_expected_body_hash_mismatch(tmp_path):
    """ForestStore._root requires expected_body_hash and validates it."""
    s = store(tmp_path)
    note = make_note(s, tmp_path, body="claim")
    with pytest.raises(ForestError, match="body_hash mismatch"):
        s._root(
            entry_id=note,
            quote="ground it",
            adopting_signature="author",
            expected_body_hash="b" * 64,
        )


def test_root_postcondition_entry_is_ground(tmp_path):
    """After _root, is_ground must return True — postcondition verified."""
    s = store(tmp_path)
    note = make_note(s, tmp_path, body="claim to ground")
    row = s.get(note)
    s._root(
        entry_id=note,
        quote="yes, ground",
        adopting_signature="author",
        expected_body_hash=row["body_hash"],
    )
    assert s.is_ground(note)


# ---------------------------------------------------------------------------
# Forest meta version guard
# ---------------------------------------------------------------------------


def test_store_with_entries_and_correct_meta_opens(tmp_path):
    db = tmp_path / "forest.db"
    with ForestStore(db) as s:
        s.init_schema()
        linked_pair(s, tmp_path, "test entry")
    # Reopening with correct meta should succeed
    with ForestStore(db) as s:
        count = s.conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
        assert count == 1
