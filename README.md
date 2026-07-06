# Forest

**AI memory that tracks where text came from — not just what sounds similar.**

RAG stores chunks and retrieves by cosine similarity. That breaks down when you need to know whether a sentence was **said by the user**, **guessed by the model**, **superseded**, **rejected**, or merely **related**.

Forest stores custody with the text: every entry carries a signature (who produced it), a bucket (what kind of text it is), and ancestry (where it came from). Status — ground, superseded, sealed — is derived from an append-only record trail, never stored as a flag that can be forged.

> **Similarity can retrieve. Similarity cannot promote.**

Forest is for systems where a wrong "fact" in memory is costly and long-lived: writing projects with a canon, research notes with citation standards, codebases with decisions that must not silently drift. See [`examples/`](examples/) for all three.

---

## Install

```bash
pip install forest-custody-memory
```

```python
from forest_memory import ForestStore, adopt_to_ground

with ForestStore("woods.db") as store:
    store.init_schema()

    pair = store.insert_pair("Her brother's name is Elias.")
    draft = store.insert_entry(
        body="Maybe Elias betrayed her.",
        bucket="inference",
        signature="model",
        origins=[(pair, "derived_from")],
    )

    # Retrieval yes. Promotion no — until the authority-holder adopts.
    assert store.search("Elias")

    adopt_to_ground(
        store,
        adopted_entry_id=draft,
        body="Elias betrayed her in winter.",
        adopting_words="Yes — adopt this as canon.",
        adopting_signature="author",  # who spoke — your app authenticates this
    )
```

Route promotion through `adopt_to_ground` (not `ForestStore.adopt()` directly), and read authoritative truth from the `current_ground` view — `search()` may still return superseded history.

To run the tests from source:

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

## How it works (60 seconds)

Every piece of stored text has:

| Mechanism | Job |
|-----------|-----|
| **Bucket** | What kind of text this is (canon, draft, inference, hearsay, …) |
| **Signature** | Who produced it (author, model, source, …) |
| **Ancestry** | Where it came from (origin edges back to a root) |
| **Ceremony** | Explicit authority acts — adoption, supersession, sealing |

Search can **find** text. Only a recorded ceremony can **promote** it to ground truth.

```text
session_pair ──► inference / draft ──► canon + adoption_record (one transaction)
                        │
                        └──► refused unless authority-holder adopts
```

The full rules live in [`FOREST.md`](FOREST.md) — the constitution — and [`schema.sql`](schema.sql), which enforces what SQL can enforce: immutable entries and edges, derived-status views, sealed-body FTS removal.

---

## Why not Mem0 / Letta / MemGPT?

Those solve **retrieval**: getting relevant text back into context. Forest solves **trust**: whether that text was ever true, who said so, and whether anyone with authority agreed. Existing memory frameworks store a memory's importance or confidence as a score — usually assigned by the model itself. Generative Agents (the Stanford "Smallville" paper) made this explicit: retrieval weighted by recency × relevance × *model-scored importance*. Nothing in that loop can distinguish "the user said this" from "the model decided this was important," and nothing can refuse a write.

Forest is the layer underneath: custody recorded at insert, promotion only by recorded ceremony, refusals enforced by schema and tested as code. It is deliberately not a framework — no embeddings, no autonomous retrieval, no agent orchestration in v0.3. Add those on top when the core schema starts to hurt.

---

## The audit that changed the schema

An external audit of v0.1 found that the promotion boundary could be forged: status lived in writable columns, so an attacker (or a confused agent) could set `status = 'ground'` directly and skip adoption entirely.

v0.2 removed the columns. Status is now **derived** from the append-only record trail — ground exists only because an adoption record exists. Forging ground requires inserting an adoption record, which *is* the ceremony. The seven exploits from that audit are preserved in the test suite as refusals.

If you copied the v0.1 schema, re-copy. Migration from any earlier store is one call — `migrate_to_latest(old_path, new_path)` — your original file is never written, and the store refuses to open outdated files rather than fail confusingly. Details in the [CHANGELOG](CHANGELOG.md).

---

## Hostile tests

Forest only works if it refuses the usual shortcuts — unsigned inserts, praise mistaken for adoption, sealed text leaking back, silent file edits after adoption. See [`tests/HOSTILE_CASES.md`](tests/HOSTILE_CASES.md).

| Layer | Enforced by |
|-------|-------------|
| Constitutional | `schema.sql` + `ForestStore` |
| Ceremonial | `adopt_to_ground` (your app must call a gate like this) |
| Drift | `check_file_drift` when ground also lives in files (whole-file in v0.3; see FOREST.md §9) |

57 tests, including the seven audit exploits as refusals. All should pass before you trust a fork.

---

## Copying the spec instead

Porting to another language, or building your own wrapper? The spec is meant to be copied — that's what the MIT license is for:

```bash
git clone https://github.com/schmerbert/The_Forest.git
cp The_Forest/schema.sql your-project/woods/schema.sql
```

**Do not ship `schema.sql` without an insert wrapper.** SQL defines the container; Forest rules require application-layer ceremony: signatures, ancestry, adoption, sealing, promotion gates, and retrieval logging. Read [`FOREST.md`](FOREST.md) first and use [`src/forest_memory/`](src/forest_memory/) as the reference implementation. When this schema changes, downstream copies should sync from `schema.sql` here.

**v0.3 includes:** insert discipline, adoption, supersession, sealing + unsealing, search + retrieval log (with result sets), ceremony gates, file drift checks, mycelium — open questions stored so they resurface next to the entries a search disturbs — and migration from any earlier store version. The Python package tracks the spec version.

---

## Related projects

- [The Inn](https://github.com/schmerbert/The_Inn) — a working memory environment for long-form writing, built on this schema
- [TheMarble](https://github.com/schmerbert/TheMarble) — inheritable environments for recurring AI work: persistent memory and session handoff across platforms

---

## License

MIT — see [`LICENSE`](LICENSE). The spec is meant to be copied.

---

*Build the refusals first. Beauty is allowed after the floor holds weight.*
