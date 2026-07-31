# THE FOREST

*A custody-shaped DB layer for AI harnesses (v0.4).*

Forest is not “better RAG.” It records **where text came from** and **what it is allowed to mean** — underneath your harness.

**Ops contract (axes, walk, packets, loop):** [`README.md`](README.md) — if this file and the README disagree on ops or naming, **the README wins**.  
This document is the **constitution** behind [`schema.sql`](schema.sql) (schema and ceremony depth).

**Custody** means every stored unit carries:

- who produced it (signature)
- what kind of thing it is (bucket, optional source)
- why it is here (jurisdiction: `home` | `wild`)
- where it came from (ancestry edges)
- whether it is ground, superseded, or sealed — **derived from the record trail, never stored as a flag**

Retrieval may find text. Retrieval may not promote text. **Root is optional** — only when something must stay true.

---

## 1. Diagnosis

The usual pattern — chunk → embed → cosine → stuff context — discards structure at every step.

1. **Chunking severs ancestry.**
2. **Similarity becomes the only law.**
3. **Relevance is assumed to be semantic** when the valuable path is often genealogical.
4. **Retrieval is stateless.**

> RAG often fails because it stores text and discards custody.

---

## 2. The four laws

### Law 1 — append-only

Entries and edges are never rewritten or deleted. Revision is supersession. Old ground remains inspectable; it loses current authority. Ground is never silently edited or unrooted — corrections supersede through another recorded authority act.

### Law 2 — everything is signed

Every entry carries who produced it. Unsigned inserts are refused.

### Law 3 — everything has ancestry

Every non-`pair` entry needs at least one origin edge. Pairs are the conversation heartbeat and may be roots.

### Law 4 — similarity cannot promote

Search may surface an entry. Only a recorded **authority act** (`root`) can make it ground. Arrival in `home` or `wild` never promotes.

---

## 3. Core concepts

### Entry

| Field | Role |
|-------|------|
| `id`, `created_at` | Identity and time |
| `jurisdiction` | *Why* here: `home` or `wild` (not a content type) |
| `bucket` | Kind at birth |
| `source` | Optional provenance (nullable) |
| `signature` | Who produced the text |
| `body`, `body_hash` | Verbatim text and SHA-256 at insert |
| `meta_json` | Optional metadata (`scroll_ptr` required on pairs, nest offsets, …) |

Status is derived:

| Status | Derived how |
|--------|-------------|
| ground | An `adoption_record` has `adopts` → entry; nothing supersedes it; not sealed (`current_ground`) |
| superseded | A `supersedes` edge points at it |
| sealed | Latest seals/unseals edge to it is `seals` |

### Root (in-place, optional)

Rooting records an `adoption_record` whose `adopts` edge points at the **existing** entry. No second “canon” body is minted. The same row becomes ground because the trail exists.

Use root when something **must stay true**. Casual chat need not root anything. A Forest with empty `current_ground` is complete.

Route promotion through `root_to_ground` (or your own gate). Praise ≠ root. The store records `adopting_signature` verbatim; authenticating the speaker is the host’s job.

### Supersession

Insert a new entry + `supersedes` → old + new `adoption_record`/`adopts` → new. Only current ground can be superseded. This is the correction path for wrong ground.

### Seal / unseal

Record inserts; FTS removes sealed bodies from the index. Sealed entries are refused by `open` / `read` / recall.

### Scrub

Write always goes through scrub. Scrub removes transport, protocol, and harness scaffolding. It must not silently alter the substantive claim. Transformative compression or interpretation must be stored as a separately attributed synthesis.

### Scroll / head

Not SQLite tables. One append-only **file** per session (`Scroll`). Head = current turn’s exact API context — append it; never dump the whole scroll into ordinary model context. `read_slice` refuses any range that covers the entire non-empty file; prefer `tail` for recent context.

Every **pair** must carry `meta_json.scroll_ptr` (`path` + `offset`, optional `hash`). Prefer `commit_turn(store, scroll, …)` which appends then writes the pointer. Scroll is **evidence**, not ordinary retrieval material. Access control, retention, redaction, and secret handling belong to the host.

### Recall packets (preview ≠ read)

Every scrap from `recall_similar` / `recall_side` / `around` **leads with** `jurisdiction` (`home`|`wild`) and carries a **bounded excerpt**. Unlabeled is a bug. Full body disclosure is `read`’s job. Default similar scope is `home`.

### Walk (`open` / `around` / `step` / `read`)

Walk grammar is defined in [`README.md`](README.md). Canonical verbs:

`recall_similar` → `open` → `around` → `step(in|out|next|prev)` → `read`

- **Discovery does not constitute reading.** Bounded previews only until `read`.
- One boundary at a time; no jumps.
- `next` / `prev` on pairs: forward / backward in time.
- Harness may log steps; do **not** mint entries from open/step/read. Deeper extracts may write `nests` children (`parent[start:end] == child`) when you materialize depth (`move(..., deeper=…)` interim).
- **Tickets prove continuity.** `open` mints an opaque ticket; `around` records disclosed routes on it; `step` spends the ticket and mints a new one; `read` requires a valid ticket. Fabricated positions are refused.

Soft `near` (open only from that set) is optional terrain — not shipped in 0.4. Interim `move` remains for edge/deeper/shallower; prefer `step` + `around`.

### Questions (optional)

`bucket='question'` + mycelium helpers. A Forest without questions is complete. Answering never promotes.

### Tool results and jurisdiction

Jurisdiction is *why* an entry is here — not a content type. `home` = made in this conversation’s stand; `wild` = brought in (tools, reference, imports).

Tool results write as **wild**. They do not change jurisdiction. An earned `read` of a wild entry pends a `cites` edge onto the next pair — it entered context whether or not it was “used.” Crossing into home as claimed knowledge is a separately attributed **synthesis** with an edge back to the wild source — not the raw tool result relocating.

---

## 4. Buckets (closed vocabulary)

`pair`, `draft`, `visitor_words`, `note`, `journal`, `hearsay`, `synthesis`, `inference`, `question`, `internet`, `import`, `adoption_record`, `sealing_record`, `unsealing_record`

Ceremony buckets (`*_record`) are written only by ceremonies.

---

## 5. Edge kinds

`spoken_in`, `responds_to`, `derived_from`, `adopts`, `supersedes`, `cites`, `seals`, `unseals`, `asks_about`, `feeds`, `answers`, `reopens`, `nests`

Ceremony kinds (`adopts`, `supersedes`, `seals`, `unseals`) only via ceremonies.

---

## 6. Public ops (reference wrapper)

| Op | Meaning |
|----|---------|
| `commit_turn` | Append scroll head + `write_pair` with `scroll_ptr` |
| `write` / `write_pair` | Scrub, insert, origin edges; pairs require `scroll_ptr` |
| `recall_similar` | FTS → jurisdiction-first **previews** |
| `recall_side` | Label host/alternate scraps (previews) |
| `open` | Mint ticket at bearing; unread |
| `around` | Lawful destinations — bounded previews with `routes` (disclosed on ticket) |
| `step` | One disclosed boundary: `in` \| `out` \| `next` \| `prev` |
| `read` | Current ticket position body only |
| `move` | *Interim:* neighbor / deeper / shallower (ticketed) |
| `root_to_ground` | Only public in-place authority act |
| `walk_back` | Current ground + signature → audit previews + scroll_ptr |
| `supersede` / `seal` / `unseal` | Ceremony writes |
| `Scroll.append` / `tail` / `read_slice` | Session evidence; `dump_all` and complete-file slices refused |

---

## 7. Hard cut

**0.4 does not open pre-0.4 stores.** No migrate path. Start a fresh database.

---

## 8. File drift

When ground also lives in a file, `check_file_drift` compares the file hash to the rooted entry behind an adoption record (whole-file). Multi-section partial adopt remains a known limitation.

---

## 9. Hostile tests

See [`tests/HOSTILE_CASES.md`](tests/HOSTILE_CASES.md). Build the refusals first.

---

## 10. Trust boundary

Forest does not authenticate speakers. It guarantees there is no *silent* path to authority: every claim to ground is a recorded, attributed, immutable act. Public rooting goes only through `root_to_ground`.
