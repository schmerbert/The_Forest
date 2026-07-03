# ceremony — authority promotion gates (application layer on the constitution).
#
# Stores: nothing
# Refuses: praise-only adoption, paraphrase posed as author prose
# Returns: adoption_record id via ForestStore.adopt
# Test: tests/test_ceremony.py

from __future__ import annotations

import re

from forest_memory.core import ForestStore

_PRAISE_ONLY = re.compile(
    r"^(oh[,!]?\s*)?(that'?s\s+)?(lovely|beautiful|great|wonderful|perfect|nice)\.?!?$",
    re.IGNORECASE,
)

_ADOPTION_MARKERS = re.compile(
    r"\b(yes|shelve|adopt|keep it|make it canon|put it in)\b",
    re.IGNORECASE,
)


class CeremonyRefusal(Exception):
    """Raised when promotion ceremony is insufficient for ground."""


def _is_praise_only(adopting_words: str) -> bool:
    text = adopting_words.strip()
    if _PRAISE_ONLY.match(text):
        return True
    if not _ADOPTION_MARKERS.search(text) and len(text.split()) < 8:
        return True
    return False


def adopt_to_ground(
    store: ForestStore,
    *,
    adopted_entry_id: int,
    body: str,
    adopting_words: str,
    source_verbatim: str | None = None,
) -> int:
    """Promote text to ground only through an explicit authority-holder adoption."""
    if not adopting_words or not adopting_words.strip():
        raise CeremonyRefusal("missing adopting words")
    if _is_praise_only(adopting_words):
        raise CeremonyRefusal("enthusiasm is not adoption")
    if not body or not body.strip():
        raise CeremonyRefusal("empty body")
    if source_verbatim is not None and body.strip() != source_verbatim.strip():
        raise CeremonyRefusal("unsigned words in the authority-holder's mouth: body must be verbatim")

    return store.adopt(
        adopted_entry_id=adopted_entry_id,
        quote=adopting_words.strip(),
        new_ground_body=body,
    )
