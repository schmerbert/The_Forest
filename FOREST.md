# THE FOREST

*A custody-first memory layer for AI systems.*

Forest is not “better RAG.” It is the missing custody layer under long-running AI work.

A memory system should know the difference between:

- what the user said
- what the model inferred
- what a source claimed
- what was drafted but not adopted
- what was adopted as ground
- what was superseded
- what was sealed and must not return

Retrieval may find text. Retrieval may not promote text.

That is the Forest.

## 1. Diagnosis

The standard pattern — chunk → embed → cosine → stuff context — discards structure at every step.

1. **Chunking severs ancestry.** A chunk often does not know what it came from, what preceded it, or what it was said in response to.
2. **Similarity becomes the only law.** Superseded facts, rejected ideas, model guesses, and author ground can retrieve side by side with the same apparent confidence.
3. **Relevance is assumed to be semantic.** In long work, the valuable retrieval is often causal, procedural, or genealogical rather than semantically similar.
4. **Retrieval is stateless.** The system usually does not remember what was retrieved, what mattered, what misled it, or what was later corrected.

The diagnosis in one line:

> RAG often fails because it stores text and discards custody.

Forest stores custody with the text.

## 2. Constitution

The rules are the product. The database is just the container.

### Law 1 — append-only

Entries are never rewritten in place. Revision is supersession: the old entry remains, and the new entry records that it supersedes the old one.

Old ground does not vanish. It loses current authority.

### Law 2 — everything is signed

Every entry carries the identity class that produced it: author, model, source, visitor, tool, system, or another explicit signature.

An unsigned entry is refused.

### Law 3 — everything has ancestry

Every non-root entry must carry at least one origin edge.

An entry that cannot walk back to its origin was never ground. It may be text. It may be a guess. It may be useful. It is not certified.

Conversation pairs are the usual roots, because most facts enter through exchanges.

### Law 4 — similarity cannot promote

Search may surface an entry. Ancestry may explain it. Only a recorded authority act can promote it.

In a writer's system, the authority-holder is usually the author. In a research system, it may be the principal investigator or the citation standard. In a product system, it may be the accepted spec.

Promotion must be explicit and recorded.

## 3. Core concepts

### Entry

An entry is a verbatim stored unit. It is not “the meaning of” a thing unless its bucket says it is a synthesis.

Recommended fields:

- `id`
- `created_at`
- `forest`
- `bucket`
- `signature`
- `authority`
- `visibility`
- `superseded_by`
- `body`
- `body_hash`
- `meta_json`

### Edge

An edge records ancestry or relation.

Keep the vocabulary closed and small. A rich edge taxonomy can become similarity wearing a graph costume.

Recommended edge kinds:

- `spoken_in` — entry came from a conversation pair
- `responds_to` — conversation pair links to the prior pair
- `derived_from` — synthesis or inference points to sources
- `adopts` — adoption record points to what was adopted
- `supersedes` — new entry points to old entry
- `cites` — claim points to external source/import
- `seals` — sealing record points to sealed entry
- `unseals` — unsealing record points to unsealed entry

### Bucket

A bucket is the entry kind. Buckets are pollution control by exclusion.

Reference set:

- `session_pair`
- `draft`
- `canon`
- `superseded_canon`
- `visitor_words`
- `note`
- `hearsay`
- `synthesis`
- `inference`
- `question`
- `adoption_record`
- `sealing_record`
- `import`

A retrieval scope is a set of open buckets. A closed bucket cannot leak. A downweighted result still can.

### Signature

A signature is who produced the text.

Examples:

- `author`
- `model`
- `source:nytimes`
- `visitor:george`
- `tool:parser`
- `system`

Do not confuse signature with authority. A model can sign an entry; that does not make it ground.

### Authority

Authority is what the entry is allowed to mean downstream.

Reference set:

- `ground` — accepted authority-holder ground
- `model` — produced by the model
- `inference` — derived possibility, not ground
- `draft` — proposed text, not adopted
- `stranger` — visitor words
- `hearsay` — imported/source claim
- `record` — procedural record such as adoption or sealing

## 4. Conversation pairs are the trunk

Most memory is born in conversation.

Facts are stated in response to prompts. Drafts are produced after requests. Adoptions are exchanges. Corrections happen in turns.

Therefore conversation pairs should be inserted as the session happens, not reconstructed later.

A later transcript is a diary. A live conversation-pair trunk is ancestry.

Root discipline:

- A `session_pair` may be a root.
- Every other entry needs at least one origin edge.
- If you dislike root exceptions, create a synthetic `session` entry and make each pair descend from it.

## 5. Three woods, one table

The `forest` field separates jurisdiction.

### Home wood

Everything produced inside the environment:

- session pairs
- drafts
- notes
- adoptions
- superseded canon
- visitor words

The signature says who produced it. The bucket says what kind of thing it is.

### Wild wood

Imported material:

- articles
- webpages
- research notes
- citations
- copied source text

Wild entries enter with weak authority. They can be cited and synthesized, but they do not become ground without an authority act.

### Mycelium

Mycelium is not a third writable place. It is the emergent network under the woods.

It may fruit questions. It must not assert answers.

A pattern stated as fact without authority is invention in a lab coat.

## 6. Retrieval

### Traverse: day-one retrieval

Start with keyword/FTS search (`ForestStore.search` in the reference wrapper). Then walk manually:

- up ancestry to origins
- sideways to sibling entries from the same exchange
- forward through supersession to current ground (`current_ground` view)
- outward to citations and derived notes

**v0.1 ships search + views only.** Traverse is a consumption pattern your host implements — not a library function yet. Do not wait for automation; walk by hand until boring.

Results must always arrive wearing:

- signature
- authority
- bucket
- visibility
- ancestry pointers

The consuming model should weigh, not merely receive.

### Wander: later discovery

Wander is non-greedy, visibility-aware graph walking. It is for discovery, not certification.

Wander should supply candidates. Recognition belongs to the receiving model or user.

### Vectors: last cable

Embeddings are useful as cold entry points when keyword fails. They are not the constitution.

Add vectors after the custody layer is boring and trusted.

## 7. Supersession

Supersession must be atomic.

The same transaction should:

1. insert the new entry
2. write an edge from new to old: `supersedes`
3. set `old.superseded_by = new.id`
4. optionally move old from `canon` to `superseded_canon`

Old canon remains inspectable but should not be returned as current ground unless explicitly requested as history.

## 8. Adoption

Adoption is how authority changes.

A model draft cannot become canon because it was similar, useful, beautiful, or repeatedly retrieved. It becomes canon only when the authority-holder explicitly adopts it.

An adoption record should include the authority-holder's quoted act, date, and edge to the adopted entry.

Example:

```text
body: "Adopt this: Elias betrayed her in winter, not spring."
signature: author
authority: record
bucket: adoption_record
edge: adopts -> draft_or_inference_entry
```

The adopted ground should then be inserted or superseded through the same transaction.

## 9. Sealing

Append-only memory needs a deletion answer.

The answer is not deletion. The answer is sealing.

`visibility = sealed` means:

- not returned by FTS
- not returned by traverse
- not returned by wander
- not used as mycelium/question substrate
- not silently summarized back into context

Sealing is a recorded act. The sealing record remains open; the sealed body does not.

Edges to a sealed entry should resolve to:

```text
sealed on DATE at the authority-holder's request
```

not to the body.

Unsealing requires the same explicit ceremony in reverse.

Deletion promises absence and can never prove it. Sealing promises silence and can prove it.

## 10. Ground outside the store

Many systems keep human-readable ground in files: markdown canon, specs, manuscripts, notes.

That is often correct. Humans need files they can read and love.

But files can be silently edited. An append-only store cannot protect an external file unless it keeps receipts.

If ground also lives outside the store, add:

- `body_hash` for every entry (hashed at insert; adoption records included)
- `source_path` or `source_uri` in metadata
- a drift check that compares current file text to the adopted entry

The reference wrapper provides `drift.check_file_drift` for this pattern.

Every ground statement should exist twice:

1. in the readable file
2. in the constitutional store

Drift then surfaces as mismatch rather than by vigilance.

## 11. What not to build first

Do not build the beautiful layer first.

Do not start with:

- embeddings
- autonomous wander
- mycelium machinery
- elaborate agents
- elaborate edge vocabularies
- tuning dashboards
- memory personalities

Start with:

- schema
- insert wrapper
- session-pair roots
- origin edges
- adoption
- supersession
- sealing
- hostile tests

The discipline is:

> schema yes, machinery later.

Columns are cheap at birth and painful to retrofit. Machinery built before friction is guessing.

## 12. Hostile tests

See `tests/HOSTILE_CASES.md` for the full matrix. Constitutional refusals live in the schema; ceremonial refusals live in your promotion gate.

A usable Forest should refuse:

1. unsigned inserts
2. orphan non-root inserts
3. model text becoming ground without adoption
4. superseded canon returning as current ground
5. sealed entries appearing in any retrieval path
6. wild/hearsay entries becoming ground through synthesis alone
7. silent rewrite of an existing body
8. unlogged retrieval scopes

## 13. Adopting Forest

1. Decide the authority-holder.
2. Copy the schema.
3. Write the insert wrapper.
4. Insert conversation pairs in real time.
5. Require signatures.
6. Require ancestry.
7. Add adoption and supersession ceremonies.
8. Add sealing before anyone needs it.
9. Traverse manually until boring.
10. Add cables only when the boring core reveals friction.

A marble, app, notebook, agent, or writing environment can give Forest a face.

Forest does not need the face to work. The face needs Forest to stay honest.
