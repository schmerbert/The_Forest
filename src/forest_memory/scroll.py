# scroll — append-only session file for exact API turns (head at the end).
#
# Stores: JSONL framed records on disk; never a SQLite table
# Refuses: rewriting prior turns; dumping the whole scroll as "context";
#          oversized slices (> MAX_SLICE bytes); any range covering the
#          entire non-empty file
# Returns: append offset; optional tail/slice reads; record_count
# Test: tests/test_scroll.py

from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path

MAX_SLICE = 8192  # maximum bytes readable via read_slice


class ScrollError(Exception):
    """Raised when scroll discipline is violated."""


class Scroll:
    """One append-only file per session: exact API turns stored as JSONL records.

    Each record is one UTF-8 line:
        {"v":1,"ts":ISO,"hash":sha256_hex,"n":byte_len,"payload":str}

    ``head`` is the current turn's exact API context — append it; do not ask
    Forest to load the whole scroll into a model context.

    dump_all() is refused by design.
    read_slice() is capped at MAX_SLICE bytes and refuses any range that
    covers the entire non-empty file. Prefer tail() for recent context.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.parent.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def _make_record(self, payload: str) -> bytes:
        payload_bytes = payload.encode("utf-8")
        record = {
            "v": 1,
            "ts": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            )
            + "Z",
            "hash": hashlib.sha256(payload_bytes).hexdigest(),
            "n": len(payload_bytes),
            "payload": payload,
        }
        return (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")

    def append(self, head: str) -> int:
        """Append one turn as a JSONL record. Returns byte offset of that record."""
        if not head:
            raise ScrollError("empty head refused")
        record_bytes = self._make_record(head)
        with self.path.open("ab") as f:
            offset = f.tell()
            f.write(record_bytes)
        return offset

    def size(self) -> int:
        return self.path.stat().st_size

    def record_count(self) -> int:
        """Count JSONL records in the scroll (streaming; does not buffer the file)."""
        if self.size() == 0:
            return 0
        n = 0
        with self.path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.strip():
                    n += 1
        return n

    def read_slice(self, start: int, end: int) -> str:
        """Read a byte range. Both start and end are required.

        Refuses slices larger than MAX_SLICE bytes. Refuses any range that
        covers the entire non-empty scroll (use tail() for recent context).
        Use the byte offsets returned by append() to navigate.
        """
        file_size = self.size()
        if start < 0 or start > file_size:
            raise ScrollError("slice start out of range")
        if end < start or end > file_size:
            raise ScrollError("slice end out of range")
        size = end - start
        if file_size > 0 and start == 0 and end == file_size:
            raise ScrollError(
                "reading the complete scroll is refused; "
                "use tail() for recent context or navigate with append offsets"
            )
        if size > MAX_SLICE:
            raise ScrollError(
                f"slice too large ({size} bytes > MAX_SLICE={MAX_SLICE}); "
                "use tail() for recent context or navigate with append offsets"
            )
        with self.path.open("rb") as f:
            f.seek(start)
            data = f.read(size)
        return data.decode("utf-8")

    def tail(self, max_bytes: int = 4096) -> str:
        """Recent end of the scroll only — not a dump of history.

        Backs up to a valid UTF-8 character boundary so multibyte sequences
        are never split. When the file is shorter than max_bytes, the tip
        may equal the whole file (size-bounded recent context, not a dump API).
        """
        if max_bytes <= 0:
            raise ScrollError("max_bytes must be positive")
        file_size = self.size()
        if file_size == 0:
            return ""
        with self.path.open("rb") as f:
            if file_size <= max_bytes:
                return f.read().decode("utf-8")
            f.seek(file_size - max_bytes)
            chunk = f.read(max_bytes)
        # Back up past any UTF-8 continuation bytes (0x80–0xBF) at the start.
        i = 0
        while i < len(chunk) and (chunk[i] & 0xC0) == 0x80:
            i += 1
        return chunk[i:].decode("utf-8")

    def dump_all(self) -> str:
        """Refused by design — never dump the whole scroll into context."""
        raise ScrollError(
            "dumping the whole scroll into context is refused; use tail() or a bounded read_slice()"
        )
