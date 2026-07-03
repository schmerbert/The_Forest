# core — Forest store: insert, adopt, supersede, seal, search.
#
# Stores: entries + edges in SQLite
# Refuses: unsigned inserts, orphan non-roots, empty body (Python + schema)
# Returns: entry id on insert; rows on search
# Test: tests/test_constitutional.py

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence

from forest_memory.schema import load_schema_sql


class ForestError(Exception):
    """Raised when the Forest constitution refuses a write."""


def hash_body(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class ForestStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> ForestStore:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def init_schema(self, schema_path: str | Path | None = None) -> None:
        if schema_path is not None:
            sql = Path(schema_path).read_text(encoding="utf-8")
        else:
            sql = load_schema_sql()
        self.conn.executescript(sql)
        self.conn.commit()

    def insert_entry(
        self,
        *,
        body: str,
        forest: str = "home",
        bucket: str,
        signature: str,
        authority: str,
        visibility: str = "open",
        origins: Sequence[tuple[int, str]] | None = None,
        meta: dict | None = None,
    ) -> int:
        """Insert an entry and its origin edges.

        Non-root entries require at least one origin. The only root bucket is
        session_pair. This keeps ancestry cheap at write time and impossible to
        forget later.
        """
        if not signature or not signature.strip():
            raise ForestError("unsigned insert refused")
        if not body or not body.strip():
            raise ForestError("empty body refused")
        origins = list(origins or [])
        if bucket != "session_pair" and not origins:
            raise ForestError("orphan insert refused")

        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO entries
                  (forest, bucket, signature, authority, visibility, body, body_hash, meta_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    forest,
                    bucket,
                    signature,
                    authority,
                    visibility,
                    body,
                    hash_body(body),
                    json.dumps(meta or {}, sort_keys=True),
                ),
            )
            entry_id = int(cur.lastrowid)
            for to_id, kind in origins:
                self.add_edge(entry_id, to_id, kind)
        return entry_id

    def insert_pair(
        self,
        user_text: str,
        assistant_text: str = "",
        *,
        previous_pair_id: int | None = None,
    ) -> int:
        body = f"USER:\n{user_text}\n\nASSISTANT:\n{assistant_text}".strip()
        pair_id = self.insert_entry(
            body=body,
            forest="home",
            bucket="session_pair",
            signature="conversation",
            authority="record",
            visibility="open",
        )
        if previous_pair_id is not None:
            self.add_edge(pair_id, previous_pair_id, "responds_to")
        return pair_id

    def add_edge(self, from_id: int, to_id: int, kind: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO edges (from_id, to_id, kind) VALUES (?, ?, ?)",
            (from_id, to_id, kind),
        )

    def adopt(
        self,
        *,
        adopted_entry_id: int,
        quote: str,
        new_ground_body: str | None = None,
    ) -> int:
        """Record an authority-holder adoption (low-level constitutional write).

        Route promotion through ``ceremony.adopt_to_ground`` (or your own gate).
        Calling this directly skips ceremonial refusals such as praise-only quotes.

        Does not pretend the adopted entry's signature changed. If new_ground_body
        is supplied, a new author-signed ground entry is inserted from the record.
        """
        record_id = self.insert_entry(
            body=quote,
            forest="home",
            bucket="adoption_record",
            signature="author",
            authority="record",
            origins=[(adopted_entry_id, "adopts")],
        )
        if new_ground_body:
            self.insert_entry(
                body=new_ground_body,
                forest="home",
                bucket="canon",
                signature="author",
                authority="ground",
                origins=[(record_id, "derived_from")],
            )
        return record_id

    def supersede(self, *, old_id: int, new_body: str, signature: str = "author") -> int:
        with self.conn:
            new_id = self.insert_entry(
                body=new_body,
                forest="home",
                bucket="canon",
                signature=signature,
                authority="ground",
                origins=[(old_id, "supersedes")],
            )
            self.conn.execute(
                "UPDATE entries SET superseded_by = ? WHERE id = ?",
                (new_id, old_id),
            )
            self.conn.execute(
                "UPDATE entries SET bucket = 'superseded_canon' WHERE id = ? AND bucket = 'canon'",
                (old_id,),
            )
        return new_id

    def seal(self, *, entry_id: int, quote: str) -> int:
        with self.conn:
            record_id = self.insert_entry(
                body=quote,
                forest="home",
                bucket="sealing_record",
                signature="author",
                authority="record",
                origins=[(entry_id, "seals")],
            )
            self.conn.execute(
                "UPDATE entries SET visibility = 'sealed' WHERE id = ?",
                (entry_id,),
            )
        return record_id

    def search(
        self,
        query: str,
        *,
        open_buckets: Iterable[str] | None = None,
    ) -> list[sqlite3.Row]:
        buckets = list(open_buckets or [])
        self.conn.execute(
            "INSERT INTO retrieval_log (query, open_buckets_json) VALUES (?, ?)",
            (query, json.dumps(buckets)),
        )
        params: list[object] = [query]
        bucket_clause = ""
        if buckets:
            placeholders = ",".join("?" for _ in buckets)
            bucket_clause = f"AND e.bucket IN ({placeholders})"
            params.extend(buckets)
        return list(
            self.conn.execute(
                f"""
                SELECT e.*
                FROM entries_fts f
                JOIN entries e ON e.id = f.rowid
                WHERE entries_fts MATCH ?
                  AND e.visibility != 'sealed'
                  {bucket_clause}
                ORDER BY rank
                """,
                params,
            )
        )
