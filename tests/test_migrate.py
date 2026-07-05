# Migration: v0.1 status columns -> v0.2 record trails.
#
# The v0.1 store is built raw against tests/fixtures/schema_v01.sql, shaped
# exactly the way the v0.1 wrapper wrote it (including the exploit shapes the
# audit used), then migrated and checked against the derived views.

import json
import sqlite3
from pathlib import Path

import pytest

from forest_memory import ForestError, ForestStore, check_file_drift, hash_body
from forest_memory.migrate import migrate_v01_to_v02

FIXTURE = Path(__file__).parent / "fixtures" / "schema_v01.sql"


def make_v01(path):
    conn = sqlite3.connect(path)
    conn.executescript(FIXTURE.read_text(encoding="utf-8"))

    def insert(body, bucket, signature, authority, visibility="open"):
        cur = conn.execute(
            """
            INSERT INTO entries
              (forest, bucket, signature, authority, visibility, body, body_hash, meta_json)
            VALUES ('home', ?, ?, ?, ?, ?, ?, '{}')
            """,
            (bucket, signature, authority, visibility, body, hash_body(body)),
        )
        return cur.lastrowid

    def edge(from_id, to_id, kind):
        conn.execute(
            "INSERT INTO edges (from_id, to_id, kind) VALUES (?, ?, ?)",
            (from_id, to_id, kind),
        )

    # Legitimate v0.1 ceremony shape: record adopts draft, canon derived_from record.
    pair = insert("USER:\nanchor", "session_pair", "conversation", "record")
    draft = insert("Elias betrayed her in winter.", "draft", "model", "draft")
    edge(draft, pair, "spoken_in")
    record = insert("Adopt this.", "adoption_record", "author", "record")
    edge(record, draft, "adopts")
    canon = insert("Elias betrayed her in winter.", "canon", "author", "ground")
    edge(canon, record, "derived_from")

    # Superseded old canon (v0.1 flipped bucket + superseded_by column).
    old_canon = insert("Elias betrayed her in spring.", "superseded_canon", "author", "ground")
    conn.execute("UPDATE entries SET superseded_by = ? WHERE id = ?", (canon, old_canon))
    edge(canon, old_canon, "supersedes")

    # The exploit shape: ground forged with no trail at all.
    forged = insert("Forged ground, no ceremony.", "note", "model", "ground")

    # Sealed via the mutable column, no sealing record.
    sealed = insert("The sealed secret.", "inference", "model", "inference", "sealed")

    conn.execute(
        "INSERT INTO retrieval_log (query, open_buckets_json) VALUES ('elias', '[]')"
    )
    conn.commit()
    conn.close()
    return {"canon": canon, "old_canon": old_canon, "forged": forged, "sealed": sealed}


def test_migration_translates_status_into_trails(tmp_path):
    old_db = tmp_path / "v01.db"
    ids = make_v01(old_db)
    new_db = tmp_path / "v02.db"
    report = migrate_v01_to_v02(old_db, new_db)

    with ForestStore(new_db) as s:
        ground = {r["id"] for r in s.conn.execute("SELECT id FROM current_ground")}
        # Real canon survives; superseded old canon is not current.
        assert ids["canon"] in ground
        assert ids["old_canon"] not in ground

        # Forged ground survives as ground (the old column asserted it) but the
        # trail is honest: its adoption record is signed 'migration'.
        assert ids["forged"] in ground
        synth = s.conn.execute(
            """
            SELECT r.signature FROM edges a JOIN entries r ON r.id = a.from_id
            WHERE a.to_id = ? AND a.kind = 'adopts'
            """,
            (ids["forged"],),
        ).fetchone()
        assert synth["signature"] == "migration"

        # Sealed stays sealed: absent from FTS and from search.
        assert s.is_sealed(ids["sealed"])
        hits = list(
            s.conn.execute("SELECT rowid FROM entries_fts WHERE entries_fts MATCH 'secret'")
        )
        assert hits == []

        # New store is fully locked: no status columns, no updates.
        cols = {row["name"] for row in s.conn.execute("PRAGMA table_info(entries)")}
        assert not {"authority", "visibility", "superseded_by"} & cols
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            s.conn.execute("UPDATE entries SET signature = 'x' WHERE id = 1")

        n_log = s.conn.execute("SELECT COUNT(*) AS n FROM retrieval_log").fetchone()["n"]
        assert n_log == 1

    assert report["entries"] == 7
    # forged ground + column-only seal + old_canon (ground with no v0.1 record)
    assert report["synthetic_records"] == 3


def test_drift_uses_ground_hash_on_migrated_store(tmp_path):
    # A migrated adoption record carries two adopts edges (v0.1 record->draft
    # plus the migration-added record->ground). Drift must compare against the
    # ground entry's hash, not the draft's.
    old_db = tmp_path / "v01.db"
    make_v01(old_db)
    new_db = tmp_path / "v02.db"
    migrate_v01_to_v02(old_db, new_db)

    with ForestStore(new_db) as s:
        record = s.conn.execute(
            "SELECT id FROM entries WHERE bucket = 'adoption_record' AND signature != 'migration'"
        ).fetchone()["id"]
        n_adopts = s.conn.execute(
            "SELECT COUNT(*) AS n FROM edges WHERE from_id = ? AND kind = 'adopts'",
            (record,),
        ).fetchone()["n"]
        assert n_adopts == 2

        canon_file = tmp_path / "canon.md"
        canon_file.write_text("Elias betrayed her in winter.", encoding="utf-8")
        assert check_file_drift(canon_file, s, record) == []

        canon_file.write_text("Elias forgave her in winter.", encoding="utf-8")
        warnings = check_file_drift(canon_file, s, record)
        assert len(warnings) == 1
        assert "does not match adoption trail" in warnings[0]["text"]


def test_migration_refuses_tampered_hashes(tmp_path):
    old_db = tmp_path / "v01.db"
    make_v01(old_db)
    conn = sqlite3.connect(old_db)
    conn.execute("UPDATE entries SET body_hash = ? WHERE id = 1", ("a" * 64,))
    conn.commit()
    conn.close()
    with pytest.raises(ForestError, match="tampered|does not match"):
        migrate_v01_to_v02(old_db, tmp_path / "v02.db")


def test_migration_refuses_overwrite(tmp_path):
    old_db = tmp_path / "v01.db"
    make_v01(old_db)
    target = tmp_path / "exists.db"
    target.write_text("precious")
    with pytest.raises(ForestError, match="refusing to overwrite"):
        migrate_v01_to_v02(old_db, target)
