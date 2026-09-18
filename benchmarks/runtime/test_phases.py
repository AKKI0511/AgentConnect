"""Cold indexing, Profile update through Team.join, and hashed fallback rebuild."""

from __future__ import annotations

from typing import Any

import pytest
from tests.support.budgets import extra_lag, loop_lag_budget_s
from tests.support.runtime import (
    LONG_PROFILE_MEMBERS,
    FailingEmbedder,
    assert_loop_responsive,
    heavy_profile,
    probe_during,
    short_profile,
    specialist_profile,
    start_team,
)
from tests.support.stores import open_store
from tests.team.conftest import join_member, make_did

from agentconnect.team.directory.embedder import HashedEmbedder
from benchmarks.runtime.helpers import queue_stats, sample_seconds

MEMBERS = LONG_PROFILE_MEMBERS


def _stop(async_bridge, team, store) -> None:
    async_bridge.run(team.stop())
    async_bridge.run(store.clear())
    async_bridge.run(store.close())


@pytest.mark.perf
@pytest.mark.parametrize("store_kind", ["memory", "redis"])
def test_cold_long_profiles(benchmark, async_bridge, store_kind: str) -> None:
    store = async_bridge.run(open_store(store_kind))
    team = async_bridge.run(start_team(store, embeddings=HashedEmbedder()))
    captured: dict[str, Any] = {}
    try:

        async def cold():
            for index in range(MEMBERS):
                name = f"agent{index:02d}"
                await join_member(
                    team,
                    name,
                    agent_did=make_did(name),
                    profile=heavy_profile(f"task{index:02d}"),
                )
            caller = await join_member(team, "researcher")
            return await team.find(caller["session_token"], "clause review notes")

        def timed():
            async def wrapped():
                result, intervals = await probe_during(
                    cold(), members=MEMBERS, enforce=False
                )
                captured["intervals"] = intervals
                return result

            return async_bridge.run(wrapped())

        found = benchmark.pedantic(timed, rounds=1, warmup_rounds=0, iterations=1)
        assert found["matches"]
        assert team._directory is not None
        assert not team._directory.using_fallback
        assert_loop_responsive(captured["intervals"], members=MEMBERS)
        extras = extra_lag(captured["intervals"])
        benchmark.extra_info.update(
            {
                "store": store_kind,
                "phase": "cold-index",
                "members": MEMBERS,
                "elapsed_s": sample_seconds(benchmark)[0],
                "extra_lag_max_s": max(extras),
                "lag_budget_s": loop_lag_budget_s(MEMBERS),
                "queue": queue_stats(team),
            }
        )
    finally:
        _stop(async_bridge, team, store)


@pytest.mark.perf
@pytest.mark.parametrize("store_kind", ["memory", "redis"])
def test_profile_update_join_and_rank(benchmark, async_bridge, store_kind: str) -> None:
    store = async_bridge.run(open_store(store_kind))
    team = async_bridge.run(start_team(store, embeddings=HashedEmbedder()))
    writer_did = make_did("writer")
    captured: dict[str, Any] = {}
    try:
        async_bridge.run(
            join_member(team, "writer", agent_did=writer_did, profile=short_profile(0))
        )
        for index in range(MEMBERS - 1):
            name = f"agent{index:02d}"
            async_bridge.run(
                join_member(
                    team,
                    name,
                    agent_did=make_did(name),
                    profile=heavy_profile(f"task{index:02d}"),
                )
            )
        caller = async_bridge.run(join_member(team, "researcher"))
        token = caller["session_token"]

        async def update_and_rank():
            await join_member(
                team, "writer", agent_did=writer_did, profile=specialist_profile()
            )
            return await team.find(token, "missing terms and contract risk")

        def timed():
            async def wrapped():
                result, intervals = await probe_during(
                    update_and_rank(), members=MEMBERS, enforce=False
                )
                captured["intervals"] = intervals
                return result

            return async_bridge.run(wrapped())

        found = benchmark.pedantic(timed, rounds=1, warmup_rounds=0, iterations=1)
        top = found["matches"][0]["address"]
        assert top.startswith("writer@"), (
            f"expected writer@ after Profile update, ranked {top}"
        )
        assert_loop_responsive(captured["intervals"], members=MEMBERS)
        extras = extra_lag(captured["intervals"])
        benchmark.extra_info.update(
            {
                "store": store_kind,
                "phase": "profile-update",
                "members": MEMBERS,
                "elapsed_s": sample_seconds(benchmark)[0],
                "extra_lag_max_s": max(extras),
                "lag_budget_s": loop_lag_budget_s(MEMBERS),
                "top": top,
            }
        )
    finally:
        _stop(async_bridge, team, store)


@pytest.mark.perf
@pytest.mark.parametrize("store_kind", ["memory", "redis"])
def test_fallback_rebuild(benchmark, async_bridge, store_kind: str) -> None:
    embedder = FailingEmbedder(succeed_calls=MEMBERS + 2)
    store = async_bridge.run(open_store(store_kind))
    team = async_bridge.run(start_team(store, embeddings=embedder))
    captured: dict[str, Any] = {}
    try:
        for index in range(MEMBERS):
            name = f"agent{index:02d}"
            async_bridge.run(
                join_member(
                    team,
                    name,
                    agent_did=make_did(name),
                    profile=heavy_profile(f"task{index:02d}"),
                )
            )
        caller = async_bridge.run(join_member(team, "researcher"))

        async def rebuild_find():
            return await team.find(caller["session_token"], "clause review notes")

        def timed():
            async def wrapped():
                result, intervals = await probe_during(
                    rebuild_find(), members=MEMBERS, rebuild=True, enforce=False
                )
                captured["intervals"] = intervals
                return result

            return async_bridge.run(wrapped())

        found = benchmark.pedantic(timed, rounds=1, warmup_rounds=0, iterations=1)
        assert found["matches"]
        directory = team._directory
        assert directory is not None
        assert directory.using_fallback
        assert directory.backend_name == "hashed"
        assert_loop_responsive(captured["intervals"], members=MEMBERS, rebuild=True)
        extras = extra_lag(captured["intervals"])
        benchmark.extra_info.update(
            {
                "store": store_kind,
                "phase": "fallback-rebuild",
                "members": MEMBERS,
                "elapsed_s": sample_seconds(benchmark)[0],
                "extra_lag_max_s": max(extras),
                "lag_budget_s": loop_lag_budget_s(MEMBERS, rebuild=True),
                "embed_calls": embedder.calls,
                "using_fallback": True,
                "queue": queue_stats(team),
            }
        )
    finally:
        _stop(async_bridge, team, store)
