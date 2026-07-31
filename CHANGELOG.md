# Changelog

All notable changes to the Forest constitution and reference wrapper.

## [0.4.0] — 2026-07-31

### Hard cut to clinical harness surface + custody truth hardening

Breaking rewrite so the shipped package matches the README ops contract.

- **Ops:** `write` / `write_pair` / `commit_turn`, `recall_similar` / `recall_side`, `open` / `around` / `step` / `read`, interim `move`, `root_to_ground`, gated `walk_back`; framed JSONL `Scroll` (`dump_all` + oversized / complete-file slice refused)
- **Preview ≠ read:** recall/around return bounded excerpts only; full body is `read`
- **Walk tickets:** `open` mints an opaque ticket; `around` discloses routes onto it; `step` spends and remints; `read` requires a valid ticket — forged positions refused
- **Scroll ↔ pair:** `write_pair` requires `scroll_ptr`; `commit_turn` is the canonical heartbeat
- **Access cites:** earned wild `read` pends `cites` onto the next pair
- **Root:** only `root_to_ground` is public (`ForestStore._root` internal); `expected_body_hash` required; refuses sealed/superseded; postcondition must be current ground
- **walk_back:** current ground + adopting_signature; audit previews + `scroll_ptr` only
- **Safe FTS:** Unicode-aware plain-language tokenization; `ForestError` not raw SQLite
- **Schema guard:** any existing `entries` table requires `forest_meta` 0.4.0 (empty rows included)
- **Mutations:** `add_edge` commits; supersede goes through scrub + ceremony bucket guards
- **Schema:** `forest_meta.schema_version = 0.4.0`
- Soft `near` named in the README; not shipped
- **Docs:** ops contract lives in `README.md` (former `docs/MAP.md` retired)
- **Removed:** MCP integration (`integrations/mcp`); `insert_entry` / `insert_pair` / `search` / `adopt` mint-canon / `migrate_*` / public `ForestStore.root`

## [0.3.1] — 2026-07-06

No code changes. First release published to PyPI as `forest-custody-memory`.

- README restructured library-first: `pip install` as the primary path,
  spec-copying moved to its own section for porters
- New README sections: positioning ("Why not Mem0 / Letta / MemGPT?") and
  the v0.1 audit story ("The audit that changed the schema")
- Related projects linked (The Inn, TheMarble)
- Release workflow now builds sdist + wheel, attaches them to the GitHub
  Release, and publishes to PyPI via trusted publishing (gated on the
  `pypi` environment); RELEASING.md updated to match

## [0.3.0] — 2026-07-05

### Mycelium — questions fruit next to the nodes a search disturbs

Questions are mycelium: an underground network attached to the entries it
grew from. New host-layer module `forest_memory.mycelium`:

- `plant_question` — a question grows next to specific material (`asks_about` edges); it is never a root
- `feed_question` — later entries nourish a question (`feeds`); each feed is ripeness
- `fruits_near(store, entry_ids)` — the fruiting mechanic: given the ids a search returned (or any nodes being read), the open questions attached to them surface alongside, ripest first. Questions never appear in FTS retrieval on their own; sealed questions do not fruit
- `answer_question` / `reopen_question` / `is_open` — question state is derived, never stored, same idiom as sealing: the latest `answers`/`reopens` edge wins
- **Answering never promotes.** If an answer deserves ground, the authority-holder adopts it through the ceremony like any other text

### Constitution (`schema.sql`) — breaking

- Edge-kind vocabulary widened: `asks_about`, `feeds`, `answers`, `reopens`.
  The vocabulary is a CHECK baked into the edges table, so **v0.2 stores
  need `forest_memory.migrate.migrate_v02_to_v03(old_path, new_path)`** — a
  straight copy (ids and timestamps preserved, old file never written) into
  the widened schema. The closed vocabulary caught this addition exactly as
  designed: unknown edge kinds are refused at the SQL layer.

### Also

- Drift check on migrated v0.1 stores compares against the ground entry's
  hash (a migrated adoption record carries two `adopts` edges; the latest is
  the ground edge)
- v0.1 stores are refused on open with a pointer to `migrate_v01_to_v02`
- A test enforces the two `schema.sql` copies stay byte-identical

## [0.2.0] — 2026-07-05

### Security — the v0.1 promotion boundary did not hold

An external audit defeated the v0.1 promotion boundary seven ways while all
seventeen hostile tests passed. Root cause: entry status (`authority`,
`visibility`, `superseded_by`) was stored in **mutable columns**. Direct
writes — `insert_entry(authority="ground")`, `UPDATE entries SET
authority='ground'`, supersession of a non-ground entry — could forge ground,
unseal sealed text, or launder inference into canon without any ceremony.

v0.2 removes the columns. Status is now **derived from the append-only record
trail**: an entry is ground because an adoption record adopts it, sealed
because the latest seal/unseal record says so, superseded because a
supersedes edge points at it. There is nothing to flip; forging status
requires inserting a record, which is the ceremony. The seven exploits are
now refusal tests (`tests/test_promotion_boundary.py`).

If you copied `schema.sql` from v0.1: your promotion boundary has the same
gap. Migrate (below) or re-copy the v0.2 schema.

### Constitution (`schema.sql`) — breaking

- **Removed** `authority`, `visibility`, `superseded_by` columns from `entries`
- **Removed** bucket `superseded_canon` (superseded is a derived status); **added** bucket `unsealing_record`
- Entries and edges fully immutable: UPDATE of any column refused by trigger (v0.1 protected only `body`)
- `body_hash` CHECK: 64 lowercase hex characters
- Seal/unseal state guards at SQL level: double-seal and stray unseal refused
- Sealing removes the body from the FTS index via edge triggers; unsealing restores it
- New `sealed_entries` view; `current_ground` and `retrievable_entries` rebuilt as derivations of the record trail
- `retrieval_log.result_ids_json`: searches record their result sets
- `adopts` edge now points at the entry that becomes ground (v0.1 pointed at the adopted source)

### Reference wrapper — breaking

- `insert_entry` has no `authority`/`visibility` parameters and refuses ceremony buckets and ceremony edge kinds; `add_edge` refuses ceremony kinds
- `adopt` writes the full trail (canon entry + adoption record) in one transaction and records the adopting speaker's signature
- `supersede` refuses non-ground entries and is itself an adoption ceremony (requires adopting words)
- `seal`/`unseal` are record inserts only; `unseal` implemented (the `unseals` edge existed unused in v0.1)
- `adopt_to_ground` requires `adopting_signature`; the English praise check is now a documented convenience lint (non-English adoptions pass) — speaker authentication is explicitly the host application's responsibility
- `insert_pair` signature `conversation` added to the FOREST.md Law 2 vocabulary
- `check_file_drift` follows the adoption record's `adopts` edge to the ground entry
- `ForestStore` opens with WAL mode and a 5s busy timeout
- New: `migrate_v01_to_v02(old_path, new_path)` — copies a v0.1 store into a
  fresh v0.2 store, translating status columns into record trails; synthetic
  records are signed `migration` so they are never mistaken for
  contemporaneous authority acts. Refuses stores whose `body_hash` does not
  match the body.

### Migrating from v0.1

```python
from forest_memory import migrate_v01_to_v02
report = migrate_v01_to_v02("old_forest.db", "new_forest.db")
print(report)  # counts + notes (e.g. hidden/deep visibility has no v0.2 equivalent)
```

If you wrote your own wrapper against the v0.1 schema, port the same rules:
no status writes anywhere, ceremonies as pure inserts, supersession gated on
current ground.

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
