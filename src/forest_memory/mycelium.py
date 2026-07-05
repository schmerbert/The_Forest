# mycelium — question network under the forest floor (host layer).
#
# Stores: question entries and feeds/answers/reopens edges (nothing new in schema)
# Refuses: planting on nothing, feeding or answering a sealed question
# Returns: question id on plant; fruiting questions near a set of entries
# Test: tests/test_mycelium.py
#
# Questions are mycelium: an underground network attached to the entries it
# grew from. They never appear in FTS retrieval on their own — they FRUIT,
# surfacing next to a node when a search disturbs soil they are attached to,
# ripest (most fed) first.
#
# State is derived, never stored, in the same way as sealing: a question is
# answered because the latest answers/reopens edge says so. And answering
# never promotes — if an answer deserves ground, the authority-holder routes
# it through ceremony.adopt_to_ground like any other text.

from __future__ import annotations

import sqlite3
from typing import Iterable, Sequence

from forest_memory.core import ForestError, ForestStore

# Edge vocabulary. None of these are ceremony kinds; they carry no status.
ASKS_ABOUT = "asks_about"  # question -> entry it grew next to
FEEDS = "feeds"            # entry -> question it nourishes
ANSWERS = "answers"        # entry -> question it answers
REOPENS = "reopens"        # entry -> question it reopens


def plant_question(
    store: ForestStore,
    *,
    body: str,
    about_ids: Sequence[int],
    signature: str = "model",
) -> int:
    """Plant a question next to the entries it grew from.

    A question is never a root: it grows out of specific material, and the
    asks_about edges are where its mushrooms will fruit.
    """
    if not about_ids:
        raise ForestError("a question grows next to something; about_ids is empty")
    return store.insert_entry(
        body=body,
        bucket="question",
        signature=signature,
        origins=[(about_id, ASKS_ABOUT) for about_id in about_ids],
    )


def _refuse_sealed(store: ForestStore, question_id: int, act: str) -> None:
    row = store.conn.execute(
        "SELECT bucket FROM entries WHERE id = ?", (question_id,)
    ).fetchone()
    if row is None or row["bucket"] != "question":
        raise ForestError(f"entry {question_id} is not a question")
    if store.is_sealed(question_id):
        raise ForestError(f"question {question_id} is sealed; {act} refused")


def feed_question(store: ForestStore, *, question_id: int, entry_id: int) -> None:
    """Record that an entry nourishes an open question. Each feed is ripeness."""
    _refuse_sealed(store, question_id, "feeding")
    store.add_edge(entry_id, question_id, FEEDS)
    store.conn.commit()


def answer_question(store: ForestStore, *, question_id: int, entry_id: int) -> None:
    """Mark a question answered by an entry.

    Derived state only — the question's row never changes. This does NOT
    promote the answering entry; adoption remains the only path to ground.
    """
    _refuse_sealed(store, question_id, "answering")
    store.add_edge(entry_id, question_id, ANSWERS)
    store.conn.commit()


def reopen_question(store: ForestStore, *, question_id: int, entry_id: int) -> None:
    """Reopen an answered question; the reopening entry says why."""
    _refuse_sealed(store, question_id, "reopening")
    store.add_edge(entry_id, question_id, REOPENS)
    store.conn.commit()


def is_open(store: ForestStore, question_id: int) -> bool:
    """A question is open unless the latest answers/reopens edge is an answer."""
    latest = store.conn.execute(
        """
        SELECT kind FROM edges WHERE to_id = ? AND kind IN (?, ?)
        ORDER BY id DESC LIMIT 1
        """,
        (question_id, ANSWERS, REOPENS),
    ).fetchone()
    return latest is None or latest["kind"] == REOPENS


def fruits_near(
    store: ForestStore,
    entry_ids: Iterable[int],
    *,
    min_ripeness: int = 0,
) -> list[dict]:
    """Return the open questions fruiting next to a set of entries.

    Call this with the ids of search results (or any nodes being read): the
    questions attached to those entries — planted on them (asks_about) or fed
    by them (feeds) — surface alongside, ripest first. Sealed and answered
    questions do not fruit.

    Each fruit is {"question": row, "ripeness": feed_count, "next_to": [ids]}.
    """
    ids = list(entry_ids)
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    fruits: dict[int, set[int]] = {}
    attached = store.conn.execute(
        f"""
        SELECT q.id AS qid, a.to_id AS neighbor
        FROM entries q
        JOIN edges a ON a.from_id = q.id AND a.kind = '{ASKS_ABOUT}'
        WHERE q.bucket = 'question' AND a.to_id IN ({placeholders})
          AND q.id NOT IN (SELECT id FROM sealed_entries)
        UNION
        SELECT q.id AS qid, f.from_id AS neighbor
        FROM entries q
        JOIN edges f ON f.to_id = q.id AND f.kind = '{FEEDS}'
        WHERE q.bucket = 'question' AND f.from_id IN ({placeholders})
          AND q.id NOT IN (SELECT id FROM sealed_entries)
        """,
        (*ids, *ids),
    ).fetchall()
    for row in attached:
        fruits.setdefault(row["qid"], set()).add(row["neighbor"])

    result = []
    for qid, neighbors in fruits.items():
        if not is_open(store, qid):
            continue
        ripeness = store.conn.execute(
            "SELECT COUNT(*) AS n FROM edges WHERE to_id = ? AND kind = ?",
            (qid, FEEDS),
        ).fetchone()["n"]
        if ripeness < min_ripeness:
            continue
        question = store.conn.execute(
            "SELECT * FROM entries WHERE id = ?", (qid,)
        ).fetchone()
        result.append(
            {"question": question, "ripeness": ripeness, "next_to": sorted(neighbors)}
        )
    result.sort(key=lambda f: (-f["ripeness"], f["question"]["id"]))
    return result
