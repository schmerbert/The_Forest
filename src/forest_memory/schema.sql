-- =============================================================================
-- Forest constitution — reference schema (v0.1)
-- =============================================================================
--
-- This file is the enforced law. Read FOREST.md for rationale.
-- Packaged copy (must match byte-for-byte): src/forest_memory/schema.sql
--
-- Enforced in this file:
--   - closed vocabularies (forest, bucket, authority, visibility, edge kind)
--   - non-empty signature and body
--   - append-only entry bodies (UPDATE body refused)
--   - append-only entries and edges (DELETE refused)
--   - sealed entries excluded from FTS at index time
--   - current_ground and retrievable_entries views
--
-- Application layer (your insert wrapper must enforce):
--   - ancestry: non-session_pair entries require at least one origin edge
--   - body_hash: SHA-256 of body at insert (column is not auto-computed)
--   - adoption / supersession / sealing ceremonies
--   - retrieval_log writes on every search
--   - promotion gates (praise ≠ adoption, verbatim author prose)
--
-- Known gaps (v0.1):
--   - hidden/deep visibility values exist but only sealed is excluded from FTS
--   - superseded canon may still appear in keyword search (use current_ground view)
--
-- Hostile test matrix: tests/HOSTILE_CASES.md
-- =============================================================================

PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------------
-- entries — every stored unit of text
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS entries (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),

  -- Jurisdiction: home (produced inside) or wild (imported)
  forest TEXT NOT NULL CHECK (forest IN ('home','wild')),

  -- Entry kind — scopes retrieval; see FOREST.md §3
  bucket TEXT NOT NULL CHECK (bucket IN (
    'session_pair',      -- conversation root (may have no origin edge)
    'draft',             -- proposed text, not adopted
    'canon',             -- adopted ground
    'superseded_canon',  -- former ground, retained for history
    'visitor_words',     -- external speaker in session
    'note',              -- freeform home-wood note
    'hearsay',           -- wild-wood source claim
    'synthesis',         -- model combination of sources
    'inference',         -- model possibility, not ground
    'question',          -- open question (host layer may use)
    'adoption_record',   -- authority-holder adoption act
    'sealing_record',    -- authority-holder sealing act
    'import'             -- imported document passage
  )),

  -- Who produced the text (non-empty); not the same as authority
  signature TEXT NOT NULL CHECK (length(trim(signature)) > 0),

  -- What the entry is allowed to mean downstream
  authority TEXT NOT NULL CHECK (authority IN (
    'ground',     -- accepted authority-holder truth
    'model',      -- model-produced
    'inference',  -- derived possibility
    'draft',      -- proposed, not adopted
    'stranger',   -- visitor words
    'hearsay',    -- source claim
    'record'      -- procedural record (adoption, sealing)
  )),

  -- open | hidden | deep | sealed — only sealed is enforced in FTS (v0.1)
  visibility TEXT NOT NULL DEFAULT 'open' CHECK (visibility IN (
    'open', 'hidden', 'deep', 'sealed'
  )),

  -- Set when this entry was superseded; NULL means still current for its bucket
  superseded_by INTEGER REFERENCES entries(id),

  body TEXT NOT NULL CHECK (length(body) > 0),
  body_hash TEXT NOT NULL,   -- SHA-256(hex) of body at insert; app must compute
  meta_json TEXT NOT NULL DEFAULT '{}'  -- source_path, source_uri, etc.
);

-- -----------------------------------------------------------------------------
-- edges — ancestry and relations between entries
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS edges (
  id INTEGER PRIMARY KEY,
  from_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE RESTRICT,
  to_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE RESTRICT,

  kind TEXT NOT NULL CHECK (kind IN (
    'spoken_in',    -- entry arose in this conversation pair
    'responds_to',  -- pair follows prior pair
    'derived_from', -- synthesis/inference/canon derived from source
    'adopts',       -- adoption record -> adopted entry
    'supersedes',   -- new entry -> old entry
    'cites',        -- claim -> source/import
    'seals',        -- sealing record -> sealed entry
    'unseals'       -- unsealing record -> unsealed entry
  )),

  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (from_id, to_id, kind)
);

-- -----------------------------------------------------------------------------
-- retrieval_log — every search scope is recorded (constitutional audit trail)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS retrieval_log (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  query TEXT NOT NULL,
  open_buckets_json TEXT NOT NULL,  -- JSON array of bucket names in scope
  note TEXT NOT NULL DEFAULT ''
);

-- -----------------------------------------------------------------------------
-- FTS5 — keyword search over entry bodies
-- Sealed entries are excluded at index time, not only at query time.
-- -----------------------------------------------------------------------------
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

-- -----------------------------------------------------------------------------
-- Append-only guarantee — body rewrite and deletes refused; use supersession
-- -----------------------------------------------------------------------------
CREATE TRIGGER IF NOT EXISTS prevent_body_rewrite
BEFORE UPDATE OF body ON entries
BEGIN
  SELECT RAISE(ABORT, 'entries are append-only; body rewrite refused');
END;

CREATE TRIGGER IF NOT EXISTS prevent_entry_delete
BEFORE DELETE ON entries
BEGIN
  SELECT RAISE(ABORT, 'entries are append-only; delete refused');
END;

CREATE TRIGGER IF NOT EXISTS prevent_edge_delete
BEFORE DELETE ON edges
BEGIN
  SELECT RAISE(ABORT, 'edges are append-only; delete refused');
END;

-- -----------------------------------------------------------------------------
-- Views
-- -----------------------------------------------------------------------------
-- All non-sealed entries (hidden/deep still included in v0.1)
CREATE VIEW IF NOT EXISTS retrievable_entries AS
SELECT * FROM entries
WHERE visibility != 'sealed';

-- Authoritative current ground only — use this for truth, not raw search hits
CREATE VIEW IF NOT EXISTS current_ground AS
SELECT * FROM entries
WHERE authority = 'ground'
  AND superseded_by IS NULL
  AND visibility = 'open';

-- -----------------------------------------------------------------------------
-- Indexes
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_entries_bucket ON entries(bucket);
CREATE INDEX IF NOT EXISTS idx_entries_forest ON entries(forest);
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id);
