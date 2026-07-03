# Forest

**Custody-first append-only memory for AI systems.**

Most memory stacks store text and retrieve by similarity. That works until you need to know whether a retrieved sentence was **authored**, **guessed**, **superseded**, **rejected**, or merely **adjacent**.

Forest is the missing layer: a small constitution + SQLite schema that stores **custody with the text**.

> **Similarity can retrieve. Similarity cannot promote.**

This repository is the **canonical spec**. Implementations (writer marbles, research notebooks, agent hosts) give it a face. The face needs Forest to stay honest; Forest does not need the face to work.

---

## What you get

| Artifact | Role |
|----------|------|
| [`FOREST.md`](FOREST.md) | The constitution — read this first |
| [`schema.sql`](schema.sql) | Enforced rules: CHECK constraints, append-only trigger, sealed FTS exclusion |
| [`src/forest_memory/`](src/forest_memory/) | Minimal Python reference (not a framework) |
| [`examples/`](examples/) | Writer, research, and codebase adoption stories |
| [`tests/`](tests/) | Hostile tests — the law, executable |

**v0.1 ships:** insert discipline, adoption, supersession, sealing, search + retrieval log, ceremony gates, file drift checks.

**v0.1 does not ship:** embeddings, wander, mycelium machinery, traverse automation. Those are cables — add them when the boring core hurts.

---

## Quick start

### Copy the constitution (most adopters)

```bash
cp schema.sql your-project/woods/schema.sql
# Read FOREST.md. Implement ceremonies in your app.
```

### Run the reference wrapper

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix:    source .venv/bin/activate
pip install -e ".[test]"
pytest -q
```

**15 tests green** — constitutional refusals, ceremony refusals, drift detection.

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

**Promotion ceremony is not automatic.** Route adoption through `adopt_to_ground` (or your own gate). `ForestStore.adopt()` is a low-level constitutional write that skips ceremonial refusals — do not call it from production promotion paths.

**Search is not current ground.** `search()` may return superseded history. Use the `current_ground` view when you need authoritative truth.

---

## The four jobs

| Mechanism | Job |
|-----------|-----|
| **Buckets** | Scope what retrieval may return |
| **Search** | Find entry points (FTS + `retrieval_log`) |
| **Ancestry** | Certify where an entry came from |
| **Ceremony** | Record authority acts — adoption, supersession, sealing |

Chunk → embed → cosine → stuff context discards the first three and fakes the fourth. Forest refuses that.

---

## Hostile tests

Forest is useful only if it refuses the usual laundering paths. See [`tests/HOSTILE_CASES.md`](tests/HOSTILE_CASES.md).

| Layer | Enforced by |
|-------|-------------|
| Constitutional | `schema.sql` + `ForestStore` |
| Ceremonial | `ceremony.adopt_to_ground` (your app must call a gate like this) |
| Drift | `drift.check_file_drift` when ground also lives in files |

---

## Reference implementations

- **[The Inn (The Dog-Ear)](https://github.com/schmerbert/TheInn)** — writer's marble; `inn/forest.py` tracks this schema
- Copy `schema.sql` anywhere else — keep the constitution identical, build your own ceremonies

When the schema changes here, downstream repos should sync `woods/schema.sql` from this file.

---

## Releases

Tagged releases are published to [GitHub Releases](https://github.com/schmerbert/The-Forest/releases) and [PyPI](https://pypi.org/project/forest-custody-memory/) as `forest-custody-memory`.

```bash
pip install forest-custody-memory
```

Maintainers follow [`RELEASING.md`](RELEASING.md). Contributors see [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## Project layout

```text
FOREST.md                      Constitution
schema.sql                     Canonical schema (human-facing)
src/forest_memory/
  schema.sql                   Packaged copy (must match root)
  core.py                      ForestStore — insert, adopt, supersede, seal, search
  ceremony.py                  Promotion gates — praise ≠ adoption
  drift.py                     File vs adoption trail
examples/                      Adoption stories
tests/
  HOSTILE_CASES.md             Spec for the hostile suite
  test_constitutional.py       Schema + store refusals
  test_ceremony.py             Authority promotion refusals
  test_drift.py                Silent file edit detection
```

---

## License

MIT — see [`LICENSE`](LICENSE). The spec is meant to be copied.

---

*Schema yes, machinery later. Columns are cheap at birth and painful to retrofit. Build the refusals first; beauty is allowed after the floor holds weight.*
