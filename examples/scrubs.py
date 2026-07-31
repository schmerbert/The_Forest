# Host-oriented scrub examples. Pass as scrub= to write / write_pair / commit_turn.
#
# RULE: scrub may strip transport / harness scaffolding only.
# Never silently rewrite, compress, or reinterpret the substantive claim —
# store that as a separately attributed synthesis entry instead.

from __future__ import annotations

import re

# --- extension point ---------------------------------------------------------
# def my_scrub(text: str) -> str:
#     text = default_scrub(text)   # usually compose with the minimum
#     ...
#     return text.strip()
#
# store.write(..., scrub=my_scrub)
# commit_turn(store, scroll, user, scrub=my_scrub)

_TOOL_TRACE = re.compile(
    r"(?im)^[ \t]*(?:tool[_ -]?(?:call|result|output)|function[_ -]?(?:call|response)|TOOL_RESULT)\b.*(?:\n|$)"
)

_COT_TAGS = re.compile(
    r"(?is)<(?:think|thinking|scratchpad|reasoning|inner[_-]?monologue)\b[^>]*>.*?</(?:think|thinking|scratchpad|reasoning|inner[_-]?monologue)>"
)
_COT_FENCES = re.compile(
    r"(?is)```(?:thinking|scratchpad|reasoning)\s*.*?```"
)
_STRAY_MARKERS = re.compile(
    r"</?(?:think|scratchpad|system|thinking|reasoning)[^>]*>",
    re.I,
)


def tool_trace_scrub(text: str) -> str:
    """Strip common tool-call / tool-result transcript blocks; keep the claim."""
    text = text.strip()
    text = _TOOL_TRACE.sub("", text)
    text = _COT_TAGS.sub("", text)
    text = _STRAY_MARKERS.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def cot_marker_scrub(text: str) -> str:
    """Strip chain-of-thought tags and fenced thinking blocks; keep the claim."""
    text = text.strip()
    text = _COT_FENCES.sub("", text)
    text = _COT_TAGS.sub("", text)
    text = _STRAY_MARKERS.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
