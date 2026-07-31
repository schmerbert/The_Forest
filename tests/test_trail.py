"""Trail open/around/step/read: tickets required; receipts are not written."""

import pytest

from forest_memory import ForestError, ForestStore, Trail, commit_turn, root_to_ground
from forest_memory.scroll import Scroll

from conftest import linked_pair


def store(tmp_path):
    s = ForestStore(tmp_path / "forest.db")
    s.init_schema()
    return s


def test_open_does_not_write_entries(tmp_path):
    s = store(tmp_path)
    p = linked_pair(s, tmp_path, "long body about bees and honey and summer")
    before = s.conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
    trail = s.open(p)
    assert trail.position == p
    assert trail.ticket
    after = s.conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
    assert after == before


def test_forged_ticket_read_refused(tmp_path):
    s = store(tmp_path)
    p = linked_pair(s, tmp_path, "secret body")
    with pytest.raises(ForestError, match="forged|unknown"):
        s.read(Trail(position=p, ticket="not-a-real-ticket"))


def test_raw_position_without_ticket_refused(tmp_path):
    s = store(tmp_path)
    p = linked_pair(s, tmp_path, "secret body")
    with pytest.raises(ForestError, match="forged|unknown"):
        s.read(Trail(position=p, ticket=""))


def test_step_without_around_refused(tmp_path):
    s = store(tmp_path)
    p = linked_pair(s, tmp_path, "anchor")
    note = s.write(
        body="neighbor",
        bucket="note",
        signature="model",
        origins=[(p, "derived_from")],
        scrub=None,
    )
    trail = s.open(p)
    with pytest.raises(ForestError, match="disclosed|around"):
        s.step(trail, "in", target=note)


def test_spent_ticket_refused(tmp_path):
    s = store(tmp_path)
    p = linked_pair(s, tmp_path, "anchor")
    note = s.write(
        body="neighbor",
        bucket="note",
        signature="model",
        origins=[(p, "derived_from")],
        scrub=None,
    )
    trail = s.open(p)
    s.around(trail)
    new = s.step(trail, "in", target=note)
    with pytest.raises(ForestError, match="spent"):
        s.read(trail)
    assert s.read(new)["body"] == "neighbor"


def test_neighbor_move_does_not_write(tmp_path):
    s = store(tmp_path)
    p = linked_pair(s, tmp_path, "anchor")
    note = s.write(
        body="neighbor note",
        bucket="note",
        signature="model",
        origins=[(p, "derived_from")],
        scrub=None,
    )
    before = s.conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
    trail = s.open(p)
    moved = s.move(trail, neighbor_id=note)
    assert moved.position == note
    assert moved.ticket != trail.ticket
    after = s.conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
    assert after == before


def test_deeper_creates_verbatim_nest(tmp_path):
    s = store(tmp_path)
    p = linked_pair(
        s, tmp_path, "The grandmother kept bees until she was ninety.", scrub=None
    )
    stored = s.get(p)["body"]
    start = stored.index("grandmother")
    end = start + len("grandmother kept bees")
    trail = s.open(p)
    deeper = s.move(trail, deeper=(start, end))
    child = s.get(deeper.position)
    assert child["body"] == stored[start:end]
    up = s.move(deeper, shallower=True)
    assert up.position == p


def test_move_refuses_non_neighbor(tmp_path):
    s = store(tmp_path)
    a = linked_pair(s, tmp_path, "a")
    b = linked_pair(s, tmp_path, "b")
    trail = s.open(a)
    with pytest.raises(ForestError, match="no edge"):
        s.move(trail, neighbor_id=b)


def test_write_pair_without_scroll_ptr_refused(tmp_path):
    s = store(tmp_path)
    with pytest.raises(ForestError, match="scroll_ptr"):
        s.write_pair("orphan pair", scroll_ptr=None)


def test_walk_back_from_ground(tmp_path):
    s = store(tmp_path)
    scroll = Scroll(tmp_path / "session.scroll")
    p = commit_turn(s, scroll, "I will attend the river festival.")
    note = s.write(
        body="User confirmed attendance at river festival.",
        bucket="note",
        signature="model",
        origins=[(p, "derived_from")],
        scrub=None,
    )
    row = s.get(note)
    root_to_ground(
        s,
        entry_id=note,
        adopting_words="Root: I am going to that one.",
        adopting_signature="author",
        expected_body_hash=row["body_hash"],
    )
    path = s.walk_back(note, adopting_signature="author")
    assert path["is_ground"] is True
    assert path["adoption"] is not None
    assert "excerpt" in path["entry"] and "body" not in path["entry"]
    assert path["origins"]
    # note itself has no scroll_ptr; pair does — origins may include pair
    pair_meta = s.get(p)["meta_json"]
    assert "scroll_ptr" in pair_meta


def test_walk_back_refuses_non_ground(tmp_path):
    s = store(tmp_path)
    p = linked_pair(s, tmp_path, "not grounded")
    with pytest.raises(ForestError, match="not current ground"):
        s.walk_back(p, adopting_signature="author")


def test_walk_back_requires_signature(tmp_path):
    s = store(tmp_path)
    p = linked_pair(s, tmp_path, "x")
    note = s.write(
        body="g",
        bucket="note",
        signature="model",
        origins=[(p, "derived_from")],
        scrub=None,
    )
    root_to_ground(
        s,
        entry_id=note,
        adopting_words="Root this fact.",
        adopting_signature="author",
        expected_body_hash=s.get(note)["body_hash"],
    )
    with pytest.raises(ForestError, match="adopting_signature"):
        s.walk_back(note, adopting_signature="")


def test_wild_read_cites_on_next_pair(tmp_path):
    s = store(tmp_path)
    p = linked_pair(s, tmp_path, "ask about the archive")
    wild = s.write(
        body="Treaty signed in 1842.",
        jurisdiction="wild",
        bucket="internet",
        signature="tool",
        origins=[(p, "cites")],
        scrub=None,
    )
    trail = s.open(wild)
    s.read(trail)
    next_p = linked_pair(s, tmp_path, "thanks for the year")
    edge = s.conn.execute(
        "SELECT 1 FROM edges WHERE from_id=? AND to_id=? AND kind='cites'",
        (next_p, wild),
    ).fetchone()
    assert edge is not None


def test_around_previews_not_bodies(tmp_path):
    s = store(tmp_path)
    p = linked_pair(s, tmp_path, "anchor bees")
    note = s.write(
        body="neighbor note about bees",
        bucket="note",
        signature="model",
        origins=[(p, "derived_from")],
        scrub=None,
    )
    trail = s.open(p)
    before = s.conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
    scraps = s.around(trail)
    after = s.conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
    assert after == before
    assert scraps
    assert note in [sc["id"] for sc in scraps]
    assert all("excerpt" in sc and "body" not in sc for sc in scraps)
    assert all(list(sc.keys())[0] == "jurisdiction" for sc in scraps)
    assert all("routes" in sc and sc["routes"] for sc in scraps)
    note_scrap = next(sc for sc in scraps if sc["id"] == note)
    assert any(
        r["direction"] == "in" and r["relation"] == "derived_from"
        for r in note_scrap["routes"]
    )


def test_step_in_and_read(tmp_path):
    s = store(tmp_path)
    p = linked_pair(s, tmp_path, "anchor")
    note = s.write(
        body="full neighbor body text",
        bucket="note",
        signature="model",
        origins=[(p, "derived_from")],
        scrub=None,
    )
    before = s.conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
    trail = s.open(p)
    s.around(trail)
    trail = s.step(trail, "in", target=note)
    assert trail.position == note
    got = s.read(trail)
    assert got["body"] == "full neighbor body text"
    assert got["jurisdiction"] == "home"
    after = s.conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
    assert after == before


def test_step_next_prev_pair_time(tmp_path):
    s = store(tmp_path)
    older = linked_pair(s, tmp_path, "first turn")
    newer = linked_pair(s, tmp_path, "second turn", previous_pair_id=older)
    trail = s.open(newer)
    s.around(trail)
    trail = s.step(trail, "prev")
    assert trail.position == older
    s.around(trail)
    trail = s.step(trail, "next")
    assert trail.position == newer


def test_step_in_requires_target(tmp_path):
    s = store(tmp_path)
    p = linked_pair(s, tmp_path, "alone")
    trail = s.open(p)
    with pytest.raises(ForestError, match="requires target"):
        s.step(trail, "in")


def test_open_then_read_current_bearing(tmp_path):
    """After open, read of that position is earned without step."""
    s = store(tmp_path)
    p = linked_pair(s, tmp_path, "bearing text")
    trail = s.open(p)
    assert s.read(trail)["body"].startswith("USER:")


def test_authority_report_previews_non_ground(tmp_path):
    s = store(tmp_path)
    p = linked_pair(s, tmp_path, "ask")
    note = s.write(
        body="A long claim that must not appear as body in the report " * 3,
        bucket="note",
        signature="model",
        origins=[(p, "derived_from")],
        scrub=None,
    )
    report = s.authority_report(note, adopting_signature="author")
    assert report["status"]["is_ground"] is False
    assert report["body_hash"] == s.get(note)["body_hash"]
    assert "body" not in report["entry"]
    assert "excerpt" in report["entry"]
    assert "body" not in (report.get("adoption") or {})


def test_authority_report_requires_signature(tmp_path):
    s = store(tmp_path)
    p = linked_pair(s, tmp_path, "x")
    with pytest.raises(ForestError, match="adopting_signature"):
        s.authority_report(p, adopting_signature="")


def test_example_scrubs_strip_scaffolding_not_claim():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "examples" / "scrubs.py"
    spec = importlib.util.spec_from_file_location("forest_example_scrubs", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    claim = "The treaty was signed in 1842."
    assert mod.cot_marker_scrub(f"<think>secret</think>{claim}") == claim
    messy = f"TOOL_RESULT: {{\"ok\": true}}\n{claim}\n"
    out = mod.tool_trace_scrub(messy)
    assert claim in out
    assert "TOOL_RESULT" not in out
