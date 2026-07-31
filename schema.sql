-- =============================================================================
-- Forest constitution — reference schema (v0.4)
-- =============================================================================
--
-- This file is the enforced law. Read FOREST.md for rationale; ops contract
-- is README.md. Packaged copy (must match byte-for-byte):
--   src/forest_memory/schema.sql
--
-- STATUS IS DERIVED, NEVER STORED.
--   - ground      := an adoption_record has an `adopts` edge to the entry,
--                    nothing supersedes it, and it is not sealed
--   - superseded  := a `supersedes` edge points at it
--   - sealed      := the latest seals/unseals edge pointing at it is `seals`
-- Root is in-place: the authority act adopts the existing entry (no canon mint).
-- Root is optional: a Forest with no ground rows is complete.
--
-- Enforced in this file:
--   - closed vocabularies (jurisdiction, bucket, edge kind)
--   - non-empty signature and body; body_hash format (64 lowercase hex)
--   - entries and edges fully immutable: every UPDATE and DELETE refused
--   - seal/unseal state guards; FTS shadow on seal/unseal
--   - derived views: current_ground, sealed_entries, retrievable_entries
--
-- Application layer (wrapper must enforce):
--   - ancestry: non-pair entries require at least one origin edge
--   - body_hash: SHA-256 of body at insert
--   - ceremony buckets (*_record) and ceremony edge kinds only via ceremonies
--   - retrieval_log on every recall_similar
--   - jurisdiction-first recall packets; promotion gates (praise ≠ root)
--
-- Hostile test matrix: tests/HOSTILE_CASES.md
-- =============================================================================

PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------------
-- entries — immutable facts about the text AT BIRTH.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS entries (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),

  -- Jurisdiction: home (produced here) or wild (brought in)
  jurisdiction TEXT NOT NULL CHECK (jurisdiction IN ('home','wild')),

  -- Entry kind at birth. Ceremony buckets: adoption/sealing/unsealing_record.
  bucket TEXT NOT NULL CHECK (bucket IN (
    'pair',              -- conversation heartbeat (may have no origin edge)
    'draft',
    'visitor_words',
    'note',
    'journal',
    'hearsay',
    'synthesis',
    'inference',
    'question',          -- optional; Forest is complete without any
    'internet',
    'import',
    'adoption_record',
    'sealing_record',
    'unsealing_record'
  )),

  -- Optional provenance beside bucket (e.g. arxiv, url host)
  source TEXT,

  signature TEXT NOT NULL CHECK (length(trim(signature)) > 0),
  body TEXT NOT NULL CHECK (length(body) > 0),
  body_hash TEXT NOT NULL CHECK (
    length(body_hash) = 64 AND body_hash NOT GLOB '*[^0-9a-f]*'
  ),
  meta_json TEXT NOT NULL DEFAULT '{}'
);

-- -----------------------------------------------------------------------------
-- edges — ancestry, relations, and ceremony acts. Immutable.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS edges (
  id INTEGER PRIMARY KEY,
  from_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE RESTRICT,
  to_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE RESTRICT,

  kind TEXT NOT NULL CHECK (kind IN (
    'spoken_in',
    'responds_to',
    'derived_from',
    'adopts',
    'supersedes',
    'cites',
    'seals',
    'unseals',
    'asks_about',
    'feeds',
    'answers',
    'reopens',
    'nests'          -- child extract -> parent (nesting dolls)
  )),

  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (from_id, to_id, kind)
);

-- -----------------------------------------------------------------------------
-- retrieval_log — every recall_similar scope AND result set
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS retrieval_log (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  query TEXT NOT NULL,
  open_buckets_json TEXT NOT NULL,
  result_ids_json TEXT NOT NULL DEFAULT '[]',
  note TEXT NOT NULL DEFAULT ''
);

-- -----------------------------------------------------------------------------
-- Append-only guarantee
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
-- Seal state guards
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
-- FTS5 — sealed bodies removed from the index by the seals edge trigger
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
-- Derived-status views
-- -----------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS sealed_entries AS
SELECT e.* FROM entries e
WHERE (
  SELECT g.kind FROM edges g
  WHERE g.to_id = e.id AND g.kind IN ('seals','unseals')
  ORDER BY g.id DESC LIMIT 1
) = 'seals';

CREATE VIEW IF NOT EXISTS retrievable_entries AS
SELECT e.* FROM entries e
WHERE e.id NOT IN (SELECT id FROM sealed_entries);

-- Current ground: rooted in place (any bucket), not superseded, not sealed.
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
CREATE INDEX IF NOT EXISTS idx_entries_jurisdiction ON entries(jurisdiction);
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id);
CREATE INDEX IF NOT EXISTS idx_edges_to_kind ON edges(to_id, kind);

-- -----------------------------------------------------------------------------
-- forest_meta — schema version tracking (required in 0.4.0+)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS forest_meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
INSERT OR IGNORE INTO forest_meta(key, value) VALUES ('schema_version', '0.4.0');
