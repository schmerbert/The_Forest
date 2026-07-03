# Releasing Forest

Every public release follows the same checklist. Do not skip steps.

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
pytest -q
python -m build
pip install dist/*.whl && pytest -q

git tag -a v0.1.0 -m "v0.1.0"
git push origin main
git push origin v0.1.0
```

Pushing the tag triggers [`.github/workflows/release.yml`](.github/workflows/release.yml), which:

1. Builds sdist + wheel
2. Runs the full hostile test suite against the wheel
3. Creates a GitHub Release with attached artifacts
4. Publishes to PyPI (when configured)

## PyPI setup (one time)

1. Create a PyPI project named `forest-custody-memory`
2. In PyPI → **Publishing** → **Add a new pending publisher**:
   - Owner: `schmerbert`
   - Repository: `The-Forest`
   - Workflow: `release.yml`
   - Environment: (leave blank unless you add one)
3. The release workflow uses OIDC trusted publishing — no long-lived API token required

Until PyPI trusted publishing is configured, the GitHub Release and wheel artifacts still publish; only the PyPI step will fail.

## After release

- Downstream repos (e.g. The Inn) should sync `woods/schema.sql` from this repo's `schema.sql`
- Announce the tag and link the GitHub Release notes
