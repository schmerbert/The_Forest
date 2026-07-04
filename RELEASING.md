# Releasing Forest

Every public release follows the same checklist. Do not skip steps.

Forest ships on **GitHub** — the constitution (`FOREST.md`, `schema.sql`) is the product. PyPI is optional and not used for now.

## Version numbers

Keep these in sync before tagging:

- `pyproject.toml` → `[project].version`
- `src/forest_memory/__init__.py` → `__version__`
- `CHANGELOG.md` → new section with date

Tag format: `v0.1.0` (must match the version with a `v` prefix).

## Pre-release checklist

1. All changes merged to `main`
2. CI green on the release commit
3. `CHANGELOG.md` updated
4. Version bumped in `pyproject.toml` and `__init__.py`
5. `schema.sql` and `src/forest_memory/schema.sql` still match (`pytest -q` enforces this)

## Cut a release

```bash
git checkout main
git pull
pip install -e ".[test]"
pytest -q

git tag -a v0.1.0 -m "v0.1.0"
git push origin main
git push origin v0.1.0
```

Pushing the tag triggers [`.github/workflows/release.yml`](.github/workflows/release.yml), which:

1. Runs the full hostile test suite
2. Creates a [GitHub Release](https://github.com/schmerbert/The_Forest/releases) with auto-generated notes

## How adopters get Forest

Most adopters copy the spec — no install step:

```bash
git clone https://github.com/schmerbert/The_Forest.git
cp The_Forest/schema.sql your-project/woods/schema.sql
# Read FOREST.md. Implement ceremonies in your app.
```

Developers who want the reference wrapper from a checkout:

```bash
git clone https://github.com/schmerbert/The_Forest.git
cd The_Forest
pip install -e ".[test]"
pytest -q
```

## PyPI (later, optional)

Not configured. If you add pip publishing across repos later, re-enable wheel build + `pypa/gh-action-pypi-publish` in `release.yml` and register trusted publishing on PyPI.

## After release

- Downstream repos (e.g. The Inn) should sync `woods/schema.sql` from this repo's `schema.sql`
- Announce the tag and link the GitHub Release notes
