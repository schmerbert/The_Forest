# ceremony — authority promotion gates (application layer on the constitution).
#
# Stores: nothing
# Refuses: unsigned rooting words, praise-only quotes (English lint),
#          paraphrase posed as the rooted body when source_verbatim set,
#          body_hash mismatch when expected_body_hash provided
# Returns: rooted entry id via ForestStore._root (in-place)
# Test: tests/test_ceremony.py, tests/test_promotion_boundary.py

from __future__ import annotations

import re

from forest_memory.core import ForestStore

_PRAISE_ONLY = re.compile(
    r"^(oh[,!]?\s*)?(that'?s\s+)?"
    r"(lovely|beautiful|great|wonderful|perfect|nice|"
    r"sounds\s+(right|good)|love\s+it)"
    r"\.?!?$",
    re.IGNORECASE,
)


class CeremonyRefusal(Exception):
    """Raised when the rooting ceremony is insufficient for ground."""


def root_to_ground(
    store: ForestStore,
    *,
    entry_id: int,
    adopting_words: str,
    adopting_signature: str,
    expected_body_hash: str,
    source_verbatim: str | None = None,
) -> int:
    """Root an existing entry in place through an explicit authority act.

    The human adopts the **exact displayed entry as written** — adopting_words
    are the ceremony, not a canon replacement. The rooted body is unchanged;
    expected_body_hash guards against the entry drifting between display and
    adoption. Returns the same ``entry_id`` (now current ground).

    The host authenticates the speaker; the store records the claimed
    signature verbatim as attributed evidence.
    """
    if not adopting_signature or not adopting_signature.strip():
        raise CeremonyRefusal("root without a speaker signature refused")
    if not adopting_words or not adopting_words.strip():
        raise CeremonyRefusal("missing adopting words")
    if _PRAISE_ONLY.match(adopting_words.strip()):
        raise CeremonyRefusal("enthusiasm is not root")
    row = store.get(entry_id)
    if row is None:
        raise CeremonyRefusal(f"unknown entry {entry_id}")
    if row["body_hash"] != expected_body_hash:
        raise CeremonyRefusal(
            f"body_hash mismatch for entry {entry_id}: "
            f"expected {expected_body_hash!r}, stored {row['body_hash']!r}. "
            "Re-read the entry before adopting."
        )
    if source_verbatim is not None and row["body"].strip() != source_verbatim.strip():
        raise CeremonyRefusal(
            "unsigned words in the authority-holder's mouth: body must be verbatim"
        )

    store._root(
        entry_id=entry_id,
        quote=adopting_words.strip(),
        adopting_signature=adopting_signature.strip(),
        expected_body_hash=expected_body_hash,
    )
    return entry_id
