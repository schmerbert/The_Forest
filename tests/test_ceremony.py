import pytest

from forest_memory import CeremonyRefusal, ForestStore, adopt_to_ground


def store(tmp_path):
    s = ForestStore(tmp_path / "forest.db")
    s.init_schema()
    return s


AUTHOR_LINE = "She walked through the autumn leaves."
PARAPHRASE = "She strolled among fallen leaves in autumn."


def make_draft(s, body=AUTHOR_LINE):
    pair_id = s.insert_pair("draft the opening")
    return s.insert_entry(
        body=body,
        bucket="draft",
        signature="model",
        origins=[(pair_id, "spoken_in")],
    )


def test_praise_is_not_adoption(tmp_path):
    s = store(tmp_path)
    draft_id = make_draft(s)
    with pytest.raises(CeremonyRefusal, match="enthusiasm is not adoption"):
        adopt_to_ground(
            s,
            adopted_entry_id=draft_id,
            body=AUTHOR_LINE,
            adopting_words="oh, that's lovely",
            adopting_signature="author",
        )
    canon = s.conn.execute(
        "SELECT COUNT(*) AS n FROM entries WHERE bucket = 'canon'"
    ).fetchone()["n"]
    assert canon == 0


def test_paraphrase_refused_as_author_prose(tmp_path):
    s = store(tmp_path)
    draft_id = make_draft(s)
    with pytest.raises(CeremonyRefusal, match="verbatim"):
        adopt_to_ground(
            s,
            adopted_entry_id=draft_id,
            body=PARAPHRASE,
            adopting_words="Yes — shelve this as my words.",
            adopting_signature="author",
            source_verbatim=AUTHOR_LINE,
        )


def test_explicit_adoption_promotes_to_ground(tmp_path):
    s = store(tmp_path)
    draft_id = make_draft(s)
    adopt_to_ground(
        s,
        adopted_entry_id=draft_id,
        body=AUTHOR_LINE,
        adopting_words="Yes — shelve this as canon, dated today.",
        adopting_signature="author",
        source_verbatim=AUTHOR_LINE,
    )
    ground = list(s.conn.execute("SELECT body FROM current_ground"))
    assert [row["body"] for row in ground] == [AUTHOR_LINE]


def test_hearsay_does_not_enter_current_ground_without_adoption(tmp_path):
    s = store(tmp_path)
    pair_id = s.insert_pair("research the treaty year")
    hearsay_id = s.insert_entry(
        body="The treaty was signed in 1842.",
        forest="wild",
        bucket="hearsay",
        signature="source:archive",
        origins=[(pair_id, "cites")],
    )
    synthesis_id = s.insert_entry(
        body="The treaty year is probably 1842.",
        bucket="synthesis",
        signature="model",
        origins=[(hearsay_id, "derived_from")],
    )
    assert s.search("1842")
    ground_ids = {row["id"] for row in s.conn.execute("SELECT id FROM current_ground")}
    assert hearsay_id not in ground_ids
    assert synthesis_id not in ground_ids
    with pytest.raises(CeremonyRefusal, match="enthusiasm is not adoption"):
        adopt_to_ground(
            s,
            adopted_entry_id=synthesis_id,
            body="The treaty was signed in 1842.",
            adopting_words="sounds right",
            adopting_signature="author",
        )
