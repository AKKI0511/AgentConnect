"""Versioned discovery corpus.

``CORPUS_REVISION`` pins retrieval artifacts.
"""

from __future__ import annotations

from benchmarks.discovery.needs_development import DEVELOPMENT_NEEDS
from benchmarks.discovery.needs_heldout import HELD_OUT_NEEDS
from benchmarks.discovery.rosters_platform import ROSTER_PLATFORM
from benchmarks.discovery.rosters_research import ROSTER_RESEARCH
from benchmarks.discovery.rosters_small import ROSTER_COMMERCE, ROSTER_LEGAL
from benchmarks.discovery.types import Corpus, Need, Roster

CORPUS_REVISION = "discovery-v1"

_ROSTERS: dict[str, Roster] = {
    ROSTER_COMMERCE.id: ROSTER_COMMERCE,
    ROSTER_LEGAL.id: ROSTER_LEGAL,
    ROSTER_PLATFORM.id: ROSTER_PLATFORM,
    ROSTER_RESEARCH.id: ROSTER_RESEARCH,
}


def load_corpus() -> Corpus:
    """Load the pinned corpus without ranking or retrieval."""
    needs: list[Need] = list(DEVELOPMENT_NEEDS) + list(HELD_OUT_NEEDS)
    return Corpus(revision=CORPUS_REVISION, rosters=_ROSTERS, needs=needs)


def roster_sizes() -> dict[str, int]:
    """Return member counts keyed by roster id."""
    return {roster_id: roster.size for roster_id, roster in _ROSTERS.items()}
