# Forest

**A spec for AI memory that tracks where text came from — not just what sounds similar.**

RAG stores chunks and retrieves by cosine similarity. That breaks down when you need to know whether a sentence was **said by the user**, **guessed by the model**, **superseded**, **rejected**, or merely **related**.

Forest is a small **constitution** (`FOREST.md`) plus a **SQLite schema** (`schema.sql`) that stores custody with the text.

> **Similarity can retrieve. Similarity cannot promote.**

This repo is the canonical spec. Copy the schema into your project, implement the ceremonies in your app, and optionally use the Python reference wrapper to see how it works.

---

## Start here

**Most adopters** — copy the spec, no install:

```bash
git clone https://github.com/schmerbert/The_Forest.git
cp The_Forest/schema.sql your-project/woods/schema.sql
```

Then read [`FOREST.md`](FOREST.md) and wire adoption/supersession/sealing in your application.

**Developers** — run the reference wrapper and hostile tests:

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

## What's in the repo

| Artifact | What it is |
|----------|------------|
| [`FOREST.md`](FOREST.md) | The constitution — **read this first** |
| [`schema.sql`](schema.sql) | Enforced rules: CHECK constraints, append-only trigger, sealed-entry exclusion |
| [`src/forest_memory/`](src/forest_memory/) | Minimal Python reference (not a framework) |
| [`examples/`](examples/) | Writer, research, and codebase adoption stories |
| [`tests/`](tests/) | Hostile tests — refusals the spec requires, run as code |

**v0.1 includes:** insert discipline, adoption, supersession, sealing, search + retrieval log, ceremony gates, file drift checks.

**v0.1 does not include:** embeddings, autonomous retrieval, or agent orchestration. Add those only when the core schema starts to hurt.

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

```python
from forest_memory import ForestStore, adopt_to_ground

with ForestStore("woods.db") as store:
    store.init_schema()

    pair = store.insert_pair("Her brother's name is Elias.")
    draft = store.insert_entry(
        body="Maybe Elias betrayed her.",
        bucket="inference",
        signature="model",
        authority="inference",
        origins=[(pair, "derived_from")],
    )

    # Retrieval yes. Promotion no — until the authority-holder adopts.
    assert store.search("Elias")

    adopt_to_ground(
        store,
        adopted_entry_id=draft,
        body="Elias betrayed her in winter.",
        adopting_words="Yes — adopt this as canon.",
    )
```

If you use the Python wrapper: route promotion through `adopt_to_ground` (not `ForestStore.adopt()` directly), and use the `current_ground` view for authoritative truth — `search()` may still return superseded history.

---

## Hostile tests

Forest only works if it refuses the usual shortcuts — unsigned inserts, praise mistaken for adoption, sealed text leaking back, silent file edits after adoption. See [`tests/HOSTILE_CASES.md`](tests/HOSTILE_CASES.md).

| Layer | Enforced by |
|-------|-------------|
| Constitutional | `schema.sql` + `ForestStore` |
| Ceremonial | `adopt_to_ground` (your app must call a gate like this) |
| Drift | `check_file_drift` when ground also lives in files |

17 tests. All should pass before you trust a fork.

---

## Downstream projects

- **[The Inn (The Dog-Ear)](https://github.com/schmerbert/The_Inn)** — a writer tool that implements this schema
- Any other project: copy `schema.sql`, keep it identical, build your own ceremonies

When this schema changes, downstream repos should sync from `schema.sql` here.

---

## License

MIT — see [`LICENSE`](LICENSE). The spec is meant to be copied.

---

*Build the refusals first. Beauty is allowed after the floor holds weight.*
