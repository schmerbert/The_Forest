# The schema ships twice: repo root (for reading/audit) and inside the
# package (what init_schema actually executes). They must never diverge.

from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_schema_copies_are_identical():
    public = (ROOT / "schema.sql").read_bytes()
    packaged = (ROOT / "src" / "forest_memory" / "schema.sql").read_bytes()
    assert public == packaged, (
        "schema.sql and src/forest_memory/schema.sql have diverged — "
        "copy the edited one over the other"
    )
