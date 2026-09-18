"""Hashed 10,000-member stress probe. Lag only; no latency pass/fail."""

from __future__ import annotations

from typing import Any

import pytest
from tests.support.budgets import STRESS_MEMBERS, extra_lag, loop_lag_budget_s
from tests.support.runtime import join_roster, probe_during, start_team
from tests.support.stores import open_store
from tests.team.conftest import join_member

from agentconnect.team.directory.embedder import HashedEmbedder
from benchmarks.runtime.helpers import sample_seconds


@pytest.mark.perf
def test_hashed_memory_stress(benchmark, async_bridge) -> None:
    store = async_bridge.run(open_store("memory"))
    team = async_bridge.run(start_team(store, embeddings=HashedEmbedder()))
    captured: dict[str, Any] = {}
    try:
        async_bridge.run(join_roster(team, STRESS_MEMBERS))
        caller = async_bridge.run(join_member(team, "researcher"))

        async def stress_find():
            return await team.find(
                caller["session_token"], "similar paperwork", limit=20
            )

        def timed():
            async def wrapped():
                result, intervals = await probe_during(
                    stress_find(), members=STRESS_MEMBERS, enforce=False
                )
                captured["intervals"] = intervals
                return result

            return async_bridge.run(wrapped())

        found = benchmark.pedantic(timed, rounds=1, warmup_rounds=0, iterations=1)
        extras = extra_lag(captured["intervals"])
        budget = loop_lag_budget_s(STRESS_MEMBERS)
        lag = max(extras)
        assert found["matches"]
        assert lag < budget, (
            f"stress extra lag {lag * 1000:.1f}ms exceeds {budget * 1000:.0f}ms"
        )
        benchmark.extra_info.update(
            {
                "store": "memory",
                "members": STRESS_MEMBERS,
                "elapsed_s": sample_seconds(benchmark)[0],
                "extra_lag_max_s": lag,
                "lag_budget_s": budget,
                "matches": len(found["matches"]),
            }
        )
    finally:
        async_bridge.run(team.stop())
        async_bridge.run(store.close())
