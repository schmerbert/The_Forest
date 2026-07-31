# Porter checklist — minimum a reimplementation / fork must enforce

SQL (`schema.sql`) alone is **not** enough. Copy the reference wrapper
behavior or your promotion boundary will rot the same way v0.1 did.

Hostile tests to port: [`tests/HOSTILE_CASES.md`](tests/HOSTILE_CASES.md).
Ops contract: [`README.md`](README.md). Constitution: [`FOREST.md`](FOREST.md).

## Must enforce (mechanical)

| # | Rule | Where the reference does it | Hostile case |
|---|------|------------------------------|--------------|
| 1 | Refuse unsigned inserts | `ForestStore._insert_row` | 1 |
| 2 | Refuse orphan non-`pair` inserts | `ForestStore.write` | 2 |
| 3 | Refuse ceremony buckets / ceremony edge kinds at the front door | `write` / `add_edge` | 12 |
| 4 | Require `scroll_ptr` (`path` + `offset`) on every pair | `write_pair` / `commit_turn` | 22b |
| 5 | Jurisdiction-first packets on every recall / around scrap | `_require_jurisdiction` / `_row_to_scrap` | 19 |
| 6 | Preview ≠ read (bounded excerpt; no body in discovery) | `recall_*` / `around` | 19b |
| 7 | Ticket continuity: open → around discloses → step spends → read requires ticket | `Trail` + ticket dict | 22c–22d |
| 8 | Pending wild `read` → `cites` on next `write_pair` | `_pending_wild_access` | 22f |
| 9 | Public root only through a gate with required `expected_body_hash` | `root_to_ground` → `_root` | 30 |
| 10 | Status derived from the trail — never a writable authority column | views + no status columns | 9–11 |
| 11 | Append-only entries/edges (UPDATE/DELETE refused) | SQL triggers | silent rewrite/delete |
| 12 | Seal removes body from FTS; sealed refused by open/read/recall | triggers + wrapper | 6, 16 |
| 13 | Log every `recall_similar` (query + result ids) | `retrieval_log` | 8 |
| 14 | Refuse pre-0.4 / wrong `forest_meta.schema_version` | `_refuse_outdated_store` | 18, 31 |

## Non-goals for porters (do not pretend SQL covers these)

- **Speaker authentication** — host authenticates before `root_to_ground` / audit signatures.
- **Praise lint** — English regex convenience only; **not** a security boundary.
- **Jurisdiction honesty on write** — host stamps `home`/`wild`; Forest labels packets, does not babysit stamps.
- **Ticket durability across processes** — tickets live on one long-lived `ForestStore` instance (see README).
- **Embeddings / `near`** — named; not shipped. Host may hybrid-rank then call `recall_side` / `open` (still jurisdiction-first previews).

## Suggested port order

1. Schema + triggers + views (`current_ground`, `sealed_entries`, FTS shadow).
2. Write path (scrub hook, orphan/ceremony refusals, `scroll_ptr`).
3. Recall packets + retrieval log.
4. Ticketed walk.
5. Ceremonies (`_root` / supersede / seal) behind a host gate with `expected_body_hash`.
6. Run / adapt the hostile suite until green.
