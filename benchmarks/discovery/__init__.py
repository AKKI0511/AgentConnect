"""Discovery corpus and retrieval benchmark."""

from __future__ import annotations

from benchmarks.discovery.corpus import CORPUS_REVISION, load_corpus, roster_sizes
from benchmarks.discovery.types import REQUIRED_SLICE_LABELS, Corpus, Need, Roster

__all__ = [
    "CORPUS_REVISION",
    "REQUIRED_SLICE_LABELS",
    "Corpus",
    "Need",
    "Roster",
    "load_corpus",
    "roster_sizes",
]
