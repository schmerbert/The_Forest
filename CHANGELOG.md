# Changelog

All notable changes to the Forest constitution and reference wrapper.

## [Unreleased]

### Docs

- README: authority lifecycle diagram, SQL-not-enough warning, softer public phrasing
- FOREST.md: document whole-file drift limitation (§9); tighten adoption checklist
- `drift.check_file_drift` docstring: whole-file v0.1 scope

## [0.1.0] — 2026-07-03

### Constitution (`schema.sql`)

- CHECK constraints on `forest`, `bucket`, `authority`, `visibility`, edge `kind`
- `body_hash` on every entry (SHA-256 at insert)
- `meta_json` on entries
- Reworked `edges`: `id` PK, `created_at`, `UNIQUE(from_id, to_id, kind)`
- `retrieval_log` table
- `prevent_body_rewrite`, `prevent_entry_delete`, and `prevent_edge_delete` triggers — append-only as DB guarantee
- FTS triggers exclude `sealed` at index time
- `retrievable_entries` and `current_ground` views
- Btree indexes on bucket, forest, edge endpoints

### Reference wrapper (`forest_memory`)

- `ForestStore` — insert, pair roots, adopt, supersede, seal, search
- `ceremony.adopt_to_ground` — praise ≠ adoption, verbatim author prose
- `drift.check_file_drift` — file vs adoption `body_hash`
- Packaged `schema.sql` for `pip install`
- 17 hostile tests across constitutional, ceremony, and drift layers

### Docs

- `FOREST.md` — standalone constitution
- `README.md` — release-facing overview
- `tests/HOSTILE_CASES.md` — constitutional vs ceremonial split

### Release infrastructure

- GitHub Actions CI (Python 3.10–3.13, Ubuntu + Windows)
- Tag-triggered release workflow (GitHub Release with auto-generated notes)
- `RELEASING.md`, `CONTRIBUTING.md`, `SECURITY.md`
- `ForestStore.close()` and context-manager support
