from pathlib import Path

from forest_memory import ForestStore, check_file_drift


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
    record_id = s.insert_entry(
        body=original,
        bucket="adoption_record",
        signature="author",
        authority="record",
        origins=[(pair_id, "adopts")],
    )

    assert check_file_drift(canon_file, s, record_id) == []

    canon_file.write_text(original + "\nSomeone edited this silently.", encoding="utf-8")
    warnings = check_file_drift(canon_file, s, record_id)
    assert len(warnings) == 1
    assert "does not match adoption trail" in warnings[0]["text"]
