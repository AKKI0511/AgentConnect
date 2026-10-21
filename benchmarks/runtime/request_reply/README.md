# Request/reply exchange

End-to-end Runtime messaging: `send` → `lease` → `reply` → `get_result`.
No Directory `find`, no model, no Agent handler. The worker replies with a
fixed JSON string so the numbers measure AgentConnect, not inference.

This is a sibling of the discovery latency groups in
[the parent Runtime README](../README.md). Ranking quality stays in
[discovery](../../discovery/README.md).

## Workload

N independent caller/worker pairs. Each pair keeps one request in flight
and repeats a `collect=ticket` round-trip. Content is `"ping"` / `"pong"`.
Setup, join, and one warmup trip per pair stay outside the timed window.

| Matrix | Values |
| --- | --- |
| Store | memory, Redis |
| Access | embedded Team, HTTP Session transport |
| Concurrency | 1, 8, 32 pairs |
| Trips per pair | 100 at N=1 so completed-only p99 has 100 samples; 20 otherwise |
| Replicas | 1 Runtime on the default path |

Two-process Redis HTTP (`AGENTCONNECT_REPLICA_BENCH=1`) sends on Runtime A
and leases/replies on Runtime B. That is a throughput probe, not replica
support. Shared Redis does not make two processes a supported deployment.
Process-local locks and work hints are not shared. Empty-lease retries cover
cross-process delay. Historical two-process rows stay in
[RESULTS.md](RESULTS.md).

## Run

Start the dedicated test Redis from [CONTRIBUTING.md](../../../CONTRIBUTING.md).

```powershell
uv sync --locked --group benchmark --extra redis
uv run --no-sync pytest benchmarks/runtime/request_reply -q --benchmark-warmup=off --benchmark-json=benchmarks/runtime/results/exchange.json
```

`make perf` includes this group after the discovery files. Redis cases skip
locally when Redis is down; set `AGENTCONNECT_REQUIRE_REDIS=1` to fail instead.

## Gates and evidence

pytest-benchmark JSON carries p50 / p95 / p99, completed round-trips/sec,
and error / timeout rates in `extra_info`. Percentiles use completed trips
only. p99 is omitted when completed samples are under 100. Error and timeout
rates use attempted trips as the denominator. Cells at concurrency 1 and 8,
and memory at 32, must complete every trip with no timeout and p95 under
the 5 s stall bound in [tests/support/budgets.py](../../../tests/support/budgets.py).
Redis cells at 32 are measured; they are not a 100% completion gate. The
stall bound is not a latency SLA.

[RESULTS.md](RESULTS.md) records accepted hardware, the strongest
defensible concurrency, and the exact workload. Defensible means zero
errors and timeouts, throughput that still rises or holds versus the next
lower N, and p95 that has not collapsed relative to N=1 on that backend.

Percentiles use completed trips only. Throughput is completed trips divided
by wall time of the concurrent batch. Do not retune the stall bound to hide
a hang, and do not treat a local desktop run as a universal guarantee.
