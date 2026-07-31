# Promotion-boundary hostile tests (v0.4).
#
# Status is derived from the append-only record trail. Root is in-place and
# optional. Forging status requires inserting a record — which IS the ceremony.

import sqlite3

import pytest

from conftest import linked_pair

from forest_memory import CeremonyRefusal, ForestError, ForestStore, root_to_ground


def store(tmp_path):
    s = ForestStore(tmp_path / "forest.db")
    s.init_schema()
    return s


def draft(s, tmp_path, body="Elias betrayed her in winter."):
    pair_id = linked_pair(s, tmp_path, "anchor")
    return s.write(
        body=body,
        bucket="draft",
        signature="model",
        origins=[(pair_id, "spoken_in")],
        scrub=None,
    )


def root(s, draft_id):
    row = s.get(draft_id)
    return root_to_ground(
        s,
        entry_id=draft_id,
        adopting_words="Yes — shelve this as ground.",
        adopting_signature="author",
        expected_body_hash=row["body_hash"],
        source_verbatim=row["body"],
    )


def test_write_has_no_authority_parameter(tmp_path):
    s = store(tmp_path)
    pair_id = linked_pair(s, tmp_path, "anchor")
    with pytest.raises(TypeError):
        s.write(
            body="forged ground",
            bucket="note",
            signature="model",
            authority="ground",
            origins=[(pair_id, "spoken_in")],
        )


def test_write_refuses_ceremony_buckets(tmp_path):
    s = store(tmp_path)
    pair_id = linked_pair(s, tmp_path, "anchor")
    for bucket in ("adoption_record", "sealing_record", "unsealing_record"):
        with pytest.raises(ForestError, match="ceremony"):
            s.write(
                body="forged record",
                bucket=bucket,
                signature="model",
                origins=[(pair_id, "spoken_in")],
            )


def test_write_refuses_ceremony_edge_kinds(tmp_path):
    s = store(tmp_path)
    draft_id = draft(s, tmp_path)
    for kind in ("adopts", "supersedes", "seals", "unseals"):
        with pytest.raises(ForestError, match="ceremony"):
            s.write(
                body="forged trail",
                bucket="note",
                signature="model",
                origins=[(draft_id, kind)],
            )
        with pytest.raises(ForestError, match="ceremony"):
            s.add_edge(draft_id, draft_id, kind)


ENTRY_COLUMNS = [
    ("jurisdiction", "'wild'"),
    ("bucket", "'note'"),
    ("signature", "'author'"),
    ("body", "'changed'"),
    ("body_hash", "lower(hex(randomblob(32)))"),
    ("meta_json", "'{\"forged\":true}'"),
    ("created_at", "'1970-01-01T00:00:00.000Z'"),
]


@pytest.mark.parametrize("column,value", ENTRY_COLUMNS, ids=[c for c, _ in ENTRY_COLUMNS])
def test_update_any_entry_column_refuses(tmp_path, column, value):
    s = store(tmp_path)
    pair_id = linked_pair(s, tmp_path, "anchor")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        s.conn.execute(f"UPDATE entries SET {column} = {value} WHERE id = ?", (pair_id,))


def test_update_edge_refuses(tmp_path):
    s = store(tmp_path)
    draft_id = draft(s, tmp_path)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        s.conn.execute("UPDATE edges SET kind = 'adopts' WHERE from_id = ?", (draft_id,))


def test_status_columns_no_longer_exist(tmp_path):
    s = store(tmp_path)
    columns = {row["name"] for row in s.conn.execute("PRAGMA table_info(entries)")}
    assert not {"authority", "visibility", "superseded_by"} & columns
    assert "jurisdiction" in columns
    assert "forest" not in columns


def test_supersede_refuses_non_ground(tmp_path):
    s = store(tmp_path)
    inference_id = draft(s, tmp_path)
    with pytest.raises(ForestError, match="ground"):
        s.supersede(
            old_id=inference_id,
            new_body="laundered into ground",
            adopting_words="supersede it",
            adopting_signature="author",
        )


def test_supersede_is_itself_a_ceremony(tmp_path):
    s = store(tmp_path)
    ground_id = root(s, draft(s, tmp_path))
    new_id = s.supersede(
        old_id=ground_id,
        new_body="Elias betrayed her in spring.",
        adopting_words="Correction: it was spring. Supersede.",
        adopting_signature="author",
    )
    current = [(r["id"], r["body"]) for r in s.conn.execute("SELECT id, body FROM current_ground")]
    assert current == [(new_id, "Elias betrayed her in spring.")]
    n = s.conn.execute(
        """
        SELECT COUNT(*) AS n FROM edges e
        JOIN entries r ON r.id = e.from_id
        WHERE e.to_id = ? AND e.kind = 'adopts' AND r.bucket = 'adoption_record'
        """,
        (new_id,),
    ).fetchone()["n"]
    assert n == 1


def test_root_requires_speaker_signature(tmp_path):
    s = store(tmp_path)
    draft_id = draft(s, tmp_path)
    row = s.get(draft_id)
    with pytest.raises((CeremonyRefusal, TypeError)):
        root_to_ground(
            s,
            entry_id=draft_id,
            adopting_words="Yes.",
            adopting_signature="",
            expected_body_hash=row["body_hash"],
        )


def test_root_records_speaker_verbatim(tmp_path):
    s = store(tmp_path)
    draft_id = draft(s, tmp_path)
    row = s.get(draft_id)
    root_to_ground(
        s,
        entry_id=draft_id,
        adopting_words="Yes.",
        adopting_signature="author",
        expected_body_hash=row["body_hash"],
    )
    record = s.conn.execute(
        "SELECT body, signature FROM entries WHERE bucket = 'adoption_record'"
    ).fetchone()
    assert record["body"] == "Yes."
    assert record["signature"] == "author"


def test_non_english_root_accepted(tmp_path):
    s = store(tmp_path)
    draft_id = draft(s, tmp_path, body="Elias la traicionó en invierno.")
    row = s.get(draft_id)
    root_to_ground(
        s,
        entry_id=draft_id,
        adopting_words="Sí, esto es verdad ahora.",
        adopting_signature="author",
        expected_body_hash=row["body_hash"],
    )
    ground = [r["body"] for r in s.conn.execute("SELECT body FROM current_ground")]
    assert ground == ["Elias la traicionó en invierno."]


@pytest.mark.parametrize("bad_hash", ["deadbeef", "", "x" * 64, "A" * 64])
def test_malformed_body_hash_refused_by_schema(tmp_path, bad_hash):
    s = store(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        s.conn.execute(
            """
            INSERT INTO entries
              (jurisdiction, bucket, signature, body, body_hash, meta_json)
            VALUES ('home', 'note', 'model', 'x', ?, '{}')
            """,
            (bad_hash,),
        )


def test_sealed_body_absent_from_raw_fts(tmp_path):
    s = store(tmp_path)
    note_id = draft(s, tmp_path, body="The sealed secret about Elias.")
    assert s.recall_similar("secret", scope="both")
    s.seal(entry_id=note_id, quote="Seal it.")
    hits = list(s.conn.execute("SELECT rowid FROM entries_fts WHERE entries_fts MATCH 'secret'"))
    assert hits == []
    assert s.recall_similar("secret", scope="both") == []


def test_unseal_is_a_recorded_ceremony(tmp_path):
    s = store(tmp_path)
    note_id = draft(s, tmp_path, body="The sealed secret about Elias.")
    s.seal(entry_id=note_id, quote="Seal it.")
    s.unseal(entry_id=note_id, quote="Unseal it — I need it back.")
    assert [r["id"] for r in s.recall_similar("secret", scope="both")] == [note_id]
    n = s.conn.execute(
        "SELECT COUNT(*) AS n FROM entries WHERE bucket = 'unsealing_record'"
    ).fetchone()["n"]
    assert n == 1


def test_double_seal_and_stray_unseal_refused(tmp_path):
    s = store(tmp_path)
    note_id = draft(s, tmp_path)
    with pytest.raises(ForestError, match="not sealed"):
        s.unseal(entry_id=note_id, quote="unseal nothing")
    s.seal(entry_id=note_id, quote="Seal it.")
    with pytest.raises(ForestError, match="already sealed"):
        s.seal(entry_id=note_id, quote="Seal it again.")


def test_seal_state_guard_holds_at_sql_level(tmp_path):
    s = store(tmp_path)
    note_id = draft(s, tmp_path)
    record_id = s.seal(entry_id=note_id, quote="Seal it.")
    with pytest.raises(sqlite3.IntegrityError, match="already sealed"):
        s.conn.execute(
            "INSERT INTO edges (from_id, to_id, kind) VALUES (?, ?, 'seals')",
            (record_id, note_id),
        )


def test_retrieval_log_records_result_ids(tmp_path):
    s = store(tmp_path)
    pair_id = linked_pair(s, tmp_path, "Her brother's name is Elias.")
    s.recall_similar("Elias")
    row = s.conn.execute(
        "SELECT query, result_ids_json FROM retrieval_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["query"] == "Elias"
    assert str(pair_id) in row["result_ids_json"]
