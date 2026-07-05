-- =============================================================================
-- Forest constitution — reference schema (v0.2)
-- =============================================================================
--
-- This file is the enforced law. Read FOREST.md for rationale.
-- Packaged copy (must match byte-for-byte): src/forest_memory/schema.sql
--
-- v0.2 architectural rule: STATUS IS DERIVED, NEVER STORED.
-- v0.1 kept authority/visibility/superseded_by as mutable columns; a single
-- UPDATE could forge ground. In v0.2 an entry's status is a conclusion drawn
-- from the append-only record trail:
--   - ground      := an adoption_record has an `adopts` edge to the entry,
--                    and nothing supersedes it, and it is not sealed
--   - superseded  := a `supersedes` edge points at it
--   - sealed      := the latest seals/unseals edge pointing at it is `seals`
-- There is nothing to flip. Forging status requires inserting a record —
-- which IS the ceremony.
--
-- Enforced in this file:
--   - closed vocabularies (forest, bucket, edge kind)
--   - non-empty signature and body; body_hash format (64 lowercase hex)
--   - entries and edges fully immutable: every UPDATE and DELETE refused
--   - seal/unseal state guards (double-seal and stray unseal refused)
--   - FTS shadow: sealing removes the body from the index, unsealing restores
--   - derived views: current_ground, sealed_entries, retrievable_entries
--
-- Application layer (your insert wrapper must enforce):
--   - ancestry: non-session_pair entries require at least one origin edge
--   - body_hash: SHA-256 of body at insert (SQLite cannot compute it)
--   - ceremony buckets (canon, *_record) and ceremony edge kinds
--     (adopts, supersedes, seals, unseals) written only by ceremonies
--   - retrieval_log writes on every search, including result ids
--   - promotion gates (praise ≠ adoption, verbatim author prose)
--
-- Threat model (be honest about it):
--   Triggers defend against buggy or confused APPLICATION CODE — the failure
--   mode that actually corrupts memory stores. They do not defend against an
--   adversary holding write access to the database file: whoever can run
--   UPDATE can also run DROP TRIGGER. If you need protection against a
--   hostile writer, put the file behind an authenticating service boundary.
--
-- Known gaps (v0.2):
--   - body_hash format is checked here; its correctness (hash actually
--     matches body) is checked by the wrapper, not by SQLite
--   - speaker authentication for adoption quotes is the host application's
--     responsibility; the store records the claimed signature verbatim
--
-- Hostile test matrix: tests/HOSTILE_CASES.md
-- =============================================================================

PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------------
-- entries — every stored unit of text. Immutable facts about the text AT BIRTH.
-- Status (ground / superseded / sealed) is never a column; see views below.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS entries (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),

  -- Jurisdiction: home (produced inside) or wild (imported)
  forest TEXT NOT NULL CHECK (forest IN ('home','wild')),

  -- Entry kind at birth — scopes retrieval; see FOREST.md §3.
  -- canon, adoption_record, sealing_record, unsealing_record are ceremony
  -- buckets: the wrapper refuses them at the front door.
  bucket TEXT NOT NULL CHECK (bucket IN (
    'session_pair',      -- conversation root (may have no origin edge)
    'draft',             -- proposed text, not adopted
    'canon',             -- born through adoption or supersession ceremony
    'visitor_words',     -- external speaker in session
    'note',              -- freeform home-wood note
    'hearsay',           -- wild-wood source claim
    'synthesis',         -- model combination of sources
    'inference',         -- model possibility, not ground
    'question',          -- open question (host layer may use)
    'adoption_record',   -- authority-holder adoption act
    'sealing_record',    -- authority-holder sealing act
    'unsealing_record',  -- authority-holder unsealing act
    'import'             -- imported document passage
  )),

  -- Who produced the text (non-empty); custody fact, not status
  signature TEXT NOT NULL CHECK (length(trim(signature)) > 0),

  body TEXT NOT NULL CHECK (length(body) > 0),

  -- SHA-256(hex, lowercase) of body at insert; app must compute and verify
  body_hash TEXT NOT NULL CHECK (
    length(body_hash) = 64 AND body_hash NOT GLOB '*[^0-9a-f]*'
  ),

  meta_json TEXT NOT NULL DEFAULT '{}'  -- source_path, source_uri, etc.
);

-- -----------------------------------------------------------------------------
-- edges — ancestry, relations, and ceremony acts. Also immutable.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS edges (
  id INTEGER PRIMARY KEY,
  from_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE RESTRICT,
  to_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE RESTRICT,

  kind TEXT NOT NULL CHECK (kind IN (
    'spoken_in',    -- entry arose in this conversation pair
    'responds_to',  -- pair follows prior pair
    'derived_from', -- synthesis/inference/canon derived from source
    'adopts',       -- adoption record -> the entry that becomes ground
    'supersedes',   -- new entry -> old entry
    'cites',        -- claim -> source/import
    'seals',        -- sealing record -> sealed entry
    'unseals',      -- unsealing record -> unsealed entry
    'asks_about',   -- question -> entry it grew next to (mycelium)
    'feeds',        -- entry -> question it nourishes (mycelium)
    'answers',      -- entry -> question it answers (mycelium; never promotes)
    'reopens'       -- entry -> question it reopens (mycelium)
  )),

  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (from_id, to_id, kind)
);

-- -----------------------------------------------------------------------------
-- retrieval_log — every search scope AND result set is recorded
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS retrieval_log (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  query TEXT NOT NULL,
  open_buckets_json TEXT NOT NULL,          -- JSON array of bucket names in scope
  result_ids_json TEXT NOT NULL DEFAULT '[]', -- JSON array of entry ids returned
  note TEXT NOT NULL DEFAULT ''
);

-- -----------------------------------------------------------------------------
-- Append-only guarantee — entries and edges are fully immutable rows.
-- Revision is supersession; removal is sealing. Never UPDATE, never DELETE.
-- -----------------------------------------------------------------------------
CREATE TRIGGER IF NOT EXISTS prevent_entry_update
BEFORE UPDATE ON entries
BEGIN
  SELECT RAISE(ABORT, 'entries are append-only; update refused (supersede or seal instead)');
END;

CREATE TRIGGER IF NOT EXISTS prevent_entry_delete
BEFORE DELETE ON entries
BEGIN
  SELECT RAISE(ABORT, 'entries are append-only; delete refused');
END;

CREATE TRIGGER IF NOT EXISTS prevent_edge_update
BEFORE UPDATE ON edges
BEGIN
  SELECT RAISE(ABORT, 'edges are append-only; update refused');
END;

CREATE TRIGGER IF NOT EXISTS prevent_edge_delete
BEFORE DELETE ON edges
BEGIN
  SELECT RAISE(ABORT, 'edges are append-only; delete refused');
END;

-- -----------------------------------------------------------------------------
-- Seal state guards — the seal/unseal trail must alternate. This keeps the
-- derived sealed status unambiguous and protects the FTS shadow below.
-- -----------------------------------------------------------------------------
CREATE TRIGGER IF NOT EXISTS seal_state_guard
BEFORE INSERT ON edges
WHEN NEW.kind = 'seals' AND (
  SELECT kind FROM edges
  WHERE to_id = NEW.to_id AND kind IN ('seals','unseals')
  ORDER BY id DESC LIMIT 1
) = 'seals'
BEGIN
  SELECT RAISE(ABORT, 'entry already sealed');
END;

CREATE TRIGGER IF NOT EXISTS unseal_state_guard
BEFORE INSERT ON edges
WHEN NEW.kind = 'unseals' AND COALESCE((
  SELECT kind FROM edges
  WHERE to_id = NEW.to_id AND kind IN ('seals','unseals')
  ORDER BY id DESC LIMIT 1
), 'unseals') = 'unseals'
BEGIN
  SELECT RAISE(ABORT, 'entry is not sealed');
END;

-- -----------------------------------------------------------------------------
-- FTS5 — keyword search over entry bodies.
-- Sealed bodies are removed from the index by the sealing ceremony itself
-- (the seals edge insert), not by a query-time filter: the index must not
-- contain sealed text at all. Unsealing restores it.
-- -----------------------------------------------------------------------------
CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
  body,
  content='entries',
  content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS entries_fts_ai AFTER INSERT ON entries BEGIN
  INSERT INTO entries_fts(rowid, body) VALUES (NEW.id, NEW.body);
END;

CREATE TRIGGER IF NOT EXISTS edges_seal_fts AFTER INSERT ON edges
WHEN NEW.kind = 'seals'
BEGIN
  INSERT INTO entries_fts(entries_fts, rowid, body)
  SELECT 'delete', e.id, e.body FROM entries e WHERE e.id = NEW.to_id;
END;

CREATE TRIGGER IF NOT EXISTS edges_unseal_fts AFTER INSERT ON edges
WHEN NEW.kind = 'unseals'
BEGIN
  INSERT INTO entries_fts(rowid, body)
  SELECT e.id, e.body FROM entries e WHERE e.id = NEW.to_id;
END;

-- -----------------------------------------------------------------------------
-- Derived-status views — the only lawful way to read status.
-- -----------------------------------------------------------------------------

-- Sealed iff the latest seals/unseals edge pointing at the entry is `seals`.
-- Recency is edge id (monotonic in SQLite), not created_at (can tie).
CREATE VIEW IF NOT EXISTS sealed_entries AS
SELECT e.* FROM entries e
WHERE (
  SELECT g.kind FROM edges g
  WHERE g.to_id = e.id AND g.kind IN ('seals','unseals')
  ORDER BY g.id DESC LIMIT 1
) = 'seals';

-- Everything not sealed.
CREATE VIEW IF NOT EXISTS retrievable_entries AS
SELECT e.* FROM entries e
WHERE e.id NOT IN (SELECT id FROM sealed_entries);

-- Authoritative current ground: adopted by ceremony, not superseded, not sealed.
CREATE VIEW IF NOT EXISTS current_ground AS
SELECT e.* FROM entries e
WHERE EXISTS (
    SELECT 1 FROM edges a
    JOIN entries r ON r.id = a.from_id
    WHERE a.to_id = e.id AND a.kind = 'adopts' AND r.bucket = 'adoption_record'
  )
  AND NOT EXISTS (
    SELECT 1 FROM edges s WHERE s.to_id = e.id AND s.kind = 'supersedes'
  )
  AND e.id NOT IN (SELECT id FROM sealed_entries);

-- -----------------------------------------------------------------------------
-- Indexes
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_entries_bucket ON entries(bucket);
CREATE INDEX IF NOT EXISTS idx_entries_forest ON entries(forest);
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id);
CREATE INDEX IF NOT EXISTS idx_edges_to_kind ON edges(to_id, kind);
