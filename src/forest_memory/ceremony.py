# ceremony — authority promotion gates (application layer on the constitution).
#
# Stores: nothing
# Refuses: unsigned adopting words, praise-only quotes (English lint),
#          paraphrase posed as author prose
# Returns: new ground entry id via ForestStore.adopt
# Test: tests/test_ceremony.py, tests/test_promotion_boundary.py
#
# Trust boundary: the store records adopting_signature verbatim. It cannot
# verify that the named speaker actually spoke the adopting words — the HOST
# APPLICATION authenticates the speaker before calling this gate. What Forest
# guarantees is that the claim is recorded, attributed, and immutable.

from __future__ import annotations

import re

from forest_memory.core import ForestStore

# Convenience lint, NOT enforcement: catches common English praise/hedge
# phrases mistaken for adoption ("oh, that's lovely", "sounds right").
# It is English-only by construction; adoptions in other languages pass
# through untouched. Do not extend it into an intent classifier — deciding
# what counts as an adoption act is the host application's job.
_PRAISE_ONLY = re.compile(
    r"^(oh[,!]?\s*)?(that'?s\s+)?"
    r"(lovely|beautiful|great|wonderful|perfect|nice|"
    r"sounds\s+(right|good)|love\s+it)"
    r"\.?!?$",
    re.IGNORECASE,
)


class CeremonyRefusal(Exception):
    """Raised when promotion ceremony is insufficient for ground."""


def adopt_to_ground(
    store: ForestStore,
    *,
    adopted_entry_id: int,
    body: str,
    adopting_words: str,
    adopting_signature: str,
    source_verbatim: str | None = None,
) -> int:
    """Promote text to ground only through an explicit authority-holder adoption.

    ``adopting_signature`` names who spoke the adopting words; the host
    application is responsible for having authenticated that speaker. The
    words are recorded verbatim in the adoption record.

    Returns the new ground entry id.
    """
    if not adopting_signature or not adopting_signature.strip():
        raise CeremonyRefusal("adoption without a speaker signature refused")
    if not adopting_words or not adopting_words.strip():
        raise CeremonyRefusal("missing adopting words")
    if _PRAISE_ONLY.match(adopting_words.strip()):
        raise CeremonyRefusal("enthusiasm is not adoption")
    if not body or not body.strip():
        raise CeremonyRefusal("empty body")
    if source_verbatim is not None and body.strip() != source_verbatim.strip():
        raise CeremonyRefusal(
            "unsigned words in the authority-holder's mouth: body must be verbatim"
        )

    _, ground_id = store.adopt(
        adopted_entry_id=adopted_entry_id,
        quote=adopting_words.strip(),
        ground_body=body,
        adopting_signature=adopting_signature.strip(),
    )
    return ground_id
