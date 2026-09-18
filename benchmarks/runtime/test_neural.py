"""Neural FastEmbed Team.find. 1,000 members is measured, not a hashed p95 gate."""

from __future__ import annotations

import asyncio
import os

import httpx
import pytest
from tests.support.budgets import (
    CONCURRENT_FINDERS,
    HTTP_WARMUPS,
    NEURAL_MEASURED_MEMBERS,
    NEURAL_SUPPORTED_MEMBERS,
    WARM_SAMPLES,
    extra_lag,
    loop_lag_budget_s,
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

from agentconnect.team.directory.embedder import FastEmbedEmbedder
from benchmarks.runtime.helpers import (
    close_bench_store,
    open_bench_store,
    queue_stats,
    sample_seconds,
)

QUERY = "similar paperwork"

NEURAL_CASES = [
    (store, transport, size)
    for size in NEURAL_MEASURED_MEMBERS
    for store in (("memory",) if size == 1000 else ("memory", "redis"))
    for transport in (("embedded",) if size == 1000 else ("embedded", "http"))
]


def _require_neural() -> None:
    flag = os.environ.get("AGENTCONNECT_REQUIRE_NEURAL", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    try:
        import fastembed  # noqa: F401
    except ImportError:
        if flag:
            pytest.fail("neural coverage is required; install agentconnect[embeddings]")
        pytest.skip("fastembed is not installed")


@pytest.mark.perf
@pytest.mark.parametrize("store_kind,transport,members", NEURAL_CASES)
def test_neural_warm_find(
    benchmark,
    async_bridge,
    store_kind: str,
    transport: str,
    members: int,
) -> None:
    _require_neural()
    embeddings = FastEmbedEmbedder()
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
        p95 = percentile(sample_seconds(benchmark), 95)
        assert_measured_backend(team, embeddings.name)

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
        extras = extra_lag(intervals)
        benchmark.extra_info.update(
            {
                "store": store_kind,
                "backend": "neural",
                "transport": transport,
                "members": members,
                "p95_s": p95,
                "gated": members in NEURAL_SUPPORTED_MEMBERS,
                "extra_lag_max_s": max(extras) if extras else None,
                "lag_budget_s": loop_lag_budget_s(members),
                "queue": queue_stats(team),
                "backend_name": team._directory.backend_name,
            }
        )
    finally:
        if client is not None:
            async_bridge.run(client.aclose())
        async_bridge.run(team.stop())
        async_bridge.run(close_bench_store(store))
