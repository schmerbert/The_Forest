"""Scroll: append-only JSONL file; no whole-dump into context; bounded slices."""

import json

import pytest

from forest_memory import Scroll, ScrollError
from forest_memory.scroll import MAX_SLICE


def test_append_returns_byte_offset(tmp_path):
    scroll = Scroll(tmp_path / "s.scroll")
    off0 = scroll.append("first turn")
    assert off0 == 0
    off1 = scroll.append("second turn")
    assert off1 > 0
    assert off1 > off0


def test_append_uses_seek_end_not_full_read(tmp_path):
    """append must not need to load the whole file to find the offset."""
    scroll = Scroll(tmp_path / "s.scroll")
    off0 = scroll.append("a")
    off1 = scroll.append("b")
    assert off0 == 0
    assert off1 == scroll.path.stat().st_size - len(scroll.path.read_bytes()[off1:])


def test_append_record_is_valid_jsonl(tmp_path):
    scroll = Scroll(tmp_path / "s.scroll")
    scroll.append("hello world")
    lines = scroll.path.read_bytes().decode("utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["v"] == 1
    assert rec["payload"] == "hello world"
    assert len(rec["hash"]) == 64
    assert rec["n"] == len("hello world".encode("utf-8"))
    assert "ts" in rec


def test_append_two_records(tmp_path):
    scroll = Scroll(tmp_path / "s.scroll")
    scroll.append("turn 1: hello")
    scroll.append("turn 2: world")
    lines = scroll.path.read_bytes().decode("utf-8").strip().splitlines()
    assert len(lines) == 2
    payloads = [json.loads(l)["payload"] for l in lines]
    assert payloads == ["turn 1: hello", "turn 2: world"]


def test_record_count(tmp_path):
    scroll = Scroll(tmp_path / "s.scroll")
    assert scroll.record_count() == 0
    scroll.append("a")
    assert scroll.record_count() == 1
    scroll.append("b")
    assert scroll.record_count() == 2


def test_tail_returns_recent_content(tmp_path):
    scroll = Scroll(tmp_path / "s.scroll")
    scroll.append("turn 1: hello")
    scroll.append("turn 2: world")
    # Size-bounded tip may equal the whole file when short — that is not dump_all.
    tail = scroll.tail(max_bytes=scroll.size())
    assert "turn 2" in tail
    assert "turn 1" in tail


def test_tail_does_not_split_utf8(tmp_path):
    scroll = Scroll(tmp_path / "s.scroll")
    scroll.append("日本語テスト: あいう")
    data = scroll.path.read_bytes()
    for max_b in range(1, len(data) + 1):
        result = scroll.tail(max_bytes=max_b)
        assert isinstance(result, str)


def test_read_slice_requires_both_args(tmp_path):
    scroll = Scroll(tmp_path / "s.scroll")
    off1 = scroll.append("turn 1")
    off2 = scroll.append("turn 2")
    text = scroll.read_slice(off1, off2)
    assert "turn 1" in text


def test_read_slice_contains_payload(tmp_path):
    scroll = Scroll(tmp_path / "s.scroll")
    off0 = scroll.append("turn 1: hello")
    off1 = scroll.append("turn 2: world")
    text = scroll.read_slice(off0, off1)
    assert "turn 1" in text


def test_read_slice_oversized_refused(tmp_path):
    scroll = Scroll(tmp_path / "s.scroll")
    big = "x" * (MAX_SLICE + 1)
    scroll.append(big)
    with pytest.raises(ScrollError, match="too large|MAX_SLICE|complete scroll"):
        scroll.read_slice(0, scroll.size())


def test_read_slice_complete_scroll_refused(tmp_path):
    """Ordinary reads must not return the entire non-empty scroll, even if small."""
    scroll = Scroll(tmp_path / "s.scroll")
    scroll.append("small record")
    sz = scroll.size()
    assert 0 < sz <= MAX_SLICE
    with pytest.raises(ScrollError, match="complete scroll"):
        scroll.read_slice(0, sz)


def test_read_slice_partial_within_max_ok(tmp_path):
    scroll = Scroll(tmp_path / "s.scroll")
    off0 = scroll.append("turn 1: hello")
    off1 = scroll.append("turn 2: world")
    # Partial range — not the whole file
    text = scroll.read_slice(off0, off1)
    assert "turn 1" in text
    assert "turn 2" not in text


def test_dump_all_refused(tmp_path):
    scroll = Scroll(tmp_path / "s.scroll")
    scroll.append("secret history")
    with pytest.raises(ScrollError, match="dumping the whole scroll"):
        scroll.dump_all()


def test_empty_head_refused(tmp_path):
    scroll = Scroll(tmp_path / "s.scroll")
    with pytest.raises(ScrollError, match="empty"):
        scroll.append("")


def test_tail_max_bytes_positive(tmp_path):
    scroll = Scroll(tmp_path / "s.scroll")
    with pytest.raises(ScrollError, match="positive"):
        scroll.tail(max_bytes=0)
    with pytest.raises(ScrollError, match="positive"):
        scroll.tail(max_bytes=-1)
