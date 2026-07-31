# Forest

<img
  width="300"
  alt="The Forest — a bounded woods under glass"
  src="https://github.com/user-attachments/assets/202dc43d-9dc3-48a5-b87d-a53868d8279a"
/>

**Custody-shaped memory for people (and models) building their own harnesses.**

Forest is a SQLite DB layer + the physics to wire it — not a chat app, not an agent framework, not “better RAG in a box.” It sits *under* your harness.

It keeps what happened, stores what you write (scrubbed), returns short related context with **jurisdiction labeled** (`home` | `wild`), and refuses to treat anything as true until someone **roots** it — so you can open a ticket and move through related territory instead of dumping history into the model.

> **Similarity can retrieve. Similarity cannot promote. Root is optional — and sparing.**

**This README is the ops contract** (axes, walk, packets, loop).  
**Schema / ceremony depth:** [`FOREST.md`](FOREST.md). **Enforced law:** [`schema.sql`](schema.sql). **Refusals:** [`tests/HOSTILE_CASES.md`](tests/HOSTILE_CASES.md).

Naming is clinical by default. The Python API names below are canonical (`recall_similar`, not `recall.similar`).

---

## Install

```bash
pip install forest-custody-memory
```

```python
from forest_memory import ForestStore, Scroll, commit_turn, hash_body, root_to_ground

with ForestStore("woods.db") as store:
    store.init_schema()
    scroll = Scroll("session.scroll")

    # Canonical heartbeat: append exact head + write pair with scroll_ptr.
    pair = commit_turn(store, scroll, "Her brother's name is Elias.")

    draft = store.write(
        body="Maybe Elias betrayed her.",
        bucket="inference",
        signature="model",
        origins=[(pair, "derived_from")],
    )

    # Bounded preview — jurisdiction first. Full body is read(), not recall.
    scraps = store.recall_similar("Elias")  # default scope: home
    assert scraps[0]["jurisdiction"] == "home"
    assert "excerpt" in scraps[0] and "body" not in scraps[0]

    trail = store.open(pair)           # mints opaque ticket; unread
    around = store.around(trail)       # discloses routes onto the ticket
    trail = store.step(trail, "in", target=draft)  # spends ticket; new ticket
    body = store.read(trail)           # current layer only; ticket required

    # Optional: adopt the *exact* entry body as written (hash = compare-and-root).
    # Adopting words are the authority act — not a replacement canon.
    root_to_ground(
        store,
        entry_id=draft,
        adopting_words="Yes — root this entry exactly as displayed.",
        adopting_signature="author",  # your harness authenticates this
        expected_body_hash=hash_body("Maybe Elias betrayed her."),
    )
```

**Canonical ops:** `write` / `write_pair` / `commit_turn` · `recall_similar` / `recall_side` · `open` · `around` · `step` · `read` · `root_to_ground` · `walk_back` / `authority_report` · `Scroll.append`  
**Interim:** `move` (prefer `step` + `around`). **Optional, not shipped:** soft `near` (embeddings) — see host hybrid below.  
**Promotion gate:** only `root_to_ground` is public. The store’s trail write is internal (`_root`).  
**Porters:** [`PORTERS.md`](PORTERS.md) — mechanical “wrapper must enforce” list (SQL alone is not enough).

**0.4 is a hard cut.** Pre-0.4 databases are not opened — start fresh.

```bash
git clone https://github.com/schmerbert/The_Forest.git
cd The_Forest
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix:    source .venv/bin/activate
pip install -e ".[test]"
pytest -q
```

---

## Three axes — never merge them

| Axis | Question | Values |
|------|----------|--------|
| **jurisdiction** | *Why* is it here? | `home` (made in this conversation’s stand) \| `wild` (brought in) |
| **bucket** (+ optional **source**) | What kind? | `pair`, `note`, `inference`, `internet`, … |
| **ground?** | True for us yet? | Only if **rooted** — derived from the record trail, never a writable flag |

Jurisdiction is **not** a data type. It is the reason the entry is in the Forest. Once that seam is located, everything else separates cleanly.

`home` ≠ ground. `wild` ≠ false.

**Load-bearing invariants:**

- **Arrival never promotes.** Landing in home or wild does not make ground.
- **Similarity never promotes.** Recall surfaces leads; only **root** creates ground.
- **Ground is never silently edited or unrooted.** Corrections supersede through another recorded authority act.
- **Scroll is append-only evidence**, not ordinary retrieval material. Complete-scroll reads are refused. Every pair carries a required `scroll_ptr`. Host owns secrets / retention / redaction.
- **Write always goes through scrub.** Scrub strips transport/harness scaffolding; it must not silently rewrite the claim. Compression or interpretation is a separately attributed synthesis. Extension: pass `scrub=`; examples in [`examples/scrubs.py`](examples/scrubs.py).
- **Walk is ticketed (process-local).** `open` mints an opaque ticket on **this** `ForestStore` instance; `around` discloses routes onto it; `step` spends it and mints a new one; `read` requires a valid ticket. Fabricated positions are refused. **Contract: one long-lived store process per walk session** — tickets are not durable across `close()` / new connections / other processes. Keep the store open for the harness session; do not serialize tickets to a DB column and expect another process to honor them.
- **Wild access links the next pair.** An earned `read` of a wild entry pends a `cites` edge onto the next `write_pair` / `commit_turn` — it entered context whether or not the model “used” it. Pending cites clear on the next pair or when the store closes.

---

## The loop

```text
talk (harness)
  → commit_turn (scroll.append + write_pair with scroll_ptr)
  → tool / reference results → write as wild
  → (optional) attributed synthesis in home, edged back to the wild source
  → recall_similar / recall_side (bounded preview; jurisdiction first)
  → ignore, or open → around → step (in|out|next|prev) → read
  → wild reads pend cites onto the next pair
  → optional root_to_ground (or superseding root if correcting ground)
  → edges densen; optional mycelium may fruit beside what you touched
```

**Tool results → wild.** Crossing into home is a separately attributed synthesis with an edge back to the wild source — not relocating the raw tool row.

---

## Walk

One boundary at a time. No jumps. Discovery is not reading. Continuity is the **ticket**.

| Op | Text visible |
|----|--------------|
| **`recall_similar` / `recall_side`** | Bounded preview only (jurisdiction-first excerpt). Not the body. Not a read. |
| **`open`** | No additional text — mints ticket at position (unread). |
| **`around`** | Bounded previews of lawful destinations. Records `routes` on the ticket. |
| **`step(direction, target?)`** | One step along a **disclosed** route; spends ticket; returns new ticket. |
| **`read`** | Body of the **current** ticket position only. |

```text
recall → bearings (bounded preview)
              │ choose one
              ▼
         open          (mint ticket; unread)
              │
              ▼
         around        (bounded previews + routes → ticket)
              │
              ▼
         step in|out|next|prev   (exactly one disclosed boundary)
              │
              ▼
         read          (current layer body only; ticket required)
```

**Pairs as territory:** consecutive pairs linked with `responds_to` (via `write_pair(..., previous_pair_id=…)`) are lawful lateral steps. **`next` = forward in time; `prev` = backward.**

**Dolls / nests:** optional verbatim extracts (`parent[start:end] == child`) via interim `move(..., deeper=…)`. Soft `near` (open only from an embedding neighborhood) is named but **not shipped** in 0.4.

### Host hybrid retrieval (FTS + your ranker)

Pure FTS is intentionally thin. A custody-safe pattern when you want embeddings:

1. Run your vector / hybrid ranker **outside** Forest → get candidate entry ids.
2. Pass them through `recall_side([{ "id": n }, …])` (or open only those ids) so every scrap is still a **jurisdiction-first bounded preview**.
3. Only then `open` → `around` → `step` → `read`. Similarity still never promotes.

Do not inject full bodies from your ranker into the model and call it “recall.”

---

## Packet rule

Every scrap from `recall_*` or `around` **must lead with** `jurisdiction` (`home` \| `wild`) before id or excerpt. Unlabeled is a bug. Previews are bounded excerpts; full body is `read`’s job.

```json
{
  "jurisdiction": "home",
  "id": 41,
  "excerpt": "…",
  "routes": [{ "direction": "in", "relation": "derived_from" }]
}
```

Default `recall_similar` scope is **home**.

---

## Data model (plain)

| Piece | What it is |
|-------|------------|
| **`entries`** | Stored text (`jurisdiction`, `bucket`, optional `source`, `signature`, `body`, `body_hash`, …) |
| **`edges`** | Ancestry, cites, adopts, consecutive pairs, nests, … — neighbors to step to |
| **`scroll`** | Append-only session file: exact API turns (`head` = live tip). Host custody. |
| **`pair`** | One cleaned user+model turn in `entries` (home) — the heartbeat; **requires `scroll_ptr`** |
| **mycelium** | **Optional.** Questions via `plant_question` / `feed_question` / `answer_question` / `fruits_near`. Answering never promotes. A Forest without questions is complete. |

`current_ground` is a view over adoption + supersession edges — not a status column.

---

## Operations

| Op | Meaning |
|----|---------|
| **`commit_turn`** | Append head to scroll + `write_pair` with `scroll_ptr`. Preferred heartbeat. |
| **`write` / `write_pair`** | Scrub, insert, origin edges as required. Pairs require `scroll_ptr`. |
| **`recall_similar`** | FTS bearings → bounded previews. Scope: `home` / `wild` / `both`. |
| **`recall_side`** | Label host-supplied / alternate-equation scraps as previews. |
| **`open` / `around` / `step` / `read`** | Ticketed walk (above). |
| **`move`** | *Interim:* neighbor by edge, or deeper/shallower extract (ticketed). |
| **`root_to_ground`** | Only public promotion gate → in-place authority act. |
| **`walk_back`** | Gated audit of **current ground** (signature required): previews + `scroll_ptr`. |
| **`authority_report`** | Host debug/UI custody status for **any** entry — previews + status flags + `body_hash`; never full bodies; do not dump into model context. |
| **`supersede` / `seal` / `unseal`** | Ceremony writes. |
| **`Scroll.append` / `tail` / `read_slice`** | Session evidence; `dump_all` and complete-file slices refused. |

---

## Ceremony & concurrency

WAL mode is on; that is **not** a full multi-writer story.

- Prefer **one writer** (one harness process) per database file.
- Only the host-authenticated authority path should call `root_to_ground` / `supersede` / `seal` / `unseal`. Serialize ceremonies (mutex / queue) so two agents cannot race two supersedes of the same ground.
- The reference runs `root` / `supersede` under **`BEGIN IMMEDIATE`** and re-checks `is_ground` inside that lock — a concurrent second ceremony on the same target is **refused**, not silent last-write-wins. This is a regression wall, not a distributed lock service.
- Multi-agent readers are fine for recall/walk; do not let every agent mint roots.
- Tickets and `_pending_wild_access` are **per store instance** and are **cleared on `close()` / a new connection** — not shared across processes.

### `walk_back` vs `authority_report`

| Helper | Use when |
|--------|----------|
| **`walk_back`** | Auditing **current ground** only (refuses non-ground). Authority trail + `scroll_ptr`. |
| **`authority_report`** | Debugging **any** entry (ground, sealed, superseded, or plain). Adds `status` flags + `body_hash`. |

Both return **previews only** (excerpt / hash / status) — never full `body`. Do not dump either packet into model context; ticketed `read` when a body is required.

---

## What Forest guarantees / doesn’t

**Does:** no silent path to authority; append-only record; correction of ground only through superseding authority acts; scroll kept out of ordinary retrieval dumps (complete reads refused); pairs linked to scroll; walk does not mint receipt entries; preview ≠ read; forged tickets refused; jurisdiction-first packets; axes stay separable; wild reads cite into the next pair.

**Doesn’t:** ship your harness UI or agent loop; authenticate who rooted or who called audit ops; babysit bad `home`/`wild` stamps on write; own scroll secret policy; durable tickets across processes; ship embeddings (`near` is optional / host hybrid). Wire the doors once; [hostile tests](tests/HOSTILE_CASES.md) and [`PORTERS.md`](PORTERS.md) keep them from rotting.

**0.4 non-goals (do not expect these in this release):** durable/cross-process tickets; shipped `near` / embedding index; multi-section partial file drift; a runtime mutex helper beyond IMMEDIATE txn + docs; any soft promotion path.

---

## Why not Mem0 / Letta / MemGPT?

Those solve **retrieval**. Forest solves **custody**: whether text was ever treated as true, who said so, and whether authority agreed. FTS for leads, walk for territory, no agent loop in-box. Add embeddings and orchestration when the core starts to hurt.

**Worth trying if** you’re building a harness and wrong long-lived “facts” are costly. **Skip if** you want turnkey “install and it remembers,” or only a vector store.

---

## Hostile tests

| Layer | Enforced by |
|-------|-------------|
| Constitutional | `schema.sql` + `ForestStore` |
| Ceremonial | `root_to_ground` (only public root) |
| Drift | `check_file_drift` when ground also lives in files |
| Scroll | `Scroll.dump_all` / complete `read_slice` refused; `scroll_ptr` on pairs |

See [`tests/HOSTILE_CASES.md`](tests/HOSTILE_CASES.md). Tour: [`examples/walkthrough.py`](examples/walkthrough.py).

---

## Copying the spec

```bash
git clone https://github.com/schmerbert/The_Forest.git
cp The_Forest/schema.sql your-project/woods/schema.sql
```

**Do not ship `schema.sql` without an insert wrapper.** Use [`src/forest_memory/`](src/forest_memory/) as the reference. Follow [`PORTERS.md`](PORTERS.md). Align to this README.

### Schema evolution (after 0.4)

`forest_meta.schema_version` is the gate. **0.4 is a hard cut** (no migrate from 0.3).

Going forward:

- **Additive, non-breaking** (same major mental model): new optional tables, new *non-ceremony* edge kinds / buckets via a documented migrate that widens CHECKs, new wrapper helpers — bump minor (`0.4.x` / `0.5.0`) and ship `migrate_0x_to_0y` when the on-disk shape changes.
- **Hard cut again** when status would become mutable, jurisdiction/packet rules weaken, or old stores cannot be opened safely — refuse old `schema_version` like 0.4 did.

Porters: never open a store whose `forest_meta.schema_version` you do not explicitly support.

---

## Related projects

- [The Inn](https://github.com/schmerbert/The_Inn) — long-form writing environment on this schema family
- [TheMarble](https://github.com/schmerbert/TheMarble) — inheritable environments / session handoff

---

## License

MIT — see [`LICENSE`](LICENSE).

---

*`commit_turn` · `recall_similar` · `open` / `around` / `step` / `read` · `root_to_ground` sparingly*
