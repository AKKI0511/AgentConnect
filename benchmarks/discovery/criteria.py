"""Retrieval gates for the discovery corpus.

These two thresholds were fixed before measurement. Coverage at 1 and 5,
slice breakdowns, and field comparisons are reported with them. They are
not extra gates.
"""

from __future__ import annotations

# Held-out shuffled needs with a non-empty acceptable set.
RECALL_AT_10_MIN = 0.90
MRR_MIN = 0.50
COVERAGE_KS = (1, 5, 10)
# Rosters at or below this size cannot miss coverage@10 when every
# acceptable member is present. Report ordering (coverage@1, MRR, mean
# best rank) for them, and coverage@10 on rosters larger than 10.
SMALL_ROSTER_MAX = 10
