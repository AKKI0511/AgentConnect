# Runtime validation

## Accepted Runtime and benchmark code

Revision [`5cd0497`](https://github.com/AKKI0511/AgentConnect/commit/5cd0497d3182a3e621000f94b78d42b39d8a5431):

- [CI](https://github.com/AKKI0511/AgentConnect/actions/runs/35313192268):
  Python 3.11–3.14, code/schema/locks, Windows imports, distribution, and aggregator passed.
- [Performance](https://github.com/AKKI0511/AgentConnect/actions/runs/35313192236):
  **34 passed**, zero failures/errors across all five JUnit reports. The
  `runtime-bench` artifact contains raw samples and metadata. The tested PR merge
  tree was `82a68810e43e8a6575bf35daec76b3f123ec3386`.

Reference machine: four vCPUs on AMD EPYC 9V74, Linux x86_64, CPython 3.12.3,
Redis 8.2. Packages: pytest-benchmark 5.3.0, redis-py 5.3.1, hiredis 3.4.1,
FastEmbed 0.8.0 (`BAAI/bge-small-en-v1.5`), onnxruntime 1.30.0, numpy 2.5.3,
httpx 0.28.1, pydantic 2.13.5. Budgets are unchanged.

| Case | Result | Budget |
| --- | ---: | ---: |
| Hashed Redis embedded / HTTP, 1,000, p95 | 227 / 217 ms | 250 ms |
| Hashed memory embedded / HTTP, 1,000, p95 | 141 / 221 ms | 250 ms |
| Redis send during 400-member find, p95 | 50 ms | 100 ms |
| Profile update including join, memory / Redis extra lag | 0.1 / 2.4 ms | 50 ms |
| Hashed 10,000 stress extra lag | 114 ms | 500 ms |

All supported hashed store/transport/size gates passed. Cold indexing, fallback
rebuild, renewal, and expiry passed. Real neural 10/100 passed loop-lag gates;
neural latency is measured, not gated by hashed budgets. Neural 1,000 is exploratory
(162 ms p95 memory embedded); 10,000 hashed is stress only. Eight concurrent finders
were observed with one Directory worker and one embedder worker. This is one Runtime
process, not a simultaneous-agent throughput or universal hardware guarantee.

## Local verification

Windows CPython 3.12.8, dedicated Redis 8.10.1 at port 6380:

- Final default suite: **693 passed**, 3 skipped, 5 deselected.
- Final warm matrix: **12 passed**; Redis 1,000 p95 150/174 ms.
- Earlier local checks passed all 34 migrated benchmark cases across five processes.
- CPython 3.11.12: four vector checks passed after the final optimization;
  14 Redis store/adapter checks passed after the hiredis dependency change.
- Ruff lint/format, all three lockfile checks, and schema freshness passed.

## Preserved failures and interpretation

The [first migrated run](https://github.com/AKKI0511/AgentConnect/actions/runs/35306837186)
failed because `asyncio.Runner.run` rejected Tasks on Python 3.12. The adapter now
awaits coroutines, Tasks, and gather Futures on one loop; ordinary CI covers that.

Redis 1,000-member p95 missed at 260–273 ms on EPYC 7763 in that run and subsequent
[adapter-corrected](https://github.com/AKKI0511/AgentConnect/actions/runs/35311910082)
and [native-parser](https://github.com/AKKI0511/AgentConnect/actions/runs/35312718095)
runs. A native-parser run on newer EPYC 9V45 passed, so its speedup cannot be
attributed solely to hiredis. Merge was held for the slower-host failure.

Profiling then identified repeated cached-vector validation as a large CPU cost.
The final optimization removes redundant checks/conversions for plain floats and
uses a built-in iterator for dot products. It preserves normalization, dimensions,
finite-number checks, mixed integers/floats, and rejection of booleans and strings.
Local warm results improved and the full Linux gates passed on the reference host
above. Runner hardware varies: inspect samples and metadata when a gate fails;
do not retry until green, relax budgets to hide a miss, or claim universal SLAs.

[baseline.json](baseline.json) preserves the `a0a89f4` retired-harness results as
historical evidence. Its Profile-update numbers timed find only, so they are not
the current join-plus-find gate. The current suite proves that a 200 ms stall inside
Profile-update join fails the lag probe.

## Reproduce

[README.md](README.md) defines workloads, timing boundaries, and commands.
[CONTRIBUTING.md](../../CONTRIBUTING.md) sets up dedicated Redis. GitHub starts it
with DEBUG and AOF enabled. Generated results stay out of Git; update this record
for accepted reference runs, not for every ordinary CI run.
