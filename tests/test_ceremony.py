import pytest

from conftest import linked_pair

from forest_memory import CeremonyRefusal, ForestStore, hash_body, root_to_ground


def store(tmp_path):
    s = ForestStore(tmp_path / "forest.db")
    s.init_schema()
    return s


AUTHOR_LINE = "She walked through the autumn leaves."
PARAPHRASE = "She strolled among fallen leaves in autumn."


def make_draft(s, tmp_path, body=AUTHOR_LINE):
    pair_id = linked_pair(s, tmp_path, "draft the opening")
    return s.write(
        body=body,
        bucket="draft",
        signature="model",
        origins=[(pair_id, "spoken_in")],
        scrub=None,
    )


def test_praise_is_not_root(tmp_path):
    s = store(tmp_path)
    draft_id = make_draft(s, tmp_path)
    row = s.get(draft_id)
    with pytest.raises(CeremonyRefusal, match="enthusiasm is not root"):
        root_to_ground(
            s,
            entry_id=draft_id,
            adopting_words="oh, that's lovely",
            adopting_signature="author",
            expected_body_hash=row["body_hash"],
        )
    assert list(s.conn.execute("SELECT id FROM current_ground")) == []


def test_paraphrase_refused_as_author_prose(tmp_path):
    s = store(tmp_path)
    draft_id = make_draft(s, tmp_path)
    row = s.get(draft_id)
    with pytest.raises(CeremonyRefusal, match="verbatim"):
        root_to_ground(
            s,
            entry_id=draft_id,
            adopting_words="Yes — shelve this as my words.",
            adopting_signature="author",
            expected_body_hash=row["body_hash"],
            source_verbatim=PARAPHRASE,
        )


def test_explicit_root_promotes_in_place(tmp_path):
    s = store(tmp_path)
    draft_id = make_draft(s, tmp_path)
    row = s.get(draft_id)
    grounded = root_to_ground(
        s,
        entry_id=draft_id,
        adopting_words="Yes — shelve this as ground, dated today.",
        adopting_signature="author",
        expected_body_hash=row["body_hash"],
        source_verbatim=AUTHOR_LINE,
    )
    assert grounded == draft_id
    ground = list(s.conn.execute("SELECT id, body FROM current_ground"))
    assert [(row["id"], row["body"]) for row in ground] == [(draft_id, AUTHOR_LINE)]
    # No canon mint
    assert s.conn.execute(
        "SELECT COUNT(*) AS n FROM entries WHERE bucket = 'adoption_record'"
    ).fetchone()["n"] == 1
    assert s.conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"] == 3  # pair+draft+record


def test_hearsay_does_not_enter_current_ground_without_root(tmp_path):
    s = store(tmp_path)
    pair_id = linked_pair(s, tmp_path, "research the treaty year")
    hearsay_id = s.write(
        body="The treaty was signed in 1842.",
        jurisdiction="wild",
        bucket="hearsay",
        signature="source:archive",
        origins=[(pair_id, "cites")],
        scrub=None,
    )
    synthesis_id = s.write(
        body="The treaty year is probably 1842.",
        bucket="synthesis",
        signature="model",
        origins=[(hearsay_id, "derived_from")],
        scrub=None,
    )
    assert s.recall_similar("1842", scope="both")
    ground_ids = {row["id"] for row in s.conn.execute("SELECT id FROM current_ground")}
    assert hearsay_id not in ground_ids
    assert synthesis_id not in ground_ids
    row = s.get(synthesis_id)
    with pytest.raises(CeremonyRefusal, match="enthusiasm is not root"):
        root_to_ground(
            s,
            entry_id=synthesis_id,
            adopting_words="sounds right",
            adopting_signature="author",
            expected_body_hash=row["body_hash"],
        )
