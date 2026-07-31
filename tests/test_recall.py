"""Recall: jurisdiction-first packets; root optional."""

import pytest

from conftest import linked_pair

from forest_memory import ForestError, ForestStore


def store(tmp_path):
    s = ForestStore(tmp_path / "forest.db")
    s.init_schema()
    return s


def test_root_optional_empty_ground_ok(tmp_path):
    s = store(tmp_path)
    linked_pair(s, tmp_path, "What events are coming up this weekend?")
    scraps = s.recall_similar("events")
    assert scraps
    assert all(sc["jurisdiction"] == "home" for sc in scraps)
    assert list(s.conn.execute("SELECT id FROM current_ground")) == []


def test_recall_similar_leads_with_jurisdiction(tmp_path):
    s = store(tmp_path)
    linked_pair(s, tmp_path, "I am going to the river festival.")
    wild = s.write(
        body="City calendar: river festival Saturday.",
        jurisdiction="wild",
        bucket="internet",
        source="example.com",
        signature="tool",
        origins=[(1, "cites")],
        scrub=None,
    )
    home = s.recall_similar("festival", scope="home")
    assert home and home[0]["jurisdiction"] == "home"
    assert list(home[0].keys())[0] == "jurisdiction"

    both = s.recall_similar("festival", scope="both")
    jurisdictions = {sc["jurisdiction"] for sc in both}
    assert jurisdictions == {"home", "wild"}
    assert wild in [sc["id"] for sc in both]


def test_recall_side_refuses_unlabeled(tmp_path):
    s = store(tmp_path)
    with pytest.raises(ForestError, match="unknown entry"):
        s.recall_side([{"id": 1}])

    pair = linked_pair(s, tmp_path, "hello festival")
    # id-only is filled from store — jurisdiction comes from the row
    labeled = s.recall_side([{"id": pair}])
    assert labeled[0]["jurisdiction"] == "home"

    with pytest.raises(ForestError, match="unlabeled"):
        s.recall_side([{"id": pair, "jurisdiction": "maybe", "excerpt": "x"}])


def test_recall_side_accepts_prelabeled(tmp_path):
    s = store(tmp_path)
    pair = linked_pair(s, tmp_path, "side channel")
    out = s.recall_side([
        {"jurisdiction": "wild", "id": pair, "excerpt": "helper hit"},
    ])
    assert out[0]["jurisdiction"] == "wild"
    assert out[0]["excerpt"] == "helper hit"


def test_default_scope_is_home(tmp_path):
    s = store(tmp_path)
    linked_pair(s, tmp_path, "home bees")
    s.write(
        body="wild bees elsewhere",
        jurisdiction="wild",
        bucket="hearsay",
        signature="source",
        origins=[(1, "cites")],
        scrub=None,
    )
    scraps = s.recall_similar("bees")
    assert all(sc["jurisdiction"] == "home" for sc in scraps)
    assert all("excerpt" in sc and "body" not in sc for sc in scraps)


def test_recall_refuses_unbounded_excerpt(tmp_path):
    s = store(tmp_path)
    linked_pair(s, tmp_path, "bees")
    with pytest.raises(ForestError, match="excerpt_len"):
        s.recall_similar("bees", excerpt_len=None)  # type: ignore[arg-type]
    with pytest.raises(ForestError, match="excerpt_len"):
        s.recall_similar("bees", excerpt_len=0)


def test_recall_side_refuses_body_without_excerpt(tmp_path):
    s = store(tmp_path)
    pair = linked_pair(s, tmp_path, "side")
    with pytest.raises(ForestError, match="full body refused"):
        s.recall_side([{"jurisdiction": "home", "id": pair, "body": "secret"}])


@pytest.mark.parametrize(
    "body,query",
    [
        ("Un café près de la gare.", "café"),
        ("A naïve résumé of the treaty.", "naïve"),
        ("Документ на русском языке.", "русском"),
        ("النص بالعربية هنا.", "بالعربية"),
        ("日本語のテスト文書です。", "日本語"),
    ],
)
def test_recall_unicode_tokens(tmp_path, body, query):
    s = store(tmp_path)
    linked_pair(s, tmp_path, body, scrub=None)
    scraps = s.recall_similar(query)
    assert scraps
    assert any(body[:12] in sc["excerpt"] or query in sc["excerpt"] for sc in scraps)


def test_recall_rejects_punctuation_only_keeps_words(tmp_path):
    s = store(tmp_path)
    linked_pair(s, tmp_path, "safe content about bees")
    with pytest.raises(ForestError, match="empty query"):
        s.recall_similar("!!! ??? ***")
    scraps = s.recall_similar("bees!!! ???")
    assert scraps
    # Quoted tokens — operator words alone must not inject raw FTS syntax
    from forest_memory.core import _plain_language_fts_query

    built = _plain_language_fts_query('bees OR nest; DROP')
    assert "OR" not in built or '"OR"' in built
    assert ";" not in built
    assert "DROP" in built  # becomes a quoted literal token, not an operator