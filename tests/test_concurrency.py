"""Concurrency / ceremony race walls.

Reference assumes one writer per DB. These tests are a regression wall against
silent last-write-wins leaving ambiguous ``current_ground``.
"""

from __future__ import annotations

import threading

import pytest

from conftest import linked_pair
from forest_memory import ForestError, ForestStore, root_to_ground


def _ground_note(tmp_path, body="original ground claim"):
    s = ForestStore(tmp_path / "forest.db")
    s.init_schema()
    pair_id = linked_pair(s, tmp_path, "anchor")
    note = s.write(
        body=body,
        bucket="note",
        signature="model",
        origins=[(pair_id, "derived_from")],
        scrub=None,
    )
    root_to_ground(
        s,
        entry_id=note,
        adopting_words="Yes — root this claim.",
        adopting_signature="author",
        expected_body_hash=s.get(note)["body_hash"],
    )
    s.close()
    return note


def test_concurrent_supersede_second_refused(tmp_path):
    """Two supersedes of the same ground: one wins; current_ground stays unambiguous.

    Documented policy: one writer. IMMEDIATE txn + in-transaction is_ground
    re-check must refuse the loser — not leave two live grounds.
    """
    old_id = _ground_note(tmp_path)
    db = tmp_path / "forest.db"
    barrier = threading.Barrier(2)
    results: list[tuple[str, object]] = []
    lock = threading.Lock()

    def worker(label: str, new_body: str) -> None:
        store = ForestStore(db)
        try:
            barrier.wait(timeout=5)
            new_id = store.supersede(
                old_id=old_id,
                new_body=new_body,
                adopting_words=f"Supersede as {label}.",
                adopting_signature="author",
            )
            with lock:
                results.append(("ok", new_id))
        except ForestError as exc:
            with lock:
                results.append(("refuse", str(exc)))
        finally:
            store.close()

    t1 = threading.Thread(target=worker, args=("A", "revised claim A"))
    t2 = threading.Thread(target=worker, args=("B", "revised claim B"))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    oks = [r for r in results if r[0] == "ok"]
    refuses = [r for r in results if r[0] == "refuse"]
    assert len(oks) == 1, f"expected exactly one success, got {results!r}"
    assert len(refuses) == 1, f"expected exactly one refusal, got {results!r}"
    assert "not current ground" in refuses[0][1]

    with ForestStore(db) as s:
        ground_ids = {
            r["id"] for r in s.conn.execute("SELECT id FROM current_ground")
        }
        assert old_id not in ground_ids
        assert oks[0][1] in ground_ids
        # No ambiguous dual successor of the same old ground.
        successors = [
            r["from_id"]
            for r in s.conn.execute(
                "SELECT from_id FROM edges WHERE to_id=? AND kind='supersedes'",
                (old_id,),
            )
        ]
        live = [sid for sid in successors if sid in ground_ids]
        assert len(live) == 1


def test_concurrent_root_same_entry_second_refused(tmp_path):
    """Two root_to_ground on the same entry: one wins; not double-adopted ambiguously."""
    db = tmp_path / "forest.db"
    with ForestStore(db) as s:
        s.init_schema()
        pair_id = linked_pair(s, tmp_path, "anchor")
        note = s.write(
            body="candidate",
            bucket="note",
            signature="model",
            origins=[(pair_id, "derived_from")],
            scrub=None,
        )
        body_hash = s.get(note)["body_hash"]

    barrier = threading.Barrier(2)
    results: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        store = ForestStore(db)
        try:
            barrier.wait(timeout=5)
            root_to_ground(
                store,
                entry_id=note,
                adopting_words="Yes — root this candidate.",
                adopting_signature="author",
                expected_body_hash=body_hash,
            )
            with lock:
                results.append("ok")
        except (ForestError, Exception) as exc:
            # CeremonyRefusal shouldn't fire; ForestError already ground / race.
            with lock:
                results.append(f"refuse:{exc}")
        finally:
            store.close()

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert results.count("ok") == 1, results
    assert sum(1 for r in results if r.startswith("refuse")) == 1, results

    with ForestStore(db) as s:
        assert s.is_ground(note)
        n_adopts = s.conn.execute(
            """
            SELECT COUNT(*) AS n FROM edges a
            JOIN entries r ON r.id = a.from_id
            WHERE a.to_id = ? AND a.kind = 'adopts' AND r.bucket = 'adoption_record'
            """,
            (note,),
        ).fetchone()["n"]
        assert n_adopts == 1
