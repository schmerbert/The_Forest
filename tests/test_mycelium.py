# Optional mycelium: questions fruit next to nodes. Answering never promotes.

import pytest

from conftest import linked_pair

from forest_memory import ForestError, ForestStore, root_to_ground
from forest_memory.mycelium import (
    answer_question,
    feed_question,
    fruits_near,
    is_open,
    plant_question,
    reopen_question,
)


def store(tmp_path):
    s = ForestStore(tmp_path / "forest.db")
    s.init_schema()
    return s


def grow(s, tmp_path):
    pair_id = linked_pair(s, tmp_path, "Tell me about Elias.")
    node = s.write(
        body="Elias left the village before the war.",
        bucket="note",
        signature="model",
        origins=[(pair_id, "spoken_in")],
        scrub=None,
    )
    other = s.write(
        body="The river floods in spring.",
        bucket="note",
        signature="model",
        origins=[(pair_id, "spoken_in")],
        scrub=None,
    )
    q = plant_question(s, body="Why did Elias leave?", about_ids=[node])
    return pair_id, node, other, q


def test_question_fruits_next_to_its_node_only(tmp_path):
    s = store(tmp_path)
    pair, node, other, q = grow(s, tmp_path)

    fruits = fruits_near(s, [node])
    assert [f["question"]["id"] for f in fruits] == [q]
    assert fruits[0]["next_to"] == [node]

    assert fruits_near(s, [other]) == []


def test_feeding_raises_ripeness_and_ripest_fruits_first(tmp_path):
    s = store(tmp_path)
    pair, node, other, q = grow(s, tmp_path)
    q2 = plant_question(s, body="Where is the village?", about_ids=[node])

    snack = s.write(
        body="A letter mentions a debt Elias owed.",
        bucket="hearsay",
        signature="source:letter",
        origins=[(pair, "spoken_in")],
        scrub=None,
    )
    feed_question(s, question_id=q, entry_id=snack)

    fruits = fruits_near(s, [node])
    assert [f["question"]["id"] for f in fruits] == [q, q2]
    assert fruits[0]["ripeness"] == 1
    assert [f["question"]["id"] for f in fruits_near(s, [snack])] == [q]
    assert [f["question"]["id"] for f in fruits_near(s, [node], min_ripeness=1)] == [q]


def test_answered_questions_stop_fruiting_until_reopened(tmp_path):
    s = store(tmp_path)
    pair, node, other, q = grow(s, tmp_path)
    answer = s.write(
        body="He left to escape the debt.",
        bucket="synthesis",
        signature="model",
        origins=[(pair, "spoken_in")],
        scrub=None,
    )
    answer_question(s, question_id=q, entry_id=answer)
    assert not is_open(s, q)
    assert fruits_near(s, [node]) == []

    doubt = s.write(
        body="The debt was repaid years earlier; the motive fails.",
        bucket="note",
        signature="model",
        origins=[(pair, "spoken_in")],
        scrub=None,
    )
    reopen_question(s, question_id=q, entry_id=doubt)
    assert is_open(s, q)
    assert [f["question"]["id"] for f in fruits_near(s, [node])] == [q]


def test_sealed_questions_do_not_fruit_and_refuse_acts(tmp_path):
    s = store(tmp_path)
    pair, node, other, q = grow(s, tmp_path)
    s.seal(entry_id=q, quote="Seal this line of questioning.")
    assert fruits_near(s, [node]) == []
    with pytest.raises(ForestError, match="sealed"):
        feed_question(s, question_id=q, entry_id=node)


def test_plant_refuses_rootless_and_non_questions_refused(tmp_path):
    s = store(tmp_path)
    pair, node, other, q = grow(s, tmp_path)
    with pytest.raises(ForestError, match="about_ids is empty"):
        plant_question(s, body="Growing on nothing?", about_ids=[])
    with pytest.raises(ForestError, match="not a question"):
        answer_question(s, question_id=node, entry_id=other)


def test_answering_never_promotes(tmp_path):
    s = store(tmp_path)
    pair, node, other, q = grow(s, tmp_path)
    answer = s.write(
        body="He left to escape the debt.",
        bucket="synthesis",
        signature="model",
        origins=[(pair, "spoken_in")],
        scrub=None,
    )
    answer_question(s, question_id=q, entry_id=answer)
    assert not s.is_ground(answer)

    row = s.get(answer)
    grounded = root_to_ground(
        s,
        entry_id=answer,
        adopting_words="Yes — root this.",
        adopting_signature="author",
        expected_body_hash=row["body_hash"],
        source_verbatim="He left to escape the debt.",
    )
    assert grounded == answer
    assert s.is_ground(answer)
