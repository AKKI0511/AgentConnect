"""Hashed warm Team.find on memory and Redis, embedded and HTTP."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from tests.support.budgets import (
    CONCURRENT_FINDERS,
    HASHED_SUPPORTED_MEMBERS,
    HTTP_WARMUPS,
    WARM_SAMPLES,
    extra_lag,
    find_p95_budget_s,
    percentile,
)
from tests.support.runtime import (
    assert_loop_responsive,
    assert_measured_backend,
    http_find,
    join_roster,
    probe_during,
    start_team,
)
from tests.team.conftest import join_member, make_did

from agentconnect.team.directory.embedder import HashedEmbedder
from agentconnect.team.retention import RETAINED_BYTES_KEY
from benchmarks.runtime.helpers import (
    close_bench_store,
    open_bench_store,
    queue_stats,
    sample_seconds,
)

QUERY = "similar paperwork"


@pytest.mark.perf
@pytest.mark.parametrize("members", HASHED_SUPPORTED_MEMBERS)
@pytest.mark.parametrize("transport", ["embedded", "http"])
@pytest.mark.parametrize("store_kind", ["memory", "redis"])
def test_hashed_warm_find(
    benchmark, async_bridge, store_kind: str, transport: str, members: int
) -> None:
    embeddings = HashedEmbedder()
    store = async_bridge.run(open_bench_store(store_kind))
    team = async_bridge.run(
        start_team(store, embeddings=embeddings, lease_ttl_seconds=8)
    )
    client: httpx.AsyncClient | None = None
    try:
        async_bridge.run(join_roster(team, members, specialist=True))
        caller = async_bridge.run(
            join_member(team, "researcher", agent_did=make_did("researcher"))
        )
        token = caller["session_token"]
        async_bridge.run(team.find(token, QUERY))

        if transport == "http":
            origin = async_bridge.run(team.serve())
            client = httpx.AsyncClient(timeout=60.0, trust_env=False)
            async_bridge.run(client.__aenter__())

            def find_once():
                return async_bridge.run(http_find(client, origin, token, QUERY))

            warmup = HTTP_WARMUPS
        else:

            def find_once():
                return async_bridge.run(team.find(token, QUERY))

            warmup = 0

        found = benchmark.pedantic(
            find_once,
            rounds=WARM_SAMPLES,
            warmup_rounds=warmup,
            iterations=1,
        )
        assert found["matches"]
        budget = find_p95_budget_s(members)
        assert budget is not None
        p95 = percentile(sample_seconds(benchmark), 95)
        assert p95 < budget, (
            f"hashed Team.find p95 {p95 * 1000:.1f}ms exceeds "
            f"{budget * 1000:.0f}ms at {members} {store_kind} {transport}"
        )

        async def one_find():
            if transport == "http":
                assert client is not None
                return await http_find(client, origin, token, QUERY)
            return await team.find(token, QUERY)

        probed, intervals = async_bridge.run(
            probe_during(one_find(), members=members, enforce=False)
        )
        assert probed["matches"]
        assert_loop_responsive(intervals, members=members)

        async def burst_find():
            return await asyncio.gather(
                *[one_find() for _ in range(CONCURRENT_FINDERS)]
            )

        burst = async_bridge.run(burst_find())
        assert all(item["matches"] for item in burst)
        assert_measured_backend(team, embeddings.name)

        retained = async_bridge.run(store.get(RETAINED_BYTES_KEY))
        extras = extra_lag(intervals)
        benchmark.extra_info.update(
            {
                "store": store_kind,
                "backend": "hashed",
                "transport": transport,
                "members": members,
                "p95_s": p95,
                "budget_p95_s": budget,
                "extra_lag_max_s": max(extras) if extras else None,
                "store_calls": getattr(store, "calls", {}),
                "write_bytes": getattr(store, "write_bytes", 0),
                "retained_bytes": 0 if retained is None else int(retained),
                "queue": queue_stats(team),
                "backend_name": team._directory.backend_name,
            }
        )
    finally:
        if client is not None:
            async_bridge.run(client.aclose())
        async_bridge.run(team.stop())
        async_bridge.run(close_bench_store(store))
