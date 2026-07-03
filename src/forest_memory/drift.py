# drift — on-disk file vs adoption record body_hash (FOREST.md §10).
#
# Stores: nothing
# Refuses: entry is not an adoption_record
# Returns: list of warning dicts
# Test: tests/test_drift.py

from __future__ import annotations

import sqlite3
from pathlib import Path

from forest_memory.core import ForestError, ForestStore, hash_body


def adoption_hash_for_entry(conn: sqlite3.Connection, entry_id: int) -> str | None:
    row = conn.execute(
        "SELECT body_hash, bucket FROM entries WHERE id = ?",
        (entry_id,),
    ).fetchone()
    if row is None:
        return None
    if row["bucket"] != "adoption_record":
        raise ForestError(f"entry {entry_id} is not an adoption_record")
    return row["body_hash"]


def check_file_drift(
    file_path: Path,
    store: ForestStore,
    adoption_entry_id: int,
) -> list[dict]:
    """Return warnings if a readable file no longer matches the adoption trail."""
    warnings: list[dict] = []
    if not file_path.exists():
        warnings.append({
            "label": "warning",
            "text": f"file missing: {file_path}",
            "path": str(file_path),
        })
        return warnings

    recorded = adoption_hash_for_entry(store.conn, adoption_entry_id)
    if recorded is None:
        warnings.append({
            "label": "warning",
            "text": f"no adoption_record for id {adoption_entry_id}",
            "id": adoption_entry_id,
        })
        return warnings

    actual = hash_body(file_path.read_text(encoding="utf-8"))
    if actual != recorded:
        warnings.append({
            "label": "warning",
            "text": "file does not match adoption trail",
            "path": str(file_path),
            "adoption_entry_id": adoption_entry_id,
            "expected_hash": recorded,
            "actual_hash": actual,
        })
    return warnings
