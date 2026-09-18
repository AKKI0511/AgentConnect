"""Predetermined Runtime pass/fail budgets.

These numbers were fixed from the M7 hashed-probe evidence in the
internal roadmap (warm medians 11ms/46ms/116ms at 100/400/1,000 short
Profiles; 109ms 10ms-timer interval at 1,000 members; 148ms interval on
the 400-member warm-ranking test against an 80ms assertion; ~53ms
interval while rebuilding 20 heavy Profiles). They are not fitted to a
later run.

Lag budgets apply to extra delay on a 10ms ``asyncio.sleep`` probe:
``extra = interval - 0.01``. The 148ms failure was a 138ms extra stall.
Hashed warm-find p95 budgets apply to public ``Team.find`` on the
supported store/transport matrix, not to isolated Directory searches.

The supported single-Runtime range is 10–1,000 hashed Memberships, 10–100
local neural Memberships, memory and Redis, embedded and HTTP. Neural
work at 1,000 is measured and may be recorded as unsupported. 10,000 is
a stress probe with no latency pass/fail. Replica work stays in v0.8.
"""

from __future__ import annotations

LOOP_PROBE_SLEEP_S = 0.01

# Extra delay on a 10ms asyncio.sleep probe (interval minus sleep).
LOOP_LAG_S_LE_100 = 0.050
LOOP_LAG_S_LE_400 = 0.080
LOOP_LAG_S_LE_1000 = 0.150
LOOP_LAG_S_REBUILD = 0.080
LOOP_LAG_S_STRESS = 0.500

# Warm hashed Team.find p95 after one warmup search.
FIND_P95_S = {
    10: 0.025,
    100: 0.050,
    400: 0.100,
    1000: 0.250,
}
FIND_P50_S = {
    10: 0.020,
    100: 0.040,
    400: 0.080,
    1000: 0.200,
}

WARM_SAMPLES = 20
CONCURRENT_FINDERS = 8
HTTP_WARMUPS = 3

# A 50ms handler with in-process hints should not wait the full hold.
WAIT_AMPLIFICATION_HINTS_S = 0.200
# Pull without hints uses a 1s empty-mailbox timeout; still must finish.
WAIT_WITHOUT_HINTS_S = 3.0

# collect=wait must not sit on a 50ms poll when the Ticket is already
# terminal and hints are enabled.
WAIT_POLL_WITHOUT_HINTS_S = 0.050

# Send issued while a 400-member hashed find is running.
SEND_DURING_FIND_P95_S = 0.100
SEND_DURING_FIND_MEMBERS = 400
SEND_DURING_FIND_SAMPLES = 20

# After complete+replay-expiry cycles, retained bytes return near empty.
RETENTION_CYCLES = 12
RETENTION_SLACK_BYTES = 4096

# Neural (local FastEmbed BGE) stays off the event loop at the hashed lag
# budgets for the same roster size. Latency itself is reported, not gated
# by hashed p95. 1,000 is measured; it is not a pass/fail latency size.
NEURAL_SUPPORTED_MEMBERS = (10, 100)
NEURAL_MEASURED_MEMBERS = (10, 100, 1000)
HASHED_SUPPORTED_MEMBERS = (10, 100, 1000)
STRESS_MEMBERS = 10_000
WARM_RANK_MEMBERS = 400


def extra_lag(
    intervals: list[float], sleep_for: float = LOOP_PROBE_SLEEP_S
) -> list[float]:
    """Return extra delay beyond the intended sleep for each probe interval."""
    return [max(0.0, item - sleep_for) for item in intervals]


def loop_lag_budget_s(members: int, *, rebuild: bool = False) -> float:
    """Return the max extra 10ms-probe lag allowed for ``members``."""
    if rebuild:
        return LOOP_LAG_S_REBUILD
    if members <= 100:
        return LOOP_LAG_S_LE_100
    if members <= 400:
        return LOOP_LAG_S_LE_400
    if members <= 1000:
        return LOOP_LAG_S_LE_1000
    return LOOP_LAG_S_STRESS


def find_p95_budget_s(members: int) -> float | None:
    """Return the hashed warm-find p95 budget, or None for stress sizes."""
    return FIND_P95_S.get(members)


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile for a non-empty sample."""
    if not values:
        raise ValueError("percentile of empty sample")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (pct / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] * (1.0 - frac) + ordered[high] * frac
