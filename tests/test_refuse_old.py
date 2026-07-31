"""0.4 hard cut: fresh vs malformed schema; no migrate path."""

import sqlite3
from pathlib import Path

import pytest

from forest_memory import ForestError, ForestStore, hash_body

FIXTURE_V02 = Path(__file__).parent / "fixtures" / "schema_v02.sql"


def test_completely_empty_database_ok(tmp_path):
    path = tmp_path / "fresh.db"
    s = ForestStore(path)
    s.init_schema()
    assert s.conn.execute("SELECT value FROM forest_meta WHERE key='schema_version'").fetchone()[
        "value"
    ] == "0.4.0"
    s.close()


def test_valid_initialized_empty_ok(tmp_path):
    path = tmp_path / "empty04.db"
    with ForestStore(path) as s:
        s.init_schema()
    # Reopen with zero rows — must still pass version gate
    with ForestStore(path) as s:
        n = s.conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]
        assert n == 0


def test_pre04_store_refused(tmp_path):
    """A DB with `forest` (not `jurisdiction`) is refused on open."""
    old = tmp_path / "old.db"
    conn = sqlite3.connect(old)
    if FIXTURE_V02.exists():
        conn.executescript(FIXTURE_V02.read_text(encoding="utf-8"))
    else:
        conn.executescript(
            """
            CREATE TABLE entries (
              id INTEGER PRIMARY KEY,
              created_at TEXT NOT NULL,
              forest TEXT NOT NULL,
              bucket TEXT NOT NULL,
              signature TEXT NOT NULL,
              body TEXT NOT NULL,
              body_hash TEXT NOT NULL,
              meta_json TEXT NOT NULL DEFAULT '{}'
            );
            """
        )
        conn.execute(
            """
            INSERT INTO entries (created_at, forest, bucket, signature, body, body_hash)
            VALUES ('2026-01-01', 'home', 'session_pair', 'conversation', 'x', ?)
            """,
            (hash_body("x"),),
        )
    conn.commit()
    conn.close()

    with pytest.raises(ForestError, match="pre-0.4|hard cut"):
        ForestStore(old)


def test_old_empty_schema_refused(tmp_path):
    """Empty pre-0.4 entries table (zero rows) is still refused."""
    old = tmp_path / "old_empty.db"
    conn = sqlite3.connect(old)
    conn.executescript(
        """
        CREATE TABLE entries (
          id INTEGER PRIMARY KEY,
          forest TEXT NOT NULL,
          bucket TEXT NOT NULL,
          signature TEXT NOT NULL,
          body TEXT NOT NULL,
          body_hash TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()
    with pytest.raises(ForestError, match="pre-0.4|hard cut|jurisdiction"):
        ForestStore(old)


def test_partial_entries_table_refused(tmp_path):
    path = tmp_path / "partial.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY, body TEXT)")
    conn.commit()
    conn.close()
    with pytest.raises(ForestError, match="pre-0.4|jurisdiction|hard cut"):
        ForestStore(path)


def test_missing_forest_meta_refused_even_when_empty(tmp_path):
    path = tmp_path / "no_meta.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE entries (
          id INTEGER PRIMARY KEY,
          created_at TEXT NOT NULL DEFAULT '',
          jurisdiction TEXT NOT NULL,
          bucket TEXT NOT NULL,
          source TEXT,
          signature TEXT NOT NULL,
          body TEXT NOT NULL,
          body_hash TEXT NOT NULL,
          meta_json TEXT NOT NULL DEFAULT '{}'
        );
        """
    )
    conn.commit()
    conn.close()
    with pytest.raises(ForestError, match="forest_meta"):
        ForestStore(path)


def test_mismatched_schema_version_refused(tmp_path):
    path = tmp_path / "bad_ver.db"
    with ForestStore(path) as s:
        s.init_schema()
    conn = sqlite3.connect(path)
    conn.execute(
        "UPDATE forest_meta SET value='0.3.0' WHERE key='schema_version'"
    )
    conn.commit()
    conn.close()
    with pytest.raises(ForestError, match="schema_version"):
        ForestStore(path)


def test_init_schema_does_not_bless_unknown_skeleton(tmp_path):
    """Opening a partial skeleton fails before init_schema can run."""
    path = tmp_path / "skeleton.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE entries (id INTEGER PRIMARY KEY, jurisdiction TEXT, body TEXT)"
    )
    conn.commit()
    conn.close()
    with pytest.raises(ForestError):
        ForestStore(path)
