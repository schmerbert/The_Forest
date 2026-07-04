# Contributing

Forest is a constitution first and a Python reference second. Changes should preserve that order.

## Before you open a PR

1. Read [`FOREST.md`](FOREST.md) — the rules are the product
2. Run the hostile suite: `pip install -e ".[test]" && pytest -q`
3. If you change `schema.sql`, update `src/forest_memory/schema.sql` to match (the sync test enforces this)

## What belongs here

- Constitutional changes (`schema.sql`, `FOREST.md`)
- Reference-wrapper behavior that demonstrates or enforces the constitution
- Hostile tests that map to [`tests/HOSTILE_CASES.md`](tests/HOSTILE_CASES.md)

## What does not belong in v0.x

- Embeddings, wander, mycelium, or agent orchestration
- Framework abstractions over the store
- Features that promote text without an explicit authority ceremony

Add machinery when the boring core hurts, not before.

## Pull requests

- One logical change per PR when possible
- Update `CHANGELOG.md` under **Unreleased** (or the target version section)
- CI must pass on Python 3.10–3.13, Ubuntu and Windows

## Releases

Maintainers follow [`RELEASING.md`](RELEASING.md). Contributors do not need to tag or publish.
