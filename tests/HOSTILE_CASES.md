# Hostile cases

Forest is useful only if it refuses the common laundering paths.

Each case names **who enforces it** in this repository:

- **Constitutional** — `schema.sql` and/or `ForestStore` refuse at write or retrieve time
- **Ceremonial** — your application must call a promotion gate (`ceremony.adopt_to_ground` in the reference wrapper)
- **Drift** — external files compared to adoption receipts (`drift.check_file_drift`)

| # | Case | Layer | Test |
|---|------|-------|------|
| 1 | Unsigned insert | Constitutional | `test_constitutional.py` |
| 2 | Orphan non-root insert | Constitutional | `test_constitutional.py` |
| 3 | Praise is not adoption | Ceremonial | `test_ceremony.py` |
| 4 | Paraphrase is not author ground | Ceremonial | `test_ceremony.py` |
| 5 | Superseded fact retrieves as current truth | Constitutional | `test_constitutional.py` (`current_ground` view) |
| 6 | Sealed entry leaks | Constitutional | `test_constitutional.py` |
| 7 | Wild wood launders into ground | Ceremonial + views | `test_ceremony.py` |
| 8 | Unlogged retrieval | Constitutional | `test_constitutional.py` (`retrieval_log`) |
| — | Silent file edit after adoption | Drift | `test_drift.py` |
| — | Silent body rewrite | Constitutional | `test_constitutional.py` (DB trigger) |

---

## 1. Unsigned insert

Attempt to insert text without a signature.

**Expected:** refused.

## 2. Orphan insert

Attempt to insert a non-root entry with no origin edge.

**Expected:** refused.

## 3. Praise is not adoption

The model writes a beautiful line and the user says, "nice." The system attempts to promote the line to canon.

**Expected:** refused unless the authority-holder explicitly adopts the text.

## 4. Paraphrase is not ground

The model paraphrases an author statement and attempts to store the paraphrase as author ground.

**Expected:** refused. Store the paraphrase as model synthesis/inference, or store exact author text.

## 5. Superseded fact retrieves as current truth

Old canon says spring. New canon supersedes it with winter. Query retrieves both.

**Expected:** traversal may show history, but `current_ground` returns winter only.

## 6. Sealed entry leaks

A sealed entry appears through FTS, traverse, wander, summary, question-fruiting, or derived retrieval.

**Expected:** failure. Sealed means silence.

## 7. Wild wood launders into ground

A web source claims a fact. A model synthesis repeats it. The system promotes it to ground.

**Expected:** refused unless authority-holder adopts it. Hearsay and inference may retrieve; they must not appear in `current_ground` without adoption.

## 8. Unlogged retrieval

Search runs without recording scope.

**Expected:** every `search()` writes to `retrieval_log`.

## Silent rewrite

An existing entry body is updated in place.

**Expected:** refused. Use supersession.

## Silent file edit

Ground lives in a readable file and someone edits the file after adoption.

**Expected:** `check_file_drift` surfaces mismatch against the adoption record's `body_hash`.
