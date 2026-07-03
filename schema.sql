-- Forest constitution — canonical schema (v0.1).
-- Append-only. Signatures and ancestry required at insert.
-- Packaged copy: src/forest_memory/schema.sql (keep in sync).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS entries (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  forest TEXT NOT NULL CHECK (forest IN ('home','wild')),
  bucket TEXT NOT NULL CHECK (bucket IN (
    'session_pair','draft','canon','superseded_canon','visitor_words','note',
    'hearsay','synthesis','inference','question','adoption_record','sealing_record','import'
  )),
  signature TEXT NOT NULL CHECK (length(trim(signature)) > 0),
  authority TEXT NOT NULL CHECK (authority IN ('ground','model','inference','draft','stranger','hearsay','record')),
  visibility TEXT NOT NULL DEFAULT 'open' CHECK (visibility IN ('open','hidden','deep','sealed')),
  superseded_by INTEGER REFERENCES entries(id),
  body TEXT NOT NULL CHECK (length(body) > 0),
  body_hash TEXT NOT NULL,
  meta_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS edges (
  id INTEGER PRIMARY KEY,
  from_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE RESTRICT,
  to_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE RESTRICT,
  kind TEXT NOT NULL CHECK (kind IN (
    'spoken_in','responds_to','derived_from','adopts','supersedes','cites','seals','unseals'
  )),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (from_id, to_id, kind)
);

CREATE TABLE IF NOT EXISTS retrieval_log (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  query TEXT NOT NULL,
  open_buckets_json TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT ''
);

CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
  body,
  content='entries',
  content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
  INSERT INTO entries_fts(rowid, body)
  SELECT NEW.id, NEW.body
  WHERE NEW.visibility != 'sealed';
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
  INSERT INTO entries_fts(entries_fts, rowid, body) VALUES('delete', OLD.id, OLD.body);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE OF visibility ON entries BEGIN
  INSERT INTO entries_fts(entries_fts, rowid, body) VALUES('delete', OLD.id, OLD.body);
  INSERT INTO entries_fts(rowid, body)
  SELECT NEW.id, NEW.body
  WHERE NEW.visibility != 'sealed';
END;

CREATE TRIGGER IF NOT EXISTS prevent_body_rewrite
BEFORE UPDATE OF body ON entries
BEGIN
  SELECT RAISE(ABORT, 'entries are append-only; body rewrite refused');
END;

CREATE VIEW IF NOT EXISTS retrievable_entries AS
SELECT * FROM entries
WHERE visibility != 'sealed';

CREATE VIEW IF NOT EXISTS current_ground AS
SELECT * FROM entries
WHERE authority = 'ground'
  AND superseded_by IS NULL
  AND visibility = 'open';

CREATE INDEX IF NOT EXISTS idx_entries_bucket ON entries(bucket);
CREATE INDEX IF NOT EXISTS idx_entries_forest ON entries(forest);
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id);
