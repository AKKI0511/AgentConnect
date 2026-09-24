# Request/reply exchange results

Accepted local run of the workload in [README.md](README.md). Generated
pytest-benchmark JSON is gitignored; this file is the durable record.

## Workload

N independent caller/worker pairs. Each pair keeps one request in flight.
Timed work is `send(collect=ticket)` → `lease` → `reply` → `get_result`
with body `"ping"` / `"pong"`. No Directory `find`, no model, no Agent
handler. One warmup trip per pair is outside the timed window. A trip that
exceeds 15 s or never leases is a timeout. Percentiles use completed trips
only. Throughput is completed trips / batch wall time.

| Setting | Value |
| --- | --- |
| Pairs (concurrency) | 1, 8, 32 |
| Trips per pair | 20 |
| Runtime processes | 1, plus Redis HTTP at 2 |
| Two-replica split | send/get_result on process A, lease/reply on process B |
| Redis | 8.2.10 at `redis://127.0.0.1:6380/15`, hiredis 3.4.1 |

## Host

Windows 11, CPython 3.12.8, 13th Gen Intel Core i7-13700H (20 logical
processors). Packages: pytest-benchmark 5.3.0, redis-py 5.3.1, hiredis 3.4.1,
httpx 0.28.1, pydantic 2.13.5. Tree was dirty on `717fc31` while this harness
and the Redis apply snapshot were added. This is one desktop, not a latency
SLA and not GitHub runner hardware.

## Strongest defensible points

Defensible means zero errors and timeouts, throughput that still rises or
holds versus the next-lower N, and p95 that has not collapsed on that
backend.

| Path | Concurrency | Throughput | p95 | Errors / timeouts |
| --- | ---: | ---: | ---: | --- |
| Memory, embedded, 1 Runtime | **32 pairs** | **1222** round-trips/s | **1.3 ms** | 0 / 0 |
| Memory, HTTP, 1 Runtime | **8 pairs** | **195** round-trips/s | **61 ms** | 0 / 0 |
| Redis, HTTP, 1 Runtime | **8 pairs** | **44** round-trips/s | **288 ms** | 0 / 0 |
| Redis, HTTP, 2 Runtime processes | **8 pairs** | **55** round-trips/s | **238 ms** | 0 / 0 |

Embedded memory still holds ~1200 round-trips/s at 32 pairs with
~1 ms p95. That is the tightest AgentConnect-only figure on this host.

HTTP on memory completes at 32 pairs with zero errors, but throughput falls
from 195 to 97 round-trips/s and p95 jumps from 61 ms to 703 ms. 8 pairs is
the last HTTP-memory point that still scales.

Redis HTTP on one Runtime is the durable production-like path. 8 pairs is
the last zero-error point whose throughput still rises versus 1 pair (15 →
44 round-trips/s). At 32 pairs every trip completed, but p95 is 3.7 s and
throughput falls to 19 round-trips/s.

Two Runtime processes sharing Redis, with send on A and lease/reply on B,
now match or slightly beat one process at 8 pairs (55 vs 44 round-trips/s).
That is not a 2× replica-safety claim. It is the same split probe after
Redis apply stopped paying one round-trip per watched key.

## Redis apply snapshot

`RedisStore.apply` used to GET each WATCHed document and each index card or
score on its own round-trip. It now MGETs documents and packs ZCARD/ZSCORE
on the WATCH connection. Semantics are unchanged: same overlay, same WATCH
retry, same MULTI/EXEC. Compared with the previous accepted matrix on this
host, Redis HTTP at 8 pairs went from **20 → 44** round-trips/s and p95
**785 → 288 ms**. Redis embedded at 8 pairs went from **21 → 58**
round-trips/s and p95 **690 → 231 ms**. Redis N=32 timeouts dropped from
36 / 1 / 35 (embedded / HTTP / two-process) to **0**.

## Full matrix

p50 / p95 / p99 in milliseconds. `ok` is completed / attempted.

| Store | Access | Replicas | N | ok | p50 | p95 | p99 | round-trips/s | err | timeout |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| memory | embedded | 1 | 1 | 20/20 | 0.8 | 0.9 | 0.9 | 1359 | 0 | 0 |
| memory | embedded | 1 | 8 | 160/160 | 0.7 | 0.9 | 1.3 | 1396 | 0 | 0 |
| memory | embedded | 1 | 32 | 640/640 | 0.7 | 1.3 | 2.8 | 1222 | 0 | 0 |
| memory | HTTP | 1 | 1 | 20/20 | 4.7 | 5.2 | 5.2 | 210 | 0 | 0 |
| memory | HTTP | 1 | 8 | 160/160 | 38.3 | 61.3 | 73.7 | 195 | 0 | 0 |
| memory | HTTP | 1 | 32 | 640/640 | 278.1 | 703.1 | 926.5 | 97 | 0 | 0 |
| redis | embedded | 1 | 1 | 20/20 | 38.4 | 59.2 | 62.8 | 25 | 0 | 0 |
| redis | embedded | 1 | 8 | 160/160 | 117.0 | 230.8 | 309.0 | 58 | 0 | 0 |
| redis | embedded | 1 | 32 | 640/640 | 1053 | 3237 | 4345 | 23 | 0 | 0 |
| redis | HTTP | 1 | 1 | 20/20 | 63.9 | 85.7 | 86.6 | 15 | 0 | 0 |
| redis | HTTP | 1 | 8 | 160/160 | 150.2 | 288.3 | 455.2 | 44 | 0 | 0 |
| redis | HTTP | 1 | 32 | 640/640 | 1246 | 3657 | 4954 | 19 | 0 | 0 |
| redis | HTTP | 2 | 8 | 160/160 | 128.0 | 238.0 | 296.3 | 55 | 0 | 0 |
| redis | HTTP | 2 | 32 | 640/640 | 685.8 | 4099 | 6357 | 24 | 0 | 0 |

Redis N=1 p95 still moves between repeats on this desktop. Use the N=8
durable row for comparisons. CI gates 100% completion at N≤8 and at memory
N=32. Redis and two-replica N=32 stay measured. The 5 s p95 stall bound is
hang detection, not an SLA.
