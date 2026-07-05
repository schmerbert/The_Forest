from pathlib import Path

from forest_memory import ForestStore, adopt_to_ground, check_file_drift


def store(tmp_path):
    s = ForestStore(tmp_path / "forest.db")
    s.init_schema()
    return s


def test_file_drift_detected_after_silent_edit(tmp_path):
    s = store(tmp_path)
    canon_file = Path(tmp_path) / "canon.md"
    original = "The treaty was signed in spring."
    canon_file.write_text(original, encoding="utf-8")

    pair_id = s.insert_pair("adoption ceremony")
    draft_id = s.insert_entry(
        body=original,
        bucket="draft",
        signature="model",
        origins=[(pair_id, "spoken_in")],
    )
    adopt_to_ground(
        s,
        adopted_entry_id=draft_id,
        body=original,
        adopting_words="Yes — adopt this file as canon.",
        adopting_signature="author",
        source_verbatim=original,
    )
    record_id = s.conn.execute(
        "SELECT id FROM entries WHERE bucket = 'adoption_record'"
    ).fetchone()["id"]

    assert check_file_drift(canon_file, s, record_id) == []

    canon_file.write_text(original + "\nSomeone edited this silently.", encoding="utf-8")
    warnings = check_file_drift(canon_file, s, record_id)
    assert len(warnings) == 1
    assert "does not match adoption trail" in warnings[0]["text"]
