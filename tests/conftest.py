# Shared test helpers — pairs always carry a real scroll_ptr via commit_turn.

from __future__ import annotations

from pathlib import Path

from forest_memory import ForestStore, Scroll, commit_turn


def make_store(tmp_path: Path) -> ForestStore:
    s = ForestStore(tmp_path / "forest.db")
    s.init_schema()
    return s


def make_scroll(tmp_path: Path, name: str = "session.scroll") -> Scroll:
    return Scroll(tmp_path / name)


def linked_pair(
    store: ForestStore,
    tmp_path: Path,
    user_text: str,
    assistant_text: str = "",
    **kwargs,
) -> int:
    """Write a pair linked to a scroll beside the store (canonical heartbeat)."""
    scroll = make_scroll(tmp_path)
    return commit_turn(store, scroll, user_text, assistant_text, **kwargs)
