"""Forest — custody-shaped DB layer for harness builders."""

from forest_memory.ceremony import CeremonyRefusal, root_to_ground
from forest_memory.core import (
    ForestError,
    ForestStore,
    Trail,
    commit_turn,
    default_scrub,
    hash_body,
)
from forest_memory.drift import check_file_drift
from forest_memory.mycelium import (
    answer_question,
    feed_question,
    fruits_near,
    is_open,
    plant_question,
    reopen_question,
)
from forest_memory.scroll import Scroll, ScrollError

__all__ = [
    "CeremonyRefusal",
    "ForestError",
    "ForestStore",
    "Scroll",
    "ScrollError",
    "Trail",
    "answer_question",
    "check_file_drift",
    "commit_turn",
    "default_scrub",
    "feed_question",
    "fruits_near",
    "hash_body",
    "is_open",
    "plant_question",
    "reopen_question",
    "root_to_ground",
]

__version__ = "0.4.0"
