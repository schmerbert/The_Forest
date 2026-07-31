# core — Forest store: write, recall, open/around/step/read, root, walk_back.
#
# Contract: README.md (canonical verbs, preview≠read, walk tickets, scroll_ptr)
# Stores: entries + edges in SQLite; status DERIVED from the record trail
# Refuses: unsigned inserts, orphan non-pairs, ceremony buckets/edges outside
#          ceremonies, pre-0.4 stores, unlabeled scraps, unbounded recall bodies,
#          FTS injection via unsafe queries, sealed/superseded rooting,
#          pairs without scroll_ptr, forged walk tickets, ungated walk_back
# Returns: entry ids; jurisdiction-first previews; Trail tickets; read bodies
# Test: tests/test_constitutional.py, tests/test_promotion_boundary.py,
#       tests/test_recall.py, tests/test_trail.py, tests/test_adversarial.py

from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, Sequence

from forest_memory.schema import load_schema_sql

if TYPE_CHECKING:
    from forest_memory.scroll import Scroll

ScrubFn = Callable[[str], str]

CEREMONY_BUCKETS = frozenset(
    {"adoption_record", "sealing_record", "unsealing_record"}
)
CEREMONY_EDGE_KINDS = frozenset({"adopts", "supersedes", "seals", "unseals"})
ROOT_BUCKET = "pair"  # only bucket that may insert with no origin edge

# Edge kinds excluded from around() — walk only traverses authored relationships.
_AROUND_EXCLUDED_KINDS = CEREMONY_EDGE_KINDS

_AUDIT_EXCERPT = 160


class ForestError(Exception):
    """Raised when the Forest constitution refuses a write or recall."""


def hash_body(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def default_scrub(text: str) -> str:
    """Minimum scrub: strip transport/harness scaffolding; do not rewrite claims.

    README: scrub removes protocol noise. Transformative compression must be a
    separately attributed synthesis, not silent scrub.
    """
    text = text.strip()
    text = re.sub(r"</?(?:think|scratchpad|system)[^>]*>", "", text, flags=re.I)
    return text.strip()


def _is_cjk_run(token: str) -> bool:
    """True if token uses scripts FTS5 unicode61 typically keeps unbroken."""
    for ch in token:
        o = ord(ch)
        if (
            0x3040 <= o <= 0x30FF  # Hiragana / Katakana
            or 0x3400 <= o <= 0x9FFF  # CJK Unified
            or 0xAC00 <= o <= 0xD7AF  # Hangul syllables
            or 0xF900 <= o <= 0xFAFF  # CJK Compatibility Ideographs
            or 0x20000 <= o <= 0x2FA1F  # CJK Extension
        ):
            return True
    return False


def _plain_language_fts_query(query: str) -> str:
    """Tokenize Unicode words and build a safe FTS5 query.

    Keeps letters/digits from any script (compatible with FTS5 unicode61).
    Drops punctuation and underscores so FTS operators are not injected.
    Each token is phrase-quoted. CJK runs use a prefix match because
    unicode61 indexes them as unbroken tokens. Raises ForestError if no
    tokens remain.
    """
    raw = re.findall(r"[^\W_]+", query, flags=re.UNICODE)
    tokens = [t.replace('"', "") for t in raw if t.replace('"', "")]
    if not tokens:
        raise ForestError(
            f"recall: empty query (no word tokens) — got {query!r}"
        )
    parts: list[str] = []
    for t in tokens:
        if _is_cjk_run(t):
            parts.append(f'"{t}"*')
        else:
            parts.append(f'"{t}"')
    return " ".join(parts)


def _direction_for_edge(edge_kind: str, edge_from: int, here: int) -> str:
    """Compute walk direction from 'here' through an edge to the neighbor.

    responds_to (newer→older): at newer → prev; at older → next.
    All other walkable edges: at from_id → out; at to_id → in.
    """
    if edge_kind == "responds_to":
        return "prev" if edge_from == here else "next"
    return "out" if edge_from == here else "in"


def _validate_scroll_ptr(scroll_ptr: dict | None) -> dict:
    if not isinstance(scroll_ptr, dict):
        raise ForestError("write_pair: scroll_ptr required (path + offset)")
    if "path" not in scroll_ptr or "offset" not in scroll_ptr:
        raise ForestError("write_pair: scroll_ptr needs path and offset")
    out: dict = {
        "path": str(scroll_ptr["path"]),
        "offset": int(scroll_ptr["offset"]),
    }
    if "hash" in scroll_ptr and scroll_ptr["hash"] is not None:
        out["hash"] = str(scroll_ptr["hash"])
    return out


@dataclass
class _TicketState:
    position: int
    disclosed: set[tuple[int, str]] = field(default_factory=set)
    spent: bool = False


@dataclass
class Trail:
    """Ephemeral walk cursor proven by an opaque ticket Forest minted."""

    position: int
    ticket: str


def _require_excerpt_bound(excerpt_len: int | None) -> int:
    """Recall/around return previews only — full body is read's job (README)."""
    if excerpt_len is None or excerpt_len <= 0:
        raise ForestError(
            "recall/around require a positive excerpt_len (bounded preview); "
            "full body disclosure is read(), not discovery"
        )
    return excerpt_len


def _row_to_scrap(row: sqlite3.Row, *, excerpt_len: int) -> dict:
    """Packet rule: jurisdiction leads every scrap; body never in preview."""
    body = row["body"]
    scrap = {
        "jurisdiction": row["jurisdiction"],
        "id": row["id"],
        "excerpt": body if len(body) <= excerpt_len else body[:excerpt_len] + "…",
        "bucket": row["bucket"],
        "signature": row["signature"],
    }
    return scrap


def _require_jurisdiction(scrap: dict) -> dict:
    if "jurisdiction" not in scrap or scrap["jurisdiction"] not in ("home", "wild"):
        raise ForestError("unlabeled recall scrap refused (jurisdiction required)")
    return scrap


def commit_turn(
    store: ForestStore,
    scroll: Scroll,
    user_text: str,
    assistant_text: str = "",
    *,
    previous_pair_id: int | None = None,
    scrub: ScrubFn | None = default_scrub,
) -> int:
    """Canonical heartbeat: append exact head to scroll, write pair with scroll_ptr."""
    head = f"USER: {user_text}\nASSISTANT: {assistant_text}"
    offset = scroll.append(head)
    scroll_ptr = {
        "path": str(scroll.path),
        "offset": offset,
        "hash": hash_body(head),
    }
    return store.write_pair(
        user_text,
        assistant_text,
        previous_pair_id=previous_pair_id,
        scroll_ptr=scroll_ptr,
        scrub=scrub,
    )


class ForestStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self._tickets: dict[str, _TicketState] = {}
        self._pending_wild_access: set[int] = set()
        self._refuse_outdated_store()

    def _refuse_outdated_store(self) -> None:
        """Hard cut: only a missing ``entries`` table is treated as fresh.

        If ``entries`` exists — even with zero rows — jurisdiction columns and
        ``forest_meta.schema_version == 0.4.0`` are required. ``init_schema``
        cannot repair an incompatible skeleton (CREATE IF NOT EXISTS).
        """
        entries_table = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entries'"
        ).fetchone()
        if entries_table is None:
            return  # genuinely fresh — ok

        cols = {row["name"] for row in self.conn.execute("PRAGMA table_info(entries)")}
        if "jurisdiction" not in cols:
            self.conn.close()
            raise ForestError(
                f"{self.path} is a pre-0.4 Forest store (missing jurisdiction). "
                "0.4 is a hard cut — start a fresh database; old stores are not opened."
            )
        meta_table = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='forest_meta'"
        ).fetchone()
        if meta_table is None:
            self.conn.close()
            raise ForestError(
                f"{self.path} has an entries table but no forest_meta. "
                "Refuse unknown/partial schema — start a fresh database."
            )
        version_row = self.conn.execute(
            "SELECT value FROM forest_meta WHERE key = 'schema_version'"
        ).fetchone()
        if version_row is None or version_row["value"] != "0.4.0":
            got = version_row["value"] if version_row else "(missing)"
            self.conn.close()
            raise ForestError(
                f"{self.path} forest_meta schema_version={got!r}; expected '0.4.0'. "
                "Start a fresh database."
            )

    def close(self) -> None:
        self._tickets.clear()
        self._pending_wild_access.clear()
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

    # -- tickets ---------------------------------------------------------------

    def _mint_ticket(self, position: int) -> Trail:
        ticket = secrets.token_urlsafe(16)
        self._tickets[ticket] = _TicketState(position=position)
        return Trail(position=position, ticket=ticket)

    def _require_ticket(self, trail: Trail) -> _TicketState:
        if not isinstance(trail, Trail) or not trail.ticket:
            raise ForestError("walk: unknown or forged ticket refused")
        state = self._tickets.get(trail.ticket)
        if state is None:
            raise ForestError("walk: unknown or forged ticket refused")
        if state.spent:
            raise ForestError("walk: spent ticket refused")
        if state.position != trail.position:
            raise ForestError("walk: ticket/position mismatch")
        return state

    def _spend_ticket(self, trail: Trail) -> None:
        state = self._require_ticket(trail)
        state.spent = True

    # -- write -----------------------------------------------------------------

    def write(
        self,
        *,
        body: str,
        bucket: str,
        signature: str,
        jurisdiction: str = "home",
        source: str | None = None,
        origins: Sequence[tuple[int, str]] | None = None,
        meta: dict | None = None,
        scrub: ScrubFn | None = default_scrub,
    ) -> int:
        """Scrub, then insert into entries (+ origin edges as required)."""
        if bucket in CEREMONY_BUCKETS:
            raise ForestError(
                f"bucket {bucket!r} is written only by a ceremony; "
                "use root_to_ground/supersede/seal/unseal"
            )
        origins = list(origins or [])
        for _, kind in origins:
            if kind in CEREMONY_EDGE_KINDS:
                raise ForestError(
                    f"edge kind {kind!r} is a ceremony act; "
                    "use root_to_ground/supersede/seal/unseal"
                )
        if bucket != ROOT_BUCKET and not origins:
            raise ForestError("orphan insert refused")

        if scrub is not None:
            body = scrub(body)

        with self.conn:
            entry_id = self._insert_row(
                body=body,
                jurisdiction=jurisdiction,
                bucket=bucket,
                signature=signature,
                source=source,
                meta=meta,
            )
            for to_id, kind in origins:
                self._add_edge(entry_id, to_id, kind)
        return entry_id

    def write_pair(
        self,
        user_text: str,
        assistant_text: str = "",
        *,
        scroll_ptr: dict,
        previous_pair_id: int | None = None,
        scrub: ScrubFn | None = default_scrub,
    ) -> int:
        """Heartbeat write: one cleaned user+model turn in home / pair.

        ``scroll_ptr`` is required (``path`` + ``offset``) so the pair links to
        session evidence. Prefer ``commit_turn`` which appends then writes.
        Pending wild reads (earned via ticket) become ``cites`` edges from the
        new pair — they entered context for this turn.
        """
        ptr = _validate_scroll_ptr(scroll_ptr)
        body = f"USER:\n{user_text}\n\nASSISTANT:\n{assistant_text}".strip()
        pending = list(self._pending_wild_access)
        self._pending_wild_access.clear()
        with self.conn:
            if scrub is not None:
                body = scrub(body)
            pair_id = self._insert_row(
                body=body,
                jurisdiction="home",
                bucket="pair",
                signature="conversation",
                meta={"scroll_ptr": ptr},
            )
            for wild_id in pending:
                self._add_edge(pair_id, wild_id, "cites")
            if previous_pair_id is not None:
                self._add_edge(pair_id, previous_pair_id, "responds_to")
        return pair_id

    def _insert_row(
        self,
        *,
        body: str,
        jurisdiction: str,
        bucket: str,
        signature: str,
        source: str | None = None,
        meta: dict | None = None,
        ceremony: bool = False,
    ) -> int:
        """Low-level insert. ceremony=True is required for CEREMONY_BUCKETS."""
        if not ceremony and bucket in CEREMONY_BUCKETS:
            raise ForestError(
                f"bucket {bucket!r} is written only by a ceremony; "
                "use root_to_ground/supersede/seal/unseal"
            )
        if not signature or not signature.strip():
            raise ForestError("unsigned insert refused")
        if not body or not body.strip():
            raise ForestError("empty body refused")
        if jurisdiction not in ("home", "wild"):
            raise ForestError(f"invalid jurisdiction {jurisdiction!r}")
        cur = self.conn.execute(
            """
            INSERT INTO entries
              (jurisdiction, bucket, source, signature, body, body_hash, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                jurisdiction,
                bucket,
                source,
                signature,
                body,
                hash_body(body),
                json.dumps(meta or {}, sort_keys=True),
            ),
        )
        return int(cur.lastrowid)

    # -- edges -----------------------------------------------------------------

    def add_edge(self, from_id: int, to_id: int, kind: str) -> None:
        if kind in CEREMONY_EDGE_KINDS:
            raise ForestError(
                f"edge kind {kind!r} is a ceremony act; "
                "use root_to_ground/supersede/seal/unseal"
            )
        with self.conn:
            self._add_edge(from_id, to_id, kind)

    def _add_edge(self, from_id: int, to_id: int, kind: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO edges (from_id, to_id, kind) VALUES (?, ?, ?)",
            (from_id, to_id, kind),
        )

    # -- status ----------------------------------------------------------------

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

    def _is_superseded(self, entry_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM edges WHERE to_id = ? AND kind = 'supersedes' LIMIT 1",
            (entry_id,),
        ).fetchone()
        return row is not None

    def get(self, entry_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()

    # -- recall ----------------------------------------------------------------

    def recall_similar(
        self,
        query: str,
        *,
        scope: str = "home",
        open_buckets: Iterable[str] | None = None,
        excerpt_len: int = 160,
        limit: int | None = 20,
    ) -> list[dict]:
        """Bearings via FTS → bounded jurisdiction-first previews. Default scope home.

        Builds a safe FTS5 query from alphanumeric tokens only. Raises ForestError
        on empty/invalid query or SQLite FTS error — does not leak raw sqlite errors.
        """
        bound = _require_excerpt_bound(excerpt_len)
        if scope not in ("home", "wild", "both"):
            raise ForestError(f"invalid recall scope {scope!r}")
        fts_query = _plain_language_fts_query(query)
        buckets = list(open_buckets or [])
        params: list[object] = [fts_query]
        clauses = [
            "entries_fts MATCH ?",
            "e.id NOT IN (SELECT id FROM sealed_entries)",
        ]
        if scope != "both":
            clauses.append("e.jurisdiction = ?")
            params.append(scope)
        if buckets:
            placeholders = ",".join("?" for _ in buckets)
            clauses.append(f"e.bucket IN ({placeholders})")
            params.extend(buckets)
        sql = f"""
            SELECT e.*
            FROM entries_fts f
            JOIN entries e ON e.id = f.rowid
            WHERE {" AND ".join(clauses)}
            ORDER BY rank
        """
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        try:
            rows = list(self.conn.execute(sql, params))
        except sqlite3.OperationalError as exc:
            raise ForestError(f"recall: FTS query failed — {exc}") from exc
        scraps = [_require_jurisdiction(_row_to_scrap(r, excerpt_len=bound)) for r in rows]
        note = json.dumps({"scope": scope})
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO retrieval_log
                  (query, open_buckets_json, result_ids_json, note)
                VALUES (?, ?, ?, ?)
                """,
                (
                    query,
                    json.dumps(buckets),
                    json.dumps([s["id"] for s in scraps]),
                    note,
                ),
            )
        return scraps

    def recall_side(
        self,
        scraps: Sequence[dict],
        *,
        excerpt_len: int = 160,
    ) -> list[dict]:
        """Label host-supplied or alternate-equation scraps. Bounded previews.

        Each scrap may be ``{"id": n}`` (filled from the store) or a packet
        that already includes ``jurisdiction`` and ``excerpt``. Unlabeled is a bug.
        Full bodies refused — use ``read``.
        """
        bound = _require_excerpt_bound(excerpt_len)
        out: list[dict] = []
        for raw in scraps:
            if "body" in raw and "excerpt" not in raw:
                raise ForestError(
                    "recall.side: full body refused; provide excerpt or id for preview"
                )
            if "id" in raw and "jurisdiction" not in raw:
                row = self.get(int(raw["id"]))
                if row is None:
                    raise ForestError(f"recall.side: unknown entry {raw['id']}")
                scrap = _row_to_scrap(row, excerpt_len=bound)
            else:
                scrap = dict(raw)
                _require_jurisdiction(scrap)
                if "id" not in scrap:
                    raise ForestError("recall.side scrap needs id")
                if "excerpt" not in scrap:
                    row = self.get(int(scrap["id"]))
                    if row is not None:
                        scrap["excerpt"] = _row_to_scrap(
                            row, excerpt_len=bound
                        )["excerpt"]
                    else:
                        raise ForestError("recall.side scrap needs excerpt")
                scrap.pop("body", None)
            out.append(_require_jurisdiction(scrap))
        return out

    # -- trail (ephemeral tickets; receipts are not written) -------------------

    def open(self, handle: int) -> Trail:
        """Establish position at a bearing. Mints a ticket. No body disclosed."""
        row = self.get(handle)
        if row is None:
            raise ForestError(f"open: unknown entry {handle}")
        if self.is_sealed(handle):
            raise ForestError(f"open: entry {handle} is sealed")
        return self._mint_ticket(handle)

    def around(
        self,
        trail: Trail,
        *,
        excerpt_len: int = 160,
    ) -> list[dict]:
        """Bounded previews of lawful destinations from here.

        Each scrap includes:
        - jurisdiction, id, excerpt (bounded), bucket, signature
        - routes: list of {direction, relation} — one per distinct authored edge

        Disclosed routes are recorded on the ticket so ``step`` can verify them.
        Ceremony edges (adopts, supersedes, seals, unseals) are excluded.
        Full bodies are ``read``.
        """
        state = self._require_ticket(trail)
        bound = _require_excerpt_bound(excerpt_len)
        here = trail.position
        if self.get(here) is None:
            raise ForestError(f"around: unknown position {here}")
        rows = self.conn.execute(
            """
            SELECT e.*, g.kind AS edge_kind, g.from_id AS edge_from, g.to_id AS edge_to
            FROM edges g
            JOIN entries e ON e.id = CASE
                WHEN g.from_id = ? THEN g.to_id ELSE g.from_id END
            WHERE (g.from_id = ? OR g.to_id = ?)
              AND g.kind NOT IN ('adopts', 'supersedes', 'seals', 'unseals')
              AND e.id NOT IN (SELECT id FROM sealed_entries)
            ORDER BY e.id, g.kind
            """,
            (here, here, here),
        ).fetchall()
        by_id: dict[int, dict] = {}
        for row in rows:
            eid = int(row["id"])
            if eid == here:
                continue
            route = {
                "direction": _direction_for_edge(
                    row["edge_kind"], int(row["edge_from"]), here
                ),
                "relation": row["edge_kind"],
            }
            if eid not in by_id:
                scrap = _row_to_scrap(row, excerpt_len=bound)
                scrap["routes"] = [route]
                by_id[eid] = _require_jurisdiction(scrap)
            else:
                if route not in by_id[eid]["routes"]:
                    by_id[eid]["routes"].append(route)
        for scrap in by_id.values():
            for route in scrap["routes"]:
                state.disclosed.add((int(scrap["id"]), route["direction"]))
        return list(by_id.values())

    def step(
        self,
        trail: Trail,
        direction: str,
        *,
        target: int | None = None,
        signature: str = "system",
    ) -> Trail:
        """One boundary: in | out | next | prev — only along routes ``around`` disclosed.

        ``in`` requires ``target``. Other directions pick the unique destination
        or refuse ambiguity. Spends the old ticket; returns a new one.
        """
        del signature  # reserved for future attributed steps
        state = self._require_ticket(trail)
        if direction not in ("in", "out", "next", "prev"):
            raise ForestError("step: direction must be in|out|next|prev")
        if direction == "in" and target is None:
            raise ForestError(
                "step: inward requires target (name one destination from around)"
            )

        matching = [
            eid for eid, d in state.disclosed if d == direction
        ]
        # unique dest ids that have this direction
        matching = list(dict.fromkeys(matching))

        if not matching and not state.disclosed:
            raise ForestError(
                "step: no disclosed routes — call around() before step"
            )

        if direction == "in":
            if target not in matching:
                raise ForestError(
                    f"step: target {target} not reachable with direction 'in' "
                    f"from {trail.position} (disclose via around first)"
                )
            self._spend_ticket(trail)
            return self._mint_ticket(int(target))

        if target is not None:
            if target not in matching:
                raise ForestError(
                    f"step: target {target} not reachable with direction "
                    f"'{direction}' from {trail.position}"
                )
            self._spend_ticket(trail)
            return self._mint_ticket(int(target))

        if not matching:
            raise ForestError(f"step: no '{direction}' neighbor from {trail.position}")
        if len(matching) > 1:
            raise ForestError(
                f"step: ambiguous '{direction}' (multiple neighbors {matching}); "
                "specify target"
            )
        self._spend_ticket(trail)
        return self._mint_ticket(int(matching[0]))

    def read(self, trail: Trail) -> dict:
        """Disclose body at the ticket position. Wild reads pend cites on next pair."""
        self._require_ticket(trail)
        row = self.get(trail.position)
        if row is None:
            raise ForestError(f"read: unknown position {trail.position}")
        if self.is_sealed(trail.position):
            raise ForestError(f"read: entry {trail.position} is sealed")
        if row["jurisdiction"] == "wild":
            self._pending_wild_access.add(int(trail.position))
        return {
            "jurisdiction": row["jurisdiction"],
            "id": row["id"],
            "body": row["body"],
            "bucket": row["bucket"],
            "signature": row["signature"],
            "source": row["source"],
        }

    def move(
        self,
        trail: Trail,
        *,
        neighbor_id: int | None = None,
        deeper: tuple[int, int] | None = None,
        shallower: bool = False,
        signature: str = "system",
    ) -> Trail:
        """0.4 interim: neighbor via edges, deeper extract, or shallower to parent.

        Prefer ``step`` + ``around`` going forward. Requires a valid ticket;
        returns a new ticket at the destination.
        """
        self._require_ticket(trail)
        actions = [
            neighbor_id is not None,
            deeper is not None,
            shallower is True,
        ]
        if sum(actions) != 1:
            raise ForestError(
                "move: specify exactly one of neighbor_id, deeper, shallower"
            )

        here = trail.position
        parent = self.get(here)
        if parent is None:
            raise ForestError(f"move: unknown position {here}")

        if neighbor_id is not None:
            link = self.conn.execute(
                """
                SELECT 1 FROM edges
                WHERE ((from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?))
                  AND kind NOT IN ('adopts', 'supersedes', 'seals', 'unseals')
                """,
                (here, neighbor_id, neighbor_id, here),
            ).fetchone()
            if link is None:
                raise ForestError(
                    f"move: no edge between {here} and {neighbor_id}"
                )
            if self.get(neighbor_id) is None:
                raise ForestError(f"move: unknown neighbor {neighbor_id}")
            self._spend_ticket(trail)
            return self._mint_ticket(neighbor_id)

        if shallower:
            nest = self.conn.execute(
                """
                SELECT to_id FROM edges
                WHERE from_id = ? AND kind = 'nests'
                LIMIT 1
                """,
                (here,),
            ).fetchone()
            if nest is None:
                der = self.conn.execute(
                    """
                    SELECT to_id FROM edges
                    WHERE from_id = ? AND kind = 'derived_from'
                    LIMIT 1
                    """,
                    (here,),
                ).fetchone()
                if der is None:
                    raise ForestError(f"move: no parent above {here}")
                self._spend_ticket(trail)
                return self._mint_ticket(int(der["to_id"]))
            self._spend_ticket(trail)
            return self._mint_ticket(int(nest["to_id"]))

        assert deeper is not None
        start, end = deeper
        body = parent["body"]
        if start < 0 or end > len(body) or start >= end:
            raise ForestError("move: deeper slice out of range")
        extract = body[start:end]
        existing = self.conn.execute(
            """
            SELECT e.id FROM entries e
            JOIN edges n ON n.from_id = e.id AND n.kind = 'nests' AND n.to_id = ?
            WHERE e.body = ? AND e.meta_json LIKE ?
            """,
            (here, extract, f'%"start": {start}%'),
        ).fetchone()
        if existing:
            self._spend_ticket(trail)
            return self._mint_ticket(int(existing["id"]))
        child_id = self.write(
            body=extract,
            jurisdiction=parent["jurisdiction"],
            bucket="note",
            signature=signature,
            origins=[(here, "nests")],
            meta={"start": start, "end": end, "parent_id": here},
            scrub=None,
        )
        self._spend_ticket(trail)
        return self._mint_ticket(child_id)

    # -- ceremonies ------------------------------------------------------------

    def _root(
        self,
        *,
        entry_id: int,
        quote: str,
        adopting_signature: str,
        expected_body_hash: str,
    ) -> int:
        """Internal trail write. Public root path is ``root_to_ground`` only."""
        if not expected_body_hash or not str(expected_body_hash).strip():
            raise ForestError("root: expected_body_hash required")
        row = self.get(entry_id)
        if row is None:
            raise ForestError(f"root: unknown entry {entry_id}")
        if row["bucket"] in CEREMONY_BUCKETS:
            raise ForestError("root: cannot root a ceremony record")
        if self.is_sealed(entry_id):
            raise ForestError(
                f"root: entry {entry_id} is sealed; cannot root a sealed entry"
            )
        if self._is_superseded(entry_id):
            raise ForestError(
                f"root: entry {entry_id} is superseded; cannot root a superseded entry"
            )
        if self.is_ground(entry_id):
            raise ForestError(f"entry {entry_id} is already current ground")
        if not quote or not quote.strip():
            raise ForestError("root without adopting words refused")
        if not adopting_signature or not adopting_signature.strip():
            raise ForestError("root without a speaker signature refused")
        if row["body_hash"] != expected_body_hash:
            raise ForestError(
                f"root: body_hash mismatch for entry {entry_id} "
                f"(expected {expected_body_hash!r}, stored {row['body_hash']!r})"
            )
        with self.conn:
            record_id = self._insert_row(
                body=quote.strip(),
                jurisdiction="home",
                bucket="adoption_record",
                signature=adopting_signature.strip(),
                ceremony=True,
            )
            self._add_edge(record_id, entry_id, "adopts")
            if not self.is_ground(entry_id):
                raise ForestError(
                    f"root postcondition failed: entry {entry_id} did not become "
                    "ground after adoption record was written"
                )
        return record_id

    def supersede(
        self,
        *,
        old_id: int,
        new_body: str,
        adopting_words: str,
        adopting_signature: str = "author",
        signature: str = "author",
        bucket: str | None = None,
        scrub: ScrubFn | None = default_scrub,
    ) -> int:
        """Replace current ground with a new entry + adoption trail.

        new_body is scrubbed by default. The new entry cannot use a ceremony bucket.
        """
        if not self.is_ground(old_id):
            raise ForestError(
                f"entry {old_id} is not current ground; only ground can be superseded"
            )
        if not adopting_words or not adopting_words.strip():
            raise ForestError("supersession without adopting words refused")
        if scrub is not None:
            new_body = scrub(new_body)
        old = self.get(old_id)
        assert old is not None
        new_bucket = bucket or (
            old["bucket"] if old["bucket"] not in CEREMONY_BUCKETS else "note"
        )
        if new_bucket in CEREMONY_BUCKETS:
            raise ForestError(
                f"supersede: new body cannot use ceremony bucket {new_bucket!r}; "
                "use a regular content bucket"
            )
        with self.conn:
            new_id = self._insert_row(
                body=new_body,
                jurisdiction=old["jurisdiction"],
                bucket=new_bucket,
                signature=signature,
                source=old["source"],
            )
            self._add_edge(new_id, old_id, "supersedes")
            record_id = self._insert_row(
                body=adopting_words.strip(),
                jurisdiction="home",
                bucket="adoption_record",
                signature=adopting_signature,
                ceremony=True,
            )
            self._add_edge(record_id, new_id, "adopts")
        return new_id

    def seal(self, *, entry_id: int, quote: str, signature: str = "author") -> int:
        if self.is_sealed(entry_id):
            raise ForestError(f"entry {entry_id} is already sealed")
        with self.conn:
            record_id = self._insert_row(
                body=quote,
                jurisdiction="home",
                bucket="sealing_record",
                signature=signature,
                ceremony=True,
            )
            self._add_edge(record_id, entry_id, "seals")
        return record_id

    def unseal(self, *, entry_id: int, quote: str, signature: str = "author") -> int:
        if not self.is_sealed(entry_id):
            raise ForestError(f"entry {entry_id} is not sealed")
        with self.conn:
            record_id = self._insert_row(
                body=quote,
                jurisdiction="home",
                bucket="unsealing_record",
                signature=signature,
                ceremony=True,
            )
            self._add_edge(record_id, entry_id, "unseals")
        return record_id

    # -- walk_back -------------------------------------------------------------

    def walk_back(self, entry_id: int, *, adopting_signature: str) -> dict:
        """Gated audit of current ground → adoption → origins → scroll_ptr.

        Previews only — full bodies remain earned ``read`` via ticket.
        """
        if not adopting_signature or not adopting_signature.strip():
            raise ForestError("walk_back: adopting_signature required")
        if not self.is_ground(entry_id):
            raise ForestError(
                f"walk_back: entry {entry_id} is not current ground"
            )
        row = self.get(entry_id)
        if row is None:
            raise ForestError(f"walk_back: unknown entry {entry_id}")
        adoption = self.conn.execute(
            """
            SELECT r.* FROM edges a
            JOIN entries r ON r.id = a.from_id
            WHERE a.to_id = ? AND a.kind = 'adopts' AND r.bucket = 'adoption_record'
            ORDER BY a.id DESC LIMIT 1
            """,
            (entry_id,),
        ).fetchone()
        origins = list(
            self.conn.execute(
                """
                SELECT e.*, g.kind AS edge_kind
                FROM edges g
                JOIN entries e ON e.id = g.to_id
                WHERE g.from_id = ?
                ORDER BY g.id
                """,
                (entry_id,),
            )
        )
        meta = json.loads(row["meta_json"] or "{}")
        return {
            "entry": _row_to_scrap(row, excerpt_len=_AUDIT_EXCERPT),
            "is_ground": True,
            "adoption": (
                _row_to_scrap(adoption, excerpt_len=_AUDIT_EXCERPT)
                if adoption
                else None
            ),
            "origins": [
                {
                    **_row_to_scrap(o, excerpt_len=_AUDIT_EXCERPT),
                    "edge_kind": o["edge_kind"],
                }
                for o in origins
            ],
            "scroll_ptr": meta.get("scroll_ptr"),
            "audit_signature": adopting_signature.strip(),
        }
