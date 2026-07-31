import sqlite3

import pytest

from conftest import linked_pair

from forest_memory import ForestError, ForestStore, root_to_ground


def store(tmp_path):
    s = ForestStore(tmp_path / "forest.db")
    s.init_schema()
    return s


def test_unsigned_insert_refuses(tmp_path):
    s = store(tmp_path)
    with pytest.raises(ForestError):
        s.write(
            body="hello",
            bucket="note",
            signature="",
            origins=[(1, "derived_from")],
        )


def test_orphan_non_root_insert_refuses(tmp_path):
    s = store(tmp_path)
    with pytest.raises(ForestError):
        s.write(body="orphan", bucket="note", signature="model")


def test_pair_can_be_root(tmp_path):
    s = store(tmp_path)
    pair_id = linked_pair(s, tmp_path, "Her brother's name is Elias.")
    assert pair_id > 0


def test_invalid_bucket_refused_by_schema(tmp_path):
    s = store(tmp_path)
    linked_pair(s, tmp_path, "anchor")
    with pytest.raises(sqlite3.IntegrityError):
        s.conn.execute(
            """
            INSERT INTO entries
              (jurisdiction, bucket, signature, body, body_hash, meta_json)
            VALUES ('home', 'typo_bucket', 'model', 'x', ?, '{}')
            """,
            ("a" * 64,),
        )


def test_body_rewrite_refuses(tmp_path):
    s = store(tmp_path)
    pair_id = linked_pair(s, tmp_path, "Her brother's name is Elias.")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        s.conn.execute("UPDATE entries SET body = 'changed' WHERE id = ?", (pair_id,))


def test_entry_delete_refuses(tmp_path):
    s = store(tmp_path)
    pair_id = linked_pair(s, tmp_path, "Her brother's name is Elias.")
    with pytest.raises(sqlite3.IntegrityError, match="delete refused"):
        s.conn.execute("DELETE FROM entries WHERE id = ?", (pair_id,))


def test_edge_delete_refuses(tmp_path):
    s = store(tmp_path)
    pair_id = linked_pair(s, tmp_path, "anchor")
    note_id = s.write(
        body="note",
        bucket="note",
        signature="model",
        origins=[(pair_id, "derived_from")],
    )
    edge_id = s.conn.execute(
        "SELECT id FROM edges WHERE from_id = ? AND to_id = ?",
        (note_id, pair_id),
    ).fetchone()["id"]
    with pytest.raises(sqlite3.IntegrityError, match="delete refused"):
        s.conn.execute("DELETE FROM edges WHERE id = ?", (edge_id,))


def test_sealed_entry_does_not_retrieve(tmp_path):
    s = store(tmp_path)
    pair_id = linked_pair(s, tmp_path, "Her brother's name is Elias.")
    note_id = s.write(
        body="Elias betrayed her in winter.",
        bucket="inference",
        signature="model",
        origins=[(pair_id, "derived_from")],
    )
    assert s.recall_similar("Elias", scope="both")
    s.seal(entry_id=note_id, quote="Seal the betrayal note.")
    bodies = [row.get("excerpt") or row.get("body") for row in s.recall_similar("betrayed", scope="both")]
    assert bodies == []


def test_superseded_ground_not_current(tmp_path):
    s = store(tmp_path)
    pair_id = linked_pair(s, tmp_path, "Her brother's name is Elias.")
    draft_id = s.write(
        body="Elias betrayed her in spring.",
        bucket="draft",
        signature="model",
        origins=[(pair_id, "spoken_in")],
        scrub=None,
    )
    old_id = root_to_ground(
        s,
        entry_id=draft_id,
        adopting_words="Yes — shelve this as ground.",
        adopting_signature="author",
        expected_body_hash=s.get(draft_id)["body_hash"],
    )
    new_id = s.supersede(
        old_id=old_id,
        new_body="Elias betrayed her in winter.",
        adopting_words="Correction: winter, not spring. Supersede.",
        adopting_signature="author",
    )
    current = list(s.conn.execute("SELECT id, body FROM current_ground"))
    assert [(row["id"], row["body"]) for row in current] == [
        (new_id, "Elias betrayed her in winter."),
    ]


def test_recall_writes_retrieval_log(tmp_path):
    s = store(tmp_path)
    linked_pair(s, tmp_path, "Her brother's name is Elias.")
    before = s.conn.execute("SELECT COUNT(*) AS n FROM retrieval_log").fetchone()["n"]
    s.recall_similar("brother")
    after = s.conn.execute("SELECT COUNT(*) AS n FROM retrieval_log").fetchone()["n"]
    assert after == before + 1
    row = s.conn.execute(
        "SELECT query, open_buckets_json FROM retrieval_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row["query"] == "brother"


def test_packaged_schema_matches_repo_root():
    from forest_memory.schema import dev_schema_path, load_schema_sql

    assert load_schema_sql() == dev_schema_path().read_text(encoding="utf-8")


def test_store_context_manager_closes_connection(tmp_path):
    db_path = tmp_path / "forest.db"
    with ForestStore(db_path) as s:
        s.init_schema()
        linked_pair(s, tmp_path, "context manager closes cleanly")
    with ForestStore(db_path) as s:
        count = s.conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
        assert count == 1
