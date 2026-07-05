# THE FOREST

*A custody-first memory layer for AI systems.*

Forest is not “better RAG.” It is the missing layer that records **where text came from** and **what it is allowed to mean** — underneath retrieval.

**Custody** means every stored unit carries:

- who produced it (signature)
- what kind of thing it is (bucket)
- where it came from (ancestry edges)
- whether it is ground, superseded, or sealed — **derived from the record trail, never stored as a flag**

A memory system should distinguish:

- what the user said
- what the model inferred
- what a source claimed
- what was drafted but not adopted
- what was adopted as ground
- what was superseded
- what was sealed and must not return

Retrieval may find text. Retrieval may not promote text.

That is the Forest.

The enforced artifact is [`schema.sql`](schema.sql). This document is the constitution behind it — the reference Forest schema for adopters.

---

## 1. Diagnosis

The usual pattern — chunk → embed → cosine → stuff context — discards structure at every step.

1. **Chunking severs ancestry.** A chunk often does not know what it came from, what preceded it, or what it was said in response to.
2. **Similarity becomes the only law.** Superseded facts, rejected ideas, model guesses, and author ground can retrieve side by side with the same apparent confidence.
3. **Relevance is assumed to be semantic.** In long work, the valuable retrieval is often causal, procedural, or genealogical — not semantically similar.
4. **Retrieval is stateless.** The system usually does not remember what was retrieved, what mattered, what misled it, or what was later corrected.

In one line:

> RAG often fails because it stores text and discards custody.

Forest stores custody with the text.

---

## 2. The four laws

The rules are the product. The database is the container.

### Law 1 — append-only

Entries are never rewritten or deleted. Revision is supersession: the old entry remains, and the new entry records that it supersedes the old one. Ancestry edges are never deleted.

Old ground does not vanish. It loses current authority.

### Law 2 — everything is signed

Every entry carries the identity class that produced it: `author`, `model`, `source`, `visitor`, `tool`, `system`, `conversation` (session pairs), or another explicit signature.

An unsigned entry is refused.

### Law 3 — everything has ancestry

Every non-root entry must carry at least one origin edge.

An entry that cannot walk back to its origin was never ground. It may be text. It may be a guess. It may be useful. It is not certified.

### Law 4 — similarity cannot promote

Search may surface an entry. Ancestry may explain it. Only a recorded **authority act** can promote it.

The **authority-holder** depends on context: the author in a writing system, the PI or citation standard in research, the accepted spec in a product.

Promotion must be explicit and recorded. And since v0.2, promotion is **only** a record: ground is not a column that can be written, it is a status derived from the existence of an adoption record. Forging ground requires inserting an adoption record — which *is* the ceremony.

---

## 3. Core concepts

### Entry

A verbatim stored unit. It is not “the meaning of” a thing unless its bucket says it is a synthesis.

Fields (see `schema.sql`):

| Field | Role |
|-------|------|
| `id`, `created_at` | Identity and time |
| `forest` | Jurisdiction: `home` or `wild` |
| `bucket` | Entry kind at birth (see below) |
| `signature` | Who produced the text |
| `body`, `body_hash` | Verbatim text and SHA-256 at insert |
| `meta_json` | Optional metadata (`source_path`, `source_uri`, …) |

Every column is an immutable fact about the text **at birth**. There is no
`authority` column, no `visibility` column, no `superseded_by` pointer —
v0.1 stored those as mutable columns, and a single `UPDATE` could forge
ground. Status is derived:

| Status | Derived from |
|--------|--------------|
| ground | An `adoption_record` has an `adopts` edge to the entry, nothing supersedes it, and it is not sealed (`current_ground` view) |
| superseded | A `supersedes` edge points at the entry |
| sealed | The latest `seals`/`unseals` edge pointing at the entry is `seals` (`sealed_entries` view) |

### Edge

An edge records ancestry or relation. Keep the vocabulary small — a large edge taxonomy becomes another similarity layer.

Kinds in v0.3:

| Kind | Meaning |
|------|---------|
| `spoken_in` | Entry came from a conversation pair |
| `responds_to` | Pair links to the prior pair |
| `derived_from` | Synthesis or inference points to sources |
| `adopts` | Adoption record points to the entry that becomes ground |
| `supersedes` | New entry points to old entry |
| `cites` | Claim points to external source/import |
| `seals` | Sealing record points to sealed entry |
| `unseals` | Unsealing record points to unsealed entry |
| `asks_about` | Question points to the entry it grew next to (mycelium) |
| `feeds` | Entry points to the question it nourishes (mycelium) |
| `answers` | Entry points to the question it answers — never promotes |
| `reopens` | Entry points to the question it reopens (mycelium) |

`adopts`, `supersedes`, `seals`, and `unseals` are **ceremony acts** — they
carry status, so the reference wrapper refuses them outside the ceremonies
(`adopt`, `supersede`, `seal`, `unseal`).

### Bucket

The entry kind. Buckets scope retrieval — a closed bucket cannot leak into a query.

Reference set:

`session_pair`, `draft`, `canon`, `visitor_words`, `note`, `hearsay`, `synthesis`, `inference`, `question`, `adoption_record`, `sealing_record`, `unsealing_record`, `import`

`canon`, `adoption_record`, `sealing_record`, and `unsealing_record` are
ceremony buckets: only a ceremony writes them. (`superseded_canon` from v0.1
is gone — superseded is a derived status, not a kind of entry.)

A retrieval scope is a set of open buckets. Filtering by bucket is exclusion, not weighting — a downweighted result can still mislead.

### Signature vs status

Do not confuse them.

- **Signature** — who produced the text (`author`, `model`, `source:nytimes`, `visitor:george`, `tool:parser`, `system`, `conversation`). A custody fact, fixed at birth.
- **Status** — what the entry is allowed to mean downstream (ground, superseded, sealed). A conclusion derived from the record trail, never written directly.

A model-signed entry is not ground until adopted. And nothing — not an
`UPDATE`, not a parameter, not a retrieval heuristic — can make it ground
except an adoption record.

---

## 4. Conversation pairs are the trunk

Most memory is born in conversation. Facts are stated in response to prompts. Drafts follow requests. Adoptions and corrections happen in turns.

Insert conversation pairs **as the session happens**, not reconstructed from a transcript later. Reconstruction loses ancestry.

Root discipline:

- A `session_pair` may be a root (no origin edge required).
- Every other entry needs at least one origin edge.
- If you dislike root exceptions, create a synthetic `session` entry and make each pair descend from it.

---

## 5. Two jurisdictions: home and wild

The `forest` field separates where material entered.

### Home (`forest = home`)

Produced inside your environment: session pairs, drafts, notes, adoptions, superseded canon, visitor words.

### Wild (`forest = wild`)

Imported material: articles, webpages, research notes, citations, copied source text.

Wild entries enter with weak authority. They can be cited and synthesized. They do not become ground without an authority act.

There is no third writable `forest` value in v0.2. Graph-walking discovery patterns (“wander”, question networks) are host-layer features — not part of the schema until the core is boring.

---

## 6. Supersession

Supersession is itself an adoption ceremony — the replacement text becomes
ground, so it needs its own adoption record. And only current ground can be
superseded: superseding an inference or draft was a laundering side-channel
in v0.1, and the wrapper now refuses it.

In one transaction:

1. Insert the new `canon` entry
2. Write edge `new → old` with kind `supersedes`
3. Insert an `adoption_record` quoting the authority-holder, with edge `adopts → new`

Nothing on the old entry changes. It stops being current ground because a
`supersedes` edge now points at it — status is derived, not flipped.

Old canon remains inspectable. It must not be returned as **current ground** unless history is explicitly requested.

Use the `current_ground` view for authoritative truth. Keyword search may still return superseded text — that is history, not current authority.

---

## 7. Adoption

Adoption is how text becomes ground.

A model draft cannot become canon because it was similar, useful, beautiful, or repeatedly retrieved. It becomes canon only when the authority-holder explicitly adopts it.

Adoption is one transaction producing two entries:

1. a new `canon` entry — the ground text, `derived_from →` the adopted draft/inference
2. an `adoption_record` — the authority-holder's quoted act (verbatim), signed with who spoke it, `adopts →` the new canon entry

Example:

```text
canon entry:      body: "Elias betrayed her in winter, not spring."
                  signature: author
                  edge: derived_from -> draft_or_inference_entry

adoption_record:  body: "Adopt this: winter, not spring."
                  signature: author       (who spoke the adopting words)
                  edge: adopts -> canon entry
```

The canon entry is ground *because* that trail exists — there is no flag to set.

**Ceremonial refusals** (praise mistaken for adoption, paraphrase posed as author prose) live in your application layer — not in the schema. The reference wrapper provides `adopt_to_ground` as an example gate.

**Trust boundary:** the store records the adopting signature verbatim; it
cannot verify that the named speaker actually spoke. Authenticating the
speaker is the host application's responsibility. The wrapper's praise
check is an English-only convenience lint, not enforcement — deciding what
counts as an adoption act in your language and interface is yours.

---

## 8. Sealing

Append-only memory still needs an answer to “remove this.”

The answer is not deletion. The answer is sealing.

Sealing is a record insert: a `sealing_record` with edge `seals →` the entry.
Unsealing is the same ceremony in reverse (`unsealing_record`, `unseals`).
An entry is sealed iff the latest seal/unseal record pointing at it is a
seal — there is no visibility column to flip, and the seal/unseal trail is
required to alternate (double-seals are refused at the SQL level).

Sealed means the body is not returned by:

- FTS / keyword search — the sealing act removes the body **from the index itself**, not just from query results
- any traversal or summary path you build
- derived retrieval that would re-expose the text

Sealing is a recorded act. The sealing record remains open; the sealed body does not.

Edges to a sealed entry should resolve to:

```text
sealed on DATE at the authority-holder's request
```

not to the body. Unsealing requires the same explicit ceremony in reverse.

Deletion promises absence and can never prove it. Sealing promises silence and can prove it.

---

## 9. Ground outside the store

Many systems keep human-readable ground in files: markdown canon, specs, manuscripts, notes. That is often correct.

Files can be silently edited. The store cannot protect an external file unless it keeps receipts.

If ground also lives outside the store:

- hash every entry at insert (`body_hash`)
- record `source_path` or `source_uri` in `meta_json`
- run a drift check comparing current file text to the adoption record

The reference wrapper provides `drift.check_file_drift` for this pattern.

**Limitation (v0.2):** `check_file_drift` compares the **SHA-256 of the entire file** to the ground entry behind one adoption record. That works when the adopted body is the whole file (a single canon document, a full manuscript export). It does **not** track individual sections inside a larger Markdown file. If one paragraph was adopted but the file contains other editable sections, drift detection will false-alarm or miss partial edits. For multi-section files, adopt whole-file snapshots, or treat anchored spans / byte ranges as future work.

Every adopted ground statement should exist twice:

1. in the readable file
2. in the constitutional store

Drift surfaces as mismatch — not vigilance.

---

## 10. Retrieval

### v0.2: search, views, manual walk

v0.2 ships keyword/FTS search and SQL views — not automated traverse.

Start with search (`ForestStore.search` in the reference wrapper). Then walk manually:

- up ancestry to origins
- sideways to sibling entries from the same exchange
- forward through supersession to current ground (`current_ground` view)
- outward to citations and derived notes

Every result should arrive wearing signature, bucket, derived status, and ancestry pointers. The consuming model should weigh — not merely receive.

Every search should log scope **and results** (`retrieval_log` in the schema records the query, the open buckets, and the entry ids returned) — otherwise diagnosis point 4 above ("retrieval is stateless") stays unfixed.

### Later: wander and vectors

**Wander** — non-greedy, seal-aware graph walking for discovery, not certification. Candidates only; promotion still requires ceremony.

**Vectors** — embeddings as cold entry points when keyword fails. Useful after the custody layer is boring and trusted. Not part of v0.2.

---

## 11. Hostile tests

See [`tests/HOSTILE_CASES.md`](tests/HOSTILE_CASES.md) for the full matrix.

Constitutional refusals live in the schema. Ceremonial refusals live in your promotion gate.

A usable Forest should refuse:

1. unsigned inserts
2. orphan non-root inserts
3. model text becoming ground without adoption
4. superseded canon returning as current ground
5. sealed entries appearing in any retrieval path
6. wild/hearsay entries becoming ground through synthesis alone
7. silent rewrite or delete of an entry or edge
8. unlogged retrieval scopes
9. ground asserted at insert time (there is no authority parameter to forge)
10. status forged by `UPDATE` (every column of entries and edges refuses updates)
11. supersession of a non-ground entry (laundering side-channel)
12. ceremony buckets or ceremony edge kinds written outside a ceremony

An external audit of v0.1 defeated the promotion boundary seven ways while
all hostile tests passed — every exploit wrote status columns directly. Those
seven exploits are now refusal tests (`tests/test_promotion_boundary.py`),
and the columns they wrote no longer exist.

### Threat model — what the triggers do and do not defend

The SQL triggers defend against **buggy or confused application code** — the
failure mode that actually corrupts memory stores. They do not defend against
an adversary with write access to the database file: whoever can run `UPDATE`
can also run `DROP TRIGGER`. If you need protection against a hostile writer,
put the file behind an authenticating service boundary. What the derived-status
design guarantees is stronger than any trigger: there is no cheap flag to flip —
forging status means fabricating a full record trail, and a fabricated trail is
at least visible, attributable, and immutable once written.

---

## 12. Adopting Forest

1. Decide the authority-holder.
2. Copy [`schema.sql`](schema.sql) — **and write an insert wrapper**. SQL alone does not enforce ancestry, ceremonies, or retrieval logging.
3. Wire signatures, ancestry, adoption, supersession, and sealing in your wrapper.
4. Insert conversation pairs in real time.
5. Add a promotion gate (praise ≠ adoption).
6. Add sealing before anyone needs it.
7. Walk ancestry manually until boring.
8. Add embeddings, wander, or agents only when the core reveals friction.

Do not start with embeddings, elaborate edge vocabularies, tuning dashboards, or memory personalities.

> Schema yes, machinery later.

Columns are cheap at birth and painful to retrofit.

---

## What v0.2 ships

- `schema.sql` with fully immutable entries and edges (every UPDATE and DELETE refused)
- Status derived from the record trail — no authority/visibility/superseded_by columns
- Views: `current_ground`, `sealed_entries`, `retrievable_entries`
- Sealing that removes bodies from the FTS index itself; unsealing restores
- `retrieval_log` with result ids
- Reference wrapper: insert, adopt, supersede (ground-only), seal, unseal, search, ceremony gate, drift check
- v0.1 → v0.2 migration (`forest_memory.migrate`)
- Hostile tests across constitutional, ceremonial, promotion-boundary, migration, and drift layers

## What v0.3 does not ship

- Embeddings
- Automated traverse or wander
- Agent orchestration

Add those when the boring core hurts — not before.

## Mycelium (v0.3)

Questions are mycelium: an underground network attached to the entries it
grew from. A question is planted next to specific material (`asks_about`),
nourished by later entries (`feeds` — each feed is ripeness), and it FRUITS
at retrieval time: when a search disturbs soil a question is attached to,
the open questions surface next to the results, ripest first
(`mycelium.fruits_near`). Questions never appear in FTS retrieval on their
own, and sealed questions do not fruit.

Question state is derived, never stored, in the same way as sealing: a
question is answered because the latest `answers`/`reopens` edge says so.
Answering never promotes — if an answer deserves ground, the
authority-holder adopts it through the ceremony like any other text.
