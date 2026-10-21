# Public SDK collaboration

End-to-end work through public `BaseAgent` and `Team`. Handlers return fixed
JSON. There is no model, keyword parser, or agent framework.

Request/reply exchange in [../request_reply/](../request_reply/README.md)
measures `send` / `lease` / `reply` / `get_result` without agents. This
suite measures caller-visible journeys on the same store and transport
matrix.

## Workloads

| Name | What it does |
| --- | --- |
| `discover_profile_ask` | `find` a specialist, `get_entry` for its Profile, `ask` and collect the answer |
| `specialist_fanout` | Ask three specialists at once and read every reply |
| `thread_follow_up` | Send a follow-up parented to the first reply; verify all four Thread Messages, parents and sequence |
| `reconnect_open_ticket` | Observe one occupied worker slot, reconnect the caller, collect retained Tickets, then complete fresh work |

Runtime/store setup, one complete warmup journey and report generation sit
outside pytest-benchmark's timer. Each timed repetition includes join, the
journey and leave. Scripted handler delay is
`COLLAB_HANDLER_DELAY_S` (currently 0). The report labels the full journey
mean separately from the mean minus configured critical-path handler sleeps:
one sleep for discovery and concurrent fanout, two for Thread follow-up,
none for the barrier-controlled reconnect workload. This estimate still
includes joins, leaves, scheduling, transport and collection; it is not
isolated Runtime overhead. Reconnect includes a 50 ms observation window
that checks the queued handler does not start while capacity is occupied,
then verifies retained replies and a fresh request after reconnect.

## Matrix and sampling

| Setting | Value |
| --- | --- |
| Store | memory, Redis |
| Access | embedded Team, HTTP Session |
| Agents | caller plus up to three specialists |
| Payload | JSON with an 80-byte notes field |
| Warmup | 1 |
| Timed repetitions | 30; reconnect uses 5 |
| Trip timeout | 15 s |
| Error / timeout rate gate | 0 |
| p95 stall bound | 5 s (hang detection, not an SLA) |
| p99 | reported only when completed samples ≥ 100 |

Percentiles use completed repetitions only. Throughput is completed
repetitions divided by wall time of the timed batch. Offered load is the
attempted count. Failures and timeouts stay in that denominator.

A single concurrency point does not measure saturation or replica safety. The 10,000-member stress probe is a separate opt-in group.

## Run

Start the dedicated test Redis from [CONTRIBUTING.md](../../../CONTRIBUTING.md).

```powershell
uv sync --locked --group benchmark --extra redis
uv run --no-sync pytest benchmarks/runtime/public_sdk -q --benchmark-warmup=off --benchmark-json=benchmarks/runtime/results/collaboration.json
```

`make perf` includes this group after request/reply. Redis cases skip
locally when Redis is down; set `AGENTCONNECT_REQUIRE_REDIS=1` to fail
instead.

Gates live in [tests/support/budgets.py](../../../tests/support/budgets.py).
Do not retune them after a run to hide a hang.
