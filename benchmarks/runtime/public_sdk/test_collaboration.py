"""Public SDK collaboration under memory/Redis and embedded/HTTP."""

from __future__ import annotations

from typing import Any

import pytest
from tests.support.budgets import (
    COLLAB_ERROR_RATE,
    COLLAB_P95_STALL_S,
    COLLAB_REPETITIONS,
    COLLAB_WARMUP,
)

from benchmarks.runtime.public_sdk.workload import (
    close_collab,
    discover_and_ask,
    fanout_and_aggregate,
    measure,
    open_collab,
    reconnect_collects_open_work,
    summarize,
    thread_follow_up,
)


def _run(
    benchmark: Any,
    async_bridge: Any,
    store_kind: str,
    transport: str,
    work,
    name: str,
    repetitions: int = COLLAB_REPETITIONS,
) -> dict[str, Any]:
    bench = async_bridge.run(open_collab(store_kind, transport))
    try:
        for _ in range(COLLAB_WARMUP):
            async_bridge.run(work(bench))

        def timed():
            return async_bridge.run(
                measure(
                    bench,
                    work,
                    repetitions=repetitions,
                )
            )

        outcomes, wall_s = benchmark.pedantic(
            timed, rounds=1, warmup_rounds=0, iterations=1
        )
        summary = summarize(
            outcomes,
            wall_s=wall_s,
            store_kind=store_kind,
            transport=transport,
            workload=name,
            repetitions=repetitions,
            warmup=COLLAB_WARMUP,
        )
    finally:
        async_bridge.run(close_collab(bench))
    benchmark.extra_info.update(summary)
    attempted = int(summary["attempted"])
    assert attempted == repetitions
    assert summary["completed"] > 0
    assert summary["completed"] == attempted, (
        f"completed {summary['completed']}/{attempted} "
        f"errors={summary['errors']} timeouts={summary['timeouts']} "
        f"samples={summary.get('error_samples')}"
    )
    assert summary["error_rate"] <= COLLAB_ERROR_RATE
    assert summary["timeout_rate"] <= COLLAB_ERROR_RATE
    p95 = summary["p95_s"]
    assert p95 is not None
    assert p95 < COLLAB_P95_STALL_S, (
        f"{name} p95 {p95 * 1000:.1f}ms exceeds "
        f"{COLLAB_P95_STALL_S * 1000:.0f}ms stall bound on "
        f"{store_kind} {transport}"
    )
    return summary


@pytest.mark.perf
@pytest.mark.parametrize("transport", ["embedded", "http"])
@pytest.mark.parametrize("store_kind", ["memory", "redis"])
def test_discover_profile_and_ask(benchmark, async_bridge, store_kind, transport):
    _run(
        benchmark,
        async_bridge,
        store_kind,
        transport,
        discover_and_ask,
        "discover_profile_ask",
    )


@pytest.mark.perf
@pytest.mark.parametrize("transport", ["embedded", "http"])
@pytest.mark.parametrize("store_kind", ["memory", "redis"])
def test_specialist_fanout(benchmark, async_bridge, store_kind, transport):
    _run(
        benchmark,
        async_bridge,
        store_kind,
        transport,
        fanout_and_aggregate,
        "specialist_fanout",
    )


@pytest.mark.perf
@pytest.mark.parametrize("transport", ["embedded", "http"])
@pytest.mark.parametrize("store_kind", ["memory", "redis"])
def test_thread_follow_up(benchmark, async_bridge, store_kind, transport):
    _run(
        benchmark,
        async_bridge,
        store_kind,
        transport,
        thread_follow_up,
        "thread_follow_up",
    )


@pytest.mark.perf
@pytest.mark.parametrize("transport", ["embedded", "http"])
@pytest.mark.parametrize("store_kind", ["memory", "redis"])
def test_reconnect_collects_retained_work(
    benchmark, async_bridge, store_kind, transport
):
    _run(
        benchmark,
        async_bridge,
        store_kind,
        transport,
        reconnect_collects_open_work,
        "reconnect_open_ticket",
        repetitions=5,
    )
