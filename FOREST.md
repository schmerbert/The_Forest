# THE FOREST

*A custody-first memory layer for AI systems.*

Forest is not “better RAG.” It is the missing layer that records **where text came from** and **what it is allowed to mean** — underneath retrieval.

**Custody** means every stored unit carries:

- who produced it (signature)
- what kind of thing it is (bucket)
- what authority it has (ground, inference, hearsay, …)
- where it came from (ancestry edges)
- whether it is current, superseded, or sealed

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

Every entry carries the identity class that produced it: `author`, `model`, `source`, `visitor`, `tool`, `system`, or another explicit signature.

An unsigned entry is refused.

### Law 3 — everything has ancestry

Every non-root entry must carry at least one origin edge.

An entry that cannot walk back to its origin was never ground. It may be text. It may be a guess. It may be useful. It is not certified.

### Law 4 — similarity cannot promote

Search may surface an entry. Ancestry may explain it. Only a recorded **authority act** can promote it.

The **authority-holder** depends on context: the author in a writing system, the PI or citation standard in research, the accepted spec in a product.

Promotion must be explicit and recorded.

---

## 3. Core concepts

### Entry

A verbatim stored unit. It is not “the meaning of” a thing unless its bucket says it is a synthesis.

Fields (see `schema.sql`):

| Field | Role |
|-------|------|
| `id`, `created_at` | Identity and time |
| `forest` | Jurisdiction: `home` or `wild` |
| `bucket` | Entry kind (see below) |
| `signature` | Who produced the text |
| `authority` | What it is allowed to mean downstream |
| `visibility` | `open`, `hidden`, `deep`, or `sealed` |
| `superseded_by` | Pointer when this entry lost current authority |
| `body`, `body_hash` | Verbatim text and SHA-256 at insert |
| `meta_json` | Optional metadata (`source_path`, `source_uri`, …) |

### Edge

An edge records ancestry or relation. Keep the vocabulary small — a large edge taxonomy becomes another similarity layer.

Kinds in v0.1:

| Kind | Meaning |
|------|---------|
| `spoken_in` | Entry came from a conversation pair |
| `responds_to` | Pair links to the prior pair |
| `derived_from` | Synthesis or inference points to sources |
| `adopts` | Adoption record points to what was adopted |
| `supersedes` | New entry points to old entry |
| `cites` | Claim points to external source/import |
| `seals` | Sealing record points to sealed entry |
| `unseals` | Unsealing record points to unsealed entry |

### Bucket

The entry kind. Buckets scope retrieval — a closed bucket cannot leak into a query.

Reference set:

`session_pair`, `draft`, `canon`, `superseded_canon`, `visitor_words`, `note`, `hearsay`, `synthesis`, `inference`, `question`, `adoption_record`, `sealing_record`, `import`

A retrieval scope is a set of open buckets. Filtering by bucket is exclusion, not weighting — a downweighted result can still mislead.

### Signature vs authority

Do not confuse them.

- **Signature** — who produced the text (`author`, `model`, `source:nytimes`, `visitor:george`, `tool:parser`, `system`)
- **Authority** — what the entry is allowed to mean downstream:

| Authority | Meaning |
|-----------|---------|
| `ground` | Accepted authority-holder truth |
| `model` | Produced by the model |
| `inference` | Derived possibility, not ground |
| `draft` | Proposed text, not adopted |
| `stranger` | Visitor words |
| `hearsay` | Imported/source claim |
| `record` | Procedural record (adoption, sealing) |

A model-signed entry is not ground until adopted.

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

There is no third writable `forest` value in v0.1. Graph-walking discovery patterns (“wander”, question networks) are host-layer features — not part of the schema until the core is boring.

---

## 6. Supersession

Supersession must be atomic. In one transaction:

1. Insert the new entry
2. Write edge `new → old` with kind `supersedes`
3. Set `old.superseded_by = new.id`
4. Move old from `canon` to `superseded_canon` when applicable

Old canon remains inspectable. It must not be returned as **current ground** unless history is explicitly requested.

Use the `current_ground` view for authoritative truth. Keyword search may still return superseded text — that is history, not current authority.

---

## 7. Adoption

Adoption is how text becomes ground.

A model draft cannot become canon because it was similar, useful, beautiful, or repeatedly retrieved. It becomes canon only when the authority-holder explicitly adopts it.

An adoption record should include:

- the authority-holder's quoted act (verbatim)
- date (via `created_at`)
- edge `adopts →` the adopted entry

Example:

```text
body: "Adopt this: Elias betrayed her in winter, not spring."
signature: author
authority: record
bucket: adoption_record
edge: adopts -> draft_or_inference_entry
```

Then insert or supersede the ground entry in the same transaction.

**Ceremonial refusals** (praise mistaken for adoption, paraphrase posed as author prose) live in your application layer — not in the schema. The reference wrapper provides `adopt_to_ground` as an example gate.

---

## 8. Sealing

Append-only memory still needs an answer to “remove this.”

The answer is not deletion. The answer is sealing.

`visibility = sealed` means the body is not returned by:

- FTS / keyword search
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

**v0.1 limitation:** `check_file_drift` compares the **SHA-256 of the entire file** to one adoption record's `body_hash`. That works when the adopted body is the whole file (a single canon document, a full manuscript export). It does **not** track individual sections inside a larger Markdown file. If one paragraph was adopted but the file contains other editable sections, drift detection will false-alarm or miss partial edits. For multi-section files, adopt whole-file snapshots in v0.1, or treat anchored spans / byte ranges as future work.

Every adopted ground statement should exist twice:

1. in the readable file
2. in the constitutional store

Drift surfaces as mismatch — not vigilance.

---

## 10. Retrieval

### v0.1: search, views, manual walk

v0.1 ships keyword/FTS search and SQL views — not automated traverse.

Start with search (`ForestStore.search` in the reference wrapper). Then walk manually:

- up ancestry to origins
- sideways to sibling entries from the same exchange
- forward through supersession to current ground (`current_ground` view)
- outward to citations and derived notes

Every result should arrive wearing signature, authority, bucket, visibility, and ancestry pointers. The consuming model should weigh — not merely receive.

Every search should log scope (`retrieval_log` in the schema).

### Later: wander and vectors

**Wander** — non-greedy, visibility-aware graph walking for discovery, not certification. Candidates only; promotion still requires ceremony.

**Vectors** — embeddings as cold entry points when keyword fails. Useful after the custody layer is boring and trusted. Not part of v0.1.

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

## What v0.1 ships

- `schema.sql` with CHECK constraints, append-only trigger, sealed FTS exclusion
- Views: `current_ground`, `retrievable_entries`
- `retrieval_log`
- Reference wrapper: insert, adopt, supersede, seal, search, ceremony gate, drift check
- Hostile tests across constitutional, ceremonial, and drift layers

## What v0.1 does not ship

- Embeddings
- Automated traverse or wander
- Mycelium / question-fruiting machinery
- Agent orchestration

Add those when the boring core hurts — not before.
