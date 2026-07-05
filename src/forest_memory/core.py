# core — Forest store: insert, adopt, supersede, seal, unseal, search.
#
# Stores: entries + edges in SQLite; status is DERIVED from the record trail
# Refuses: unsigned inserts, orphan non-roots, empty body, ceremony buckets
#          and ceremony edge kinds outside ceremonies (Python + schema)
# Returns: entry id on insert; rows on search
# Test: tests/test_constitutional.py, tests/test_promotion_boundary.py

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence

from forest_memory.schema import load_schema_sql

# Buckets only a ceremony may write. insert_entry refuses them at the front
# door; there is no authority parameter to forge — ground is a derived status.
CEREMONY_BUCKETS = frozenset(
    {"canon", "adoption_record", "sealing_record", "unsealing_record"}
)

# Edge kinds that constitute ceremony acts. add_edge and insert_entry origins
# refuse them; only adopt/supersede/seal/unseal write them.
CEREMONY_EDGE_KINDS = frozenset({"adopts", "supersedes", "seals", "unseals"})


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
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self._refuse_v01_store()

    def _refuse_v01_store(self) -> None:
        # v0.1 stored status in mutable columns; v0.2 derives it from the
        # record trail. Opening a v0.1 file with v0.2 code would fail in
        # confusing ways — refuse up front and point at the migration.
        cols = {row["name"] for row in self.conn.execute("PRAGMA table_info(entries)")}
        if {"authority", "visibility"} & cols:
            self.conn.close()
            raise ForestError(
                f"{self.path} is a v0.1 store (mutable status columns); "
                "migrate it with forest_memory.migrate.migrate_v01_to_v02 "
                "before opening"
            )

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

    # -- inserts ---------------------------------------------------------------

    def insert_entry(
        self,
        *,
        body: str,
        forest: str = "home",
        bucket: str,
        signature: str,
        origins: Sequence[tuple[int, str]] | None = None,
        meta: dict | None = None,
    ) -> int:
        """Insert an entry and its origin edges.

        Non-root entries require at least one origin. The only root bucket is
        session_pair. Ceremony buckets and ceremony edge kinds are refused here:
        ground, supersession, and sealing exist only as record trails written by
        adopt / supersede / seal / unseal.
        """
        if bucket in CEREMONY_BUCKETS:
            raise ForestError(
                f"bucket {bucket!r} is written only by a ceremony; "
                "use adopt/supersede/seal/unseal"
            )
        origins = list(origins or [])
        for _, kind in origins:
            if kind in CEREMONY_EDGE_KINDS:
                raise ForestError(
                    f"edge kind {kind!r} is a ceremony act; "
                    "use adopt/supersede/seal/unseal"
                )
        if bucket != "session_pair" and not origins:
            raise ForestError("orphan insert refused")

        with self.conn:
            entry_id = self._insert_row(
                body=body, forest=forest, bucket=bucket, signature=signature, meta=meta
            )
            for to_id, kind in origins:
                self._add_edge(entry_id, to_id, kind)
        return entry_id

    def _insert_row(
        self,
        *,
        body: str,
        forest: str,
        bucket: str,
        signature: str,
        meta: dict | None = None,
    ) -> int:
        """Raw row insert shared by insert_entry and the ceremonies."""
        if not signature or not signature.strip():
            raise ForestError("unsigned insert refused")
        if not body or not body.strip():
            raise ForestError("empty body refused")
        cur = self.conn.execute(
            """
            INSERT INTO entries (forest, bucket, signature, body, body_hash, meta_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                forest,
                bucket,
                signature,
                body,
                hash_body(body),
                json.dumps(meta or {}, sort_keys=True),
            ),
        )
        return int(cur.lastrowid)

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
        )
        if previous_pair_id is not None:
            self.add_edge(pair_id, previous_pair_id, "responds_to")
        return pair_id

    # -- edges -----------------------------------------------------------------

    def add_edge(self, from_id: int, to_id: int, kind: str) -> None:
        if kind in CEREMONY_EDGE_KINDS:
            raise ForestError(
                f"edge kind {kind!r} is a ceremony act; "
                "use adopt/supersede/seal/unseal"
            )
        self._add_edge(from_id, to_id, kind)

    def _add_edge(self, from_id: int, to_id: int, kind: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO edges (from_id, to_id, kind) VALUES (?, ?, ?)",
            (from_id, to_id, kind),
        )

    # -- status (derived, read-only) --------------------------------------------

    def is_ground(self, entry_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM current_ground WHERE id = ?", (entry_id,)
        ).fetchone()
        return row is not None

    def is_sealed(self, entry_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM sealed_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        return row is not None

    # -- ceremonies --------------------------------------------------------------

    def adopt(
        self,
        *,
        adopted_entry_id: int,
        quote: str,
        ground_body: str,
        adopting_signature: str = "author",
        ground_signature: str = "author",
    ) -> tuple[int, int]:
        """Record an authority-holder adoption (low-level constitutional write).

        Route promotion through ``ceremony.adopt_to_ground`` (or your own gate).
        Calling this directly skips ceremonial refusals.

        One transaction:
          1. new canon entry (the ground text), derived_from -> adopted entry
          2. adoption_record quoting the authority-holder verbatim,
             adopts -> the new canon entry

        Ground is not a column: the entry IS ground because this trail exists.
        The store records ``adopting_signature`` verbatim; authenticating that
        the named speaker actually spoke is the host application's job.

        Returns (record_id, ground_entry_id).
        """
        with self.conn:
            ground_id = self._insert_row(
                body=ground_body, forest="home", bucket="canon",
                signature=ground_signature,
            )
            self._add_edge(ground_id, adopted_entry_id, "derived_from")
            record_id = self._insert_row(
                body=quote, forest="home", bucket="adoption_record",
                signature=adopting_signature,
            )
            self._add_edge(record_id, ground_id, "adopts")
        return record_id, ground_id

    def supersede(
        self,
        *,
        old_id: int,
        new_body: str,
        adopting_words: str,
        adopting_signature: str = "author",
        signature: str = "author",
    ) -> int:
        """Replace current ground. Supersession is itself an adoption ceremony.

        Refuses unless the old entry is currently ground — superseding an
        inference or draft was a laundering side-channel in v0.1. The
        replacement gets its own adoption record in the same transaction.
        """
        if not self.is_ground(old_id):
            raise ForestError(
                f"entry {old_id} is not current ground; only ground can be superseded"
            )
        if not adopting_words or not adopting_words.strip():
            raise ForestError("supersession without adopting words refused")
        with self.conn:
            new_id = self._insert_row(
                body=new_body, forest="home", bucket="canon", signature=signature
            )
            self._add_edge(new_id, old_id, "supersedes")
            record_id = self._insert_row(
                body=adopting_words.strip(), forest="home",
                bucket="adoption_record", signature=adopting_signature,
            )
            self._add_edge(record_id, new_id, "adopts")
        return new_id

    def seal(self, *, entry_id: int, quote: str, signature: str = "author") -> int:
        """Seal an entry: a record insert, nothing mutated.

        The seals edge trips the FTS shadow trigger, removing the body from
        the index; the sealed_entries view derives status from the trail.
        """
        if self.is_sealed(entry_id):
            raise ForestError(f"entry {entry_id} is already sealed")
        with self.conn:
            record_id = self._insert_row(
                body=quote, forest="home", bucket="sealing_record", signature=signature
            )
            self._add_edge(record_id, entry_id, "seals")
        return record_id

    def unseal(self, *, entry_id: int, quote: str, signature: str = "author") -> int:
        """Unseal an entry: the same ceremony in reverse, also a record insert."""
        if not self.is_sealed(entry_id):
            raise ForestError(f"entry {entry_id} is not sealed")
        with self.conn:
            record_id = self._insert_row(
                body=quote, forest="home", bucket="unsealing_record",
                signature=signature,
            )
            self._add_edge(record_id, entry_id, "unseals")
        return record_id

    # -- retrieval ----------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        open_buckets: Iterable[str] | None = None,
    ) -> list[sqlite3.Row]:
        """FTS search. Logs scope AND result ids to retrieval_log.

        Sealed bodies are absent from the FTS index itself (removed by the
        sealing ceremony's trigger); the sealed_entries exclusion here is a
        defense in depth, not the primary guarantee.
        """
        buckets = list(open_buckets or [])
        params: list[object] = [query]
        bucket_clause = ""
        if buckets:
            placeholders = ",".join("?" for _ in buckets)
            bucket_clause = f"AND e.bucket IN ({placeholders})"
            params.extend(buckets)
        rows = list(
            self.conn.execute(
                f"""
                SELECT e.*
                FROM entries_fts f
                JOIN entries e ON e.id = f.rowid
                WHERE entries_fts MATCH ?
                  AND e.id NOT IN (SELECT id FROM sealed_entries)
                  {bucket_clause}
                ORDER BY rank
                """,
                params,
            )
        )
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO retrieval_log (query, open_buckets_json, result_ids_json)
                VALUES (?, ?, ?)
                """,
                (query, json.dumps(buckets), json.dumps([r["id"] for r in rows])),
            )
        return rows
