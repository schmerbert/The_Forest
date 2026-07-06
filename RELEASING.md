# Releasing Forest

Every public release follows the same checklist. Do not skip steps.

Forest ships on **GitHub** (the constitution — `FOREST.md`, `schema.sql` — is the product) and on **PyPI** as [`forest-custody-memory`](https://pypi.org/project/forest-custody-memory/) (the reference wrapper).

## Version numbers

The package version tracks the spec version. Keep these in sync before tagging:

- `pyproject.toml` → `[project].version`
- `src/forest_memory/__init__.py` → `__version__`
- `CHANGELOG.md` → new section with date

Tag format: `v0.3.0` (must match the version with a `v` prefix).

## One-time PyPI setup

Publishing uses [trusted publishing](https://docs.pypi.org/trusted-publishers/) — no API tokens stored anywhere.

1. On PyPI, add a **trusted publisher** for the project: owner `schmerbert`, repository `The_Forest`, workflow `release.yml`, environment `pypi`. (For the first release of a new project, use PyPI's "pending publisher" form.)
2. On GitHub, create an environment named `pypi` (Settings → Environments). Optionally require manual approval on it — that makes PyPI publishing a button press after the tag.

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

git tag -a v0.3.0 -m "v0.3.0"
git push origin main
git push origin v0.3.0
```

Pushing the tag triggers [`.github/workflows/release.yml`](.github/workflows/release.yml), which:

1. Runs the full hostile test suite
2. Builds the sdist and wheel
3. Creates a [GitHub Release](https://github.com/schmerbert/The_Forest/releases) with auto-generated notes and the built artifacts
4. Publishes to PyPI via trusted publishing (the `publish-pypi` job, gated on the `pypi` environment)

Do not upload local `dist/` builds by hand; the workflow builds fresh from the tagged commit.

## How adopters get Forest

Most adopters install the package:

```bash
pip install forest-custody-memory
```

Porters and spec adopters copy the spec — no install step:

```bash
git clone https://github.com/schmerbert/The_Forest.git
cp The_Forest/schema.sql your-project/woods/schema.sql
# Read FOREST.md. Implement ceremonies in your app.
```

## After release

- Verify `pip install forest-custody-memory==<version>` works in a clean venv
- Downstream repos (e.g. The Inn) should sync `woods/schema.sql` from this repo's `schema.sql`
- Announce the tag and link the GitHub Release notes
