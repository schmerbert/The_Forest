"""Forest — custody-first append-only memory for AI systems."""

from forest_memory.ceremony import CeremonyRefusal, adopt_to_ground
from forest_memory.core import ForestError, ForestStore, hash_body
from forest_memory.drift import check_file_drift
from forest_memory.migrate import (
    migrate_to_latest,
    migrate_v01_to_v02,
    migrate_v02_to_v03,
    store_version,
)
from forest_memory.mycelium import (
    answer_question,
    feed_question,
    fruits_near,
    is_open,
    plant_question,
    reopen_question,
)

__all__ = [
    "CeremonyRefusal",
    "ForestError",
    "ForestStore",
    "adopt_to_ground",
    "answer_question",
    "check_file_drift",
    "feed_question",
    "fruits_near",
    "hash_body",
    "is_open",
    "migrate_to_latest",
    "migrate_v01_to_v02",
    "migrate_v02_to_v03",
    "store_version",
    "plant_question",
    "reopen_question",
]

__version__ = "0.3.1"
