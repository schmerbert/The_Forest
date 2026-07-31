# mycelium — optional question network (host layer). Not required for a Forest.
#
# Stores: question entries and feeds/answers/reopens edges
# Refuses: planting on nothing, feeding or answering a sealed question
# Returns: question id on plant; fruiting questions near a set of entries
# Test: tests/test_mycelium.py

from __future__ import annotations

from typing import Iterable, Sequence

from forest_memory.core import ForestError, ForestStore

ASKS_ABOUT = "asks_about"
FEEDS = "feeds"
ANSWERS = "answers"
REOPENS = "reopens"


def plant_question(
    store: ForestStore,
    *,
    body: str,
    about_ids: Sequence[int],
    signature: str = "model",
) -> int:
    if not about_ids:
        raise ForestError("a question grows next to something; about_ids is empty")
    return store.write(
        body=body,
        bucket="question",
        signature=signature,
        origins=[(about_id, ASKS_ABOUT) for about_id in about_ids],
        scrub=None,
    )


def _refuse_sealed(store: ForestStore, question_id: int, act: str) -> None:
    row = store.get(question_id)
    if row is None or row["bucket"] != "question":
        raise ForestError(f"entry {question_id} is not a question")
    if store.is_sealed(question_id):
        raise ForestError(f"question {question_id} is sealed; {act} refused")


def feed_question(store: ForestStore, *, question_id: int, entry_id: int) -> None:
    _refuse_sealed(store, question_id, "feeding")
    store.add_edge(entry_id, question_id, FEEDS)
    store.conn.commit()


def answer_question(store: ForestStore, *, question_id: int, entry_id: int) -> None:
    """Mark answered. Does NOT promote — root remains the only path to ground."""
    _refuse_sealed(store, question_id, "answering")
    store.add_edge(entry_id, question_id, ANSWERS)
    store.conn.commit()


def reopen_question(store: ForestStore, *, question_id: int, entry_id: int) -> None:
    _refuse_sealed(store, question_id, "reopening")
    store.add_edge(entry_id, question_id, REOPENS)
    store.conn.commit()


def is_open(store: ForestStore, question_id: int) -> bool:
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
        question = store.get(qid)
        result.append(
            {"question": question, "ripeness": ripeness, "next_to": sorted(neighbors)}
        )
    result.sort(key=lambda f: (-f["ripeness"], f["question"]["id"]))
    return result
