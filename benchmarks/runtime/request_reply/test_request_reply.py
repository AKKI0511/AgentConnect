"""End-to-end request/reply exchange under concurrency."""

from __future__ import annotations

from typing import Any

import pytest
from tests.support.budgets import (
    EXCHANGE_CONCURRENCY,
    EXCHANGE_ERROR_RATE,
    EXCHANGE_P95_STALL_S,
    EXCHANGE_REPLICA_CONCURRENCY,
    EXCHANGE_TRIPS_PER_PAIR,
    exchange_zero_error_gated,
)

from benchmarks.runtime.request_reply.workload import (
    close_exchange,
    measure,
    open_exchange,
)


def _run_cell(
    benchmark: Any,
    async_bridge: Any,
    store_kind: str,
    transport: str,
    concurrency: int,
    replicas: int,
) -> dict[str, Any]:
    bench = async_bridge.run(
        open_exchange(store_kind, transport, concurrency, replicas=replicas)
    )
    try:

        def timed():
            return async_bridge.run(measure(bench, EXCHANGE_TRIPS_PER_PAIR))

        summary = benchmark.pedantic(timed, rounds=1, warmup_rounds=0, iterations=1)
    finally:
        async_bridge.run(close_exchange(bench))
    gated = exchange_zero_error_gated(store_kind, concurrency, replicas)
    summary["gated"] = gated
    benchmark.extra_info.update(summary)
    attempted = int(summary["attempted"])
    assert attempted == concurrency * EXCHANGE_TRIPS_PER_PAIR
    assert summary["completed"] > 0
    if not gated:
        return summary
    assert summary["completed"] == attempted, (
        f"completed {summary['completed']}/{attempted} "
        f"errors={summary['errors']} timeouts={summary['timeouts']} "
        f"samples={summary.get('error_samples')}"
    )
    assert summary["error_rate"] <= EXCHANGE_ERROR_RATE
    assert summary["timeout_rate"] <= EXCHANGE_ERROR_RATE
    p95 = summary["p95_s"]
    assert p95 is not None
    assert p95 < EXCHANGE_P95_STALL_S, (
        f"request/reply p95 {p95 * 1000:.1f}ms exceeds "
        f"{EXCHANGE_P95_STALL_S * 1000:.0f}ms stall bound at {concurrency} "
        f"{store_kind} {transport} replicas={replicas}"
    )
    return summary


@pytest.mark.perf
@pytest.mark.parametrize("concurrency", EXCHANGE_CONCURRENCY)
@pytest.mark.parametrize("transport", ["embedded", "http"])
@pytest.mark.parametrize("store_kind", ["memory", "redis"])
def test_request_reply_one_runtime(
    benchmark, async_bridge, store_kind: str, transport: str, concurrency: int
) -> None:
    _run_cell(
        benchmark,
        async_bridge,
        store_kind,
        transport,
        concurrency,
        replicas=1,
    )


@pytest.mark.perf
@pytest.mark.parametrize("concurrency", EXCHANGE_REPLICA_CONCURRENCY)
def test_request_reply_two_replicas(benchmark, async_bridge, concurrency: int) -> None:
    _run_cell(
        benchmark,
        async_bridge,
        "redis",
        "http",
        concurrency,
        replicas=2,
    )
