# Hostile cases

Forest is useful only if it refuses the usual shortcuts. Each case names **who enforces it** in this repository.

| Layer | Enforced by |
|-------|-------------|
| **Constitutional** | `schema.sql` and/or `ForestStore` at write or retrieve time |
| **Ceremonial** | Your promotion gate (`adopt_to_ground` in the reference wrapper) |
| **Drift** | `check_file_drift` when ground also lives in files |

| # | Case | Layer | Test |
|---|------|-------|------|
| 1 | Unsigned insert | Constitutional | `test_constitutional.py` |
| 2 | Orphan non-root insert | Constitutional (wrapper) | `test_constitutional.py` |
| 3 | Praise is not adoption | Ceremonial | `test_ceremony.py` |
| 4 | Paraphrase is not author ground | Ceremonial | `test_ceremony.py` |
| 5 | Superseded fact treated as current truth | Constitutional (view) | `test_constitutional.py` |
| 6 | Sealed entry leaks | Constitutional | `test_constitutional.py` |
| 7 | Wild wood launders into ground | Ceremonial + views | `test_ceremony.py` |
| 8 | Unlogged retrieval | Constitutional (wrapper) | `test_constitutional.py` |
| — | Silent body rewrite | Constitutional (trigger) | `test_constitutional.py` |
| — | Silent entry delete | Constitutional (trigger) | `test_constitutional.py` |
| — | Silent edge delete | Constitutional (trigger) | `test_constitutional.py` |
| — | Silent file edit after adoption | Drift | `test_drift.py` |
| 9 | Ground asserted at insert time | Constitutional (wrapper) | `test_promotion_boundary.py` |
| 10 | Status forged by UPDATE (any column) | Constitutional (trigger) | `test_promotion_boundary.py` |
| 11 | Supersession of a non-ground entry | Constitutional (wrapper) | `test_promotion_boundary.py` |
| 12 | Ceremony bucket/edge written outside a ceremony | Constitutional (wrapper) | `test_promotion_boundary.py` |
| 13 | Fabricated-speaker adoption (unsigned adopting words) | Ceremonial | `test_promotion_boundary.py` |
| 14 | Non-English adoption wrongly refused | Ceremonial (regression) | `test_promotion_boundary.py` |
| 15 | Malformed `body_hash` | Constitutional (CHECK) | `test_promotion_boundary.py` |
| 16 | Sealed body present in raw FTS index | Constitutional (trigger) | `test_promotion_boundary.py` |
| 17 | Double-seal / stray unseal | Constitutional (trigger + wrapper) | `test_promotion_boundary.py` |
| 18 | v0.1 status columns survive migration untranslated | Migration | `test_migrate.py` |

Cases 2, 8, 9, 11, and 12 are enforced by `ForestStore` in the reference wrapper, not by SQL alone. Your application must enforce the same rules.

**History:** cases 9–17 come from an external audit that defeated the v0.1
promotion boundary seven ways while all seventeen hostile tests passed. Root
cause: status lived in mutable columns (`authority`, `visibility`,
`superseded_by`). v0.2 removed the columns; status is derived from the
append-only record trail, so forging status requires inserting a record —
which is the ceremony.

---

## 1. Unsigned insert

Attempt to insert text without a signature.

**Expected:** refused.

## 2. Orphan insert

Attempt to insert a non-root entry with no origin edge.

**Expected:** refused. Only `session_pair` may be root.

## 3. Praise is not adoption

The model writes a beautiful line and the user says, "nice." The system attempts to promote the line to canon.

**Expected:** refused unless the authority-holder explicitly adopts the text.

## 4. Paraphrase is not ground

The model paraphrases an author statement and attempts to store the paraphrase as author ground.

**Expected:** refused. Store the paraphrase as model synthesis/inference, or store exact author text.

## 5. Superseded fact treated as current truth

Old canon says spring. New canon supersedes it with winter.

**Expected:** keyword search may return both (history). `current_ground` returns winter only. Do not treat search hits as authoritative truth.

## 6. Sealed entry leaks

A sealed entry appears through FTS, traversal, summary, or derived retrieval.

**Expected:** failure. Sealed means silence.

## 7. Wild wood launders into ground

A web source claims a fact. A model synthesis repeats it. The system promotes it to ground.

**Expected:** refused unless authority-holder adopts it. Hearsay and inference may retrieve; they must not appear in `current_ground` without adoption.

## 8. Unlogged retrieval

Search runs without recording scope.

**Expected:** every `search()` writes to `retrieval_log`.

## Silent rewrite

An existing entry body is updated in place.

**Expected:** refused by DB trigger. Use supersession.

## Silent delete

An entry or edge is removed from the store.

**Expected:** refused by DB trigger. Use supersession or sealing — not deletion.

## Silent file edit

Ground lives in a readable file and someone edits the file after adoption.

**Expected:** `check_file_drift` surfaces mismatch against the adoption record's `body_hash`.

## 9. Ground asserted at insert time

`insert_entry` is called with a ground/canon claim.

**Expected:** refused. There is no authority parameter; `canon` and the record buckets are written only by ceremonies.

## 10. Status forged by UPDATE

Any column of `entries` or `edges` is updated in place.

**Expected:** refused by trigger, for every column. Entries and edges are fully immutable rows.

## 11. Supersession launders a non-ground entry

`supersede()` is called on a draft or inference to smuggle a replacement into canon.

**Expected:** refused. Only current ground can be superseded, and the replacement gets its own adoption record.

## 12. Ceremony act outside a ceremony

An `adopts`, `supersedes`, `seals`, or `unseals` edge — or a ceremony bucket — is written through the general insert path.

**Expected:** refused by the wrapper. Ceremony acts carry status; only the ceremonies write them.

## 13. Fabricated-speaker adoption

Adopting words are submitted without a signature naming who spoke them.

**Expected:** refused. The store records the claimed speaker verbatim; authenticating the speaker is the host application's responsibility (documented trust boundary).

## 14. Non-English adoption wrongly refused

The authority-holder adopts in Spanish: "Sí, esto es canon ahora."

**Expected:** accepted. The praise check is an English convenience lint, not enforcement.

## 15. Malformed body_hash

A raw insert supplies a body_hash that is not 64 lowercase hex characters.

**Expected:** refused by CHECK constraint. Hash correctness (hash matches body) is the wrapper's job.

## 16. Sealed body in the raw FTS index

After sealing, `entries_fts` is queried directly, bypassing the wrapper.

**Expected:** no hit. The sealing ceremony removes the body from the index itself; unsealing restores it.

## 17. Double-seal / stray unseal

A second seal on a sealed entry, or an unseal on an open entry.

**Expected:** refused at the SQL level. The seal/unseal trail must alternate so derived status is unambiguous.

## 18. Migration leaves v0.1 status columns behind

A v0.1 store is migrated and old `authority`/`visibility`/`superseded_by` assertions are dropped or kept as columns.

**Expected:** translated into record trails. Trails synthesized where v0.1 had none are signed `migration` so they are never mistaken for contemporaneous authority acts.
