# Hostile cases

Forest is useful only if it refuses the usual shortcuts. Each case names **who enforces it** in this repository.

| Layer | Enforced by |
|-------|-------------|
| **Constitutional** | `schema.sql` and/or `ForestStore` at write or retrieve time |
| **Ceremonial** | `root_to_ground` (only public root path) |
| **Drift** | `check_file_drift` when ground also lives in files |
| **Scroll** | `Scroll.dump_all` refused; pairs require `scroll_ptr` |

| # | Case | Layer | Test |
|---|------|-------|------|
| 1 | Unsigned insert | Constitutional | `test_constitutional.py` |
| 2 | Orphan non-pair insert | Constitutional (wrapper) | `test_constitutional.py` |
| 3 | Praise is not root | Ceremonial | `test_ceremony.py` |
| 4 | Paraphrase posed as rooted body (`source_verbatim`) | Ceremonial | `test_ceremony.py` |
| 5 | Superseded fact treated as current truth | Constitutional (view) | `test_constitutional.py` |
| 6 | Sealed entry leaks | Constitutional | `test_constitutional.py` |
| 7 | Wild wood launders into ground | Ceremonial + views | `test_ceremony.py` |
| 8 | Unlogged recall | Constitutional (wrapper) | `test_constitutional.py` |
| — | Silent body rewrite | Constitutional (trigger) | `test_constitutional.py` |
| — | Silent entry delete | Constitutional (trigger) | `test_constitutional.py` |
| — | Silent edge delete | Constitutional (trigger) | `test_constitutional.py` |
| — | Silent file edit after root | Drift | `test_drift.py` |
| 9 | Ground asserted at insert time | Constitutional (wrapper) | `test_promotion_boundary.py` |
| 10 | Status forged by UPDATE (any column) | Constitutional (trigger) | `test_promotion_boundary.py` |
| 11 | Supersession of a non-ground entry | Constitutional (wrapper) | `test_promotion_boundary.py` |
| 12 | Ceremony bucket/edge written outside a ceremony | Constitutional (wrapper) | `test_promotion_boundary.py` |
| 13 | Fabricated-speaker root (unsigned adopting words) | Ceremonial | `test_promotion_boundary.py` |
| 14 | Non-English root wrongly refused | Ceremonial (regression) | `test_promotion_boundary.py` |
| 15 | Malformed `body_hash` | Constitutional (CHECK) | `test_promotion_boundary.py` |
| 16 | Sealed body present in raw FTS index | Constitutional (trigger) | `test_promotion_boundary.py` |
| 17 | Double-seal / stray unseal | Constitutional (trigger + wrapper) | `test_promotion_boundary.py` |
| 18 | Pre-0.4 store opened by 0.4 code | Constitutional (wrapper) | `test_refuse_old.py` |
| 19 | Unlabeled recall scrap | Constitutional (wrapper) | `test_recall.py` |
| 19b | Recall/around full body as discovery | Constitutional (wrapper) | `test_recall.py` |
| 20 | Empty ground is fine (root optional) | Constitutional | `test_recall.py` |
| 21 | Whole-scroll dump into context | Scroll | `test_scroll.py` |
| 21b | Complete scroll via `read_slice(0, size)` | Scroll | `test_scroll.py` |
| 22 | Walk open/step/read does not write receipts | Constitutional | `test_trail.py` |
| 22b | Pair without `scroll_ptr` | Constitutional (wrapper) | `test_trail.py` |
| 22c | Forged / spent ticket read or step | Constitutional (wrapper) | `test_trail.py` |
| 22d | `step` without prior `around` disclosure | Constitutional (wrapper) | `test_trail.py` |
| 22e | `walk_back` on non-ground / missing signature | Constitutional (wrapper) | `test_trail.py` |
| 22f | Wild read cites into next pair | Constitutional (wrapper) | `test_trail.py` |
| 22g | `authority_report` previews only; works on non-ground | Constitutional (wrapper) | `test_trail.py` |
| 23 | Recall with FTS-unsafe query (special chars) | Constitutional (wrapper) | `test_adversarial.py` |
| 23b | Unicode recall tokens (accented/CJK/Arabic/Cyrillic) | Constitutional (wrapper) | `test_recall.py` |
| 24 | add_edge lost on crash (commit missing) | Constitutional (wrapper) | `test_adversarial.py` |
| 25 | Root sealed entry refused | Constitutional (wrapper) | `test_adversarial.py` |
| 26 | Root superseded entry refused | Constitutional (wrapper) | `test_adversarial.py` |
| 27 | Supersede with ceremony bucket for new body | Constitutional (wrapper) | `test_adversarial.py` |
| 28 | Scroll slice larger than MAX_SLICE refused | Scroll | `test_adversarial.py` |
| 29 | around() discloses routes; step rejects wrong direction | Constitutional (wrapper) | `test_adversarial.py` |
| 29b | Multiple relations to same destination preserved | Constitutional (wrapper) | `test_adversarial.py` |
| 30 | root postcondition / expected_body_hash mismatch | Ceremonial + wrapper | `test_adversarial.py` |
| 31 | Empty/malformed schema vs fresh DB | Constitutional (wrapper) | `test_refuse_old.py` |

Cases 2, 8, 9, 12, 19, and 22b–22f are enforced by `ForestStore` in the reference wrapper, not by SQL alone.

**History:** cases 9–17 come from an external audit that defeated the v0.1
promotion boundary. v0.2 removed mutable status columns. v0.4 hard-cuts to
clinical ops: in-place optional `root_to_ground`, jurisdiction-first recall
packets, ticketed walk, required `scroll_ptr`, no canon mint, no migrate path
from 0.3. MCP integration removed from the repo.

---

## 1. Unsigned insert

Attempt to insert text without a signature.

**Expected:** refused.

## 2. Orphan insert

Attempt to insert a non-`pair` entry with no origin edge.

**Expected:** refused. Only `pair` may omit origins (and pairs require `scroll_ptr`).

## 3. Praise is not root

Attempt to root with praise-only adopting words.

**Expected:** ceremonial refusal; no ground.

## 4. Paraphrase posed as rooted body

When `source_verbatim` is set on `root_to_ground`, the existing entry body must match exactly (in-place root — no replacement body).

**Expected:** refused.

## 5. Superseded fact as current truth

**Expected:** only the live rooted entry appears in `current_ground`.

## 6. Sealed entry leaks

**Expected:** sealed body absent from FTS and `recall_similar`.

## 7. Wild laundering

Wild/hearsay/synthesis never become ground without root.

## 8. Unlogged recall

Every `recall_similar` writes `retrieval_log` including result ids.

## 9–17. Promotion boundary

No authority parameter; no ceremony buckets at the front door; UPDATE refused;
supersede only on ground; speaker recorded; body_hash CHECK; seal FTS shadow.

## 18. Pre-0.4 store

**Expected:** `ForestError` pointing at hard cut / fresh DB.

## 19. Unlabeled recall scrap

**Expected:** every scrap leads with `jurisdiction` `home`|`wild`.

## 19b. Recall / around full body

**Expected:** `excerpt_len` missing/non-positive or body-as-discovery refused; full body is `read` only.

## 20. Root optional

**Expected:** pairs + recall with empty `current_ground` is valid.

## 21. Scroll dump

**Expected:** `Scroll.dump_all()` raises.

## 22. Walk receipts / tickets / scroll_ptr

**Expected:** `open` / neighbor `step` / `read` do not insert entries; `around` returns previews only; forged tickets refused; `step` requires prior `around` disclosure; pairs without `scroll_ptr` refused; `walk_back` requires current ground + signature and returns previews only; wild `read` cites into the next pair; `authority_report` returns previews/status/`body_hash` without bodies.
