# migrate — v0.1 store to v0.2 store (status columns -> record trails).
#
# Stores: a fresh v0.2 database; the v0.1 file is never written
# Refuses: body_hash mismatches (an entry whose hash does not match its body)
# Returns: report dict with counts and honesty notes
# Test: tests/test_migrate.py
#
# v0.1 stored status in mutable columns (authority, visibility, superseded_by).
# v0.2 derives status from the append-only record trail. This migration
# translates the old columns into synthetic adoption/sealing records so old
# trails survive, marked with signature 'migration' so they are never mistaken
# for authority-holder acts performed at the time.

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from forest_memory.core import ForestError, ForestStore, hash_body

_SYNTH_ADOPTION_BODY = (
    "migrated from v0.1: the authority column asserted ground; "
    "no contemporaneous adoption record was found"
)
_SYNTH_SEALING_BODY = (
    "migrated from v0.1: the visibility column asserted sealed; "
    "no contemporaneous sealing record was found"
)


def migrate_v01_to_v02(old_path: str | Path, new_path: str | Path) -> dict:
    """Copy a v0.1 Forest store into a fresh v0.2 store at new_path.

    Entries and edges keep their ids and timestamps. Status columns are
    translated into record trails:

    - ``authority='ground'``: if the entry reaches an adoption_record through
      its ``derived_from`` edge (the v0.1 ceremony shape), an ``adopts`` edge
      is added from that record. Otherwise a synthetic adoption_record signed
      'migration' is created.
    - ``visibility='sealed'``: a synthetic sealing_record is created unless a
      seals edge already applies. ``hidden``/``deep`` have no v0.2 equivalent
      and become open (reported in notes).
    - ``superseded_by``: a ``supersedes`` edge is synthesized if missing.
    - ``bucket='superseded_canon'`` becomes ``canon`` (superseded is derived).
    """
    new_path = Path(new_path)
    if new_path.exists():
        raise ForestError(f"refusing to overwrite existing file: {new_path}")

    old = sqlite3.connect(f"file:{Path(old_path)}?mode=ro", uri=True)
    old.row_factory = sqlite3.Row
    report: dict = {"entries": 0, "edges": 0, "synthetic_records": 0, "notes": []}

    try:
        entries = list(old.execute("SELECT * FROM entries ORDER BY id"))
        bad = [e["id"] for e in entries if hash_body(e["body"]) != e["body_hash"]]
        if bad:
            raise ForestError(
                f"body_hash does not match body for entries {bad}; "
                "the v0.1 store was tampered with or written without the wrapper — "
                "resolve before migrating"
            )

        store = ForestStore(new_path)
        store.init_schema()
        conn = store.conn
        with conn:
            for e in entries:
                bucket = "canon" if e["bucket"] == "superseded_canon" else e["bucket"]
                conn.execute(
                    """
                    INSERT INTO entries
                      (id, created_at, forest, bucket, signature, body, body_hash, meta_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        e["id"], e["created_at"], e["forest"], bucket,
                        e["signature"], e["body"], e["body_hash"], e["meta_json"],
                    ),
                )
                report["entries"] += 1

            for g in old.execute("SELECT * FROM edges ORDER BY id"):
                try:
                    conn.execute(
                        """
                        INSERT INTO edges (id, from_id, to_id, kind, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (g["id"], g["from_id"], g["to_id"], g["kind"], g["created_at"]),
                    )
                    report["edges"] += 1
                except sqlite3.IntegrityError as exc:
                    report["notes"].append(f"edge {g['id']} skipped: {exc}")

            for e in entries:
                _translate_status(conn, e, report)

            for r in old.execute("SELECT * FROM retrieval_log ORDER BY id"):
                conn.execute(
                    """
                    INSERT INTO retrieval_log
                      (id, created_at, query, open_buckets_json, result_ids_json, note)
                    VALUES (?, ?, ?, ?, '[]', ?)
                    """,
                    (r["id"], r["created_at"], r["query"], r["open_buckets_json"], r["note"]),
                )
        store.close()
    finally:
        old.close()
    return report


def _synthetic_record(conn: sqlite3.Connection, *, bucket: str, body: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO entries (forest, bucket, signature, body, body_hash, meta_json)
        VALUES ('home', ?, 'migration', ?, ?, '{}')
        """,
        (bucket, body, hash_body(body)),
    )
    return int(cur.lastrowid)


def _translate_status(conn: sqlite3.Connection, e: sqlite3.Row, report: dict) -> None:
    entry_id = e["id"]

    if e["authority"] == "ground":
        has_adopts = conn.execute(
            """
            SELECT 1 FROM edges a JOIN entries r ON r.id = a.from_id
            WHERE a.to_id = ? AND a.kind = 'adopts' AND r.bucket = 'adoption_record'
            """,
            (entry_id,),
        ).fetchone()
        if not has_adopts:
            record = conn.execute(
                """
                SELECT r.id FROM edges d JOIN entries r ON r.id = d.to_id
                WHERE d.from_id = ? AND d.kind = 'derived_from'
                  AND r.bucket = 'adoption_record'
                """,
                (entry_id,),
            ).fetchone()
            if record:
                record_id = record["id"]
            else:
                record_id = _synthetic_record(
                    conn, bucket="adoption_record", body=_SYNTH_ADOPTION_BODY
                )
                report["synthetic_records"] += 1
            conn.execute(
                "INSERT OR IGNORE INTO edges (from_id, to_id, kind) VALUES (?, ?, 'adopts')",
                (record_id, entry_id),
            )

    if e["visibility"] == "sealed":
        latest = conn.execute(
            """
            SELECT kind FROM edges WHERE to_id = ? AND kind IN ('seals','unseals')
            ORDER BY id DESC LIMIT 1
            """,
            (entry_id,),
        ).fetchone()
        if latest is None or latest["kind"] != "seals":
            record_id = _synthetic_record(
                conn, bucket="sealing_record", body=_SYNTH_SEALING_BODY
            )
            report["synthetic_records"] += 1
            conn.execute(
                "INSERT INTO edges (from_id, to_id, kind) VALUES (?, ?, 'seals')",
                (record_id, entry_id),
            )
    elif e["visibility"] in ("hidden", "deep"):
        report["notes"].append(
            f"entry {entry_id}: visibility '{e['visibility']}' has no v0.2 "
            "equivalent; now open (seal it if it must not retrieve)"
        )

    if e["superseded_by"] is not None:
        conn.execute(
            "INSERT OR IGNORE INTO edges (from_id, to_id, kind) VALUES (?, ?, 'supersedes')",
            (e["superseded_by"], entry_id),
        )
