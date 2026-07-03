import sqlite3

import pytest

from forest_memory import ForestError, ForestStore


def store(tmp_path):
    s = ForestStore(tmp_path / "forest.db")
    s.init_schema()
    return s


def test_unsigned_insert_refuses(tmp_path):
    s = store(tmp_path)
    with pytest.raises(ForestError):
        s.insert_entry(
            body="hello",
            bucket="note",
            signature="",
            authority="model",
            origins=[(1, "derived_from")],
        )


def test_orphan_non_root_insert_refuses(tmp_path):
    s = store(tmp_path)
    with pytest.raises(ForestError):
        s.insert_entry(body="orphan", bucket="note", signature="model", authority="model")


def test_session_pair_can_be_root(tmp_path):
    s = store(tmp_path)
    pair_id = s.insert_pair("Her brother's name is Elias.")
    assert pair_id > 0


def test_invalid_bucket_refused_by_schema(tmp_path):
    s = store(tmp_path)
    pair_id = s.insert_pair("anchor")
    with pytest.raises(sqlite3.IntegrityError):
        s.conn.execute(
            """
            INSERT INTO entries
              (forest, bucket, signature, authority, visibility, body, body_hash, meta_json)
            VALUES ('home', 'typo_bucket', 'model', 'model', 'open', 'x', 'deadbeef', '{}')
            """,
        )


def test_body_rewrite_refuses(tmp_path):
    s = store(tmp_path)
    pair_id = s.insert_pair("Her brother's name is Elias.")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        s.conn.execute("UPDATE entries SET body = 'changed' WHERE id = ?", (pair_id,))


def test_sealed_entry_does_not_retrieve(tmp_path):
    s = store(tmp_path)
    pair_id = s.insert_pair("Her brother's name is Elias.")
    note_id = s.insert_entry(
        body="Elias betrayed her in winter.",
        bucket="inference",
        signature="model",
        authority="inference",
        origins=[(pair_id, "derived_from")],
    )
    assert s.search("Elias")
    s.seal(entry_id=note_id, quote="Seal the betrayal note.")
    bodies = [row["body"] for row in s.search("betrayed")]
    assert bodies == []


def test_superseded_ground_not_current(tmp_path):
    s = store(tmp_path)
    pair_id = s.insert_pair("Her brother's name is Elias.")
    old_id = s.insert_entry(
        body="Elias betrayed her in spring.",
        bucket="canon",
        signature="author",
        authority="ground",
        origins=[(pair_id, "spoken_in")],
    )
    new_id = s.supersede(old_id=old_id, new_body="Elias betrayed her in winter.")
    current = list(s.conn.execute("SELECT id, body FROM current_ground"))
    assert [(row["id"], row["body"]) for row in current] == [
        (new_id, "Elias betrayed her in winter."),
    ]


def test_search_writes_retrieval_log(tmp_path):
    s = store(tmp_path)
    s.insert_pair("Her brother's name is Elias.")
    before = s.conn.execute("SELECT COUNT(*) AS n FROM retrieval_log").fetchone()["n"]
    s.search("brother")
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
        s.insert_pair("context manager closes cleanly")
    # Re-open after close — would fail on Windows if the handle leaked.
    with ForestStore(db_path) as s:
        count = s.conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
        assert count == 1
