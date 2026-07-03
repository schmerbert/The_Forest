"""Schema resolution — packaged wheel and dev checkout."""

from __future__ import annotations

from importlib import resources
from pathlib import Path


def load_schema_sql() -> str:
    """Return the bundled constitution SQL (works after pip install)."""
    return resources.files("forest_memory").joinpath("schema.sql").read_text(encoding="utf-8")


def dev_schema_path() -> Path:
    """Repo-root schema.sql for contributors running from a checkout."""
    return Path(__file__).resolve().parents[2] / "schema.sql"
