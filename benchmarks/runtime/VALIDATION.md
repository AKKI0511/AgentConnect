# Runtime validation

## Verified reference run

Runtime and benchmark code: [`5f45f7a`](https://github.com/AKKI0511/AgentConnect/commit/5f45f7aca8b978e73d39175b178f5e8e0ee5f43f).

- [CI](https://github.com/AKKI0511/AgentConnect/actions/runs/35312474992):
  Python 3.11–3.14, code/schema/locks, Windows imports, distribution, and aggregator passed.
- [Performance](https://github.com/AKKI0511/AgentConnect/actions/runs/35312474998):
  **34 passed**, zero failures or errors in all five JUnit reports. Raw samples and
  reports are in its `runtime-bench` artifact. The tested PR merge tree was
  `5fe649debdaaf08d48a341c0c01b3e03d397feab`.

The performance runner had four vCPUs on an AMD EPYC 9V45, Linux x86_64,
CPython 3.12.3, and Redis 8.2. Package versions: pytest-benchmark 5.3.0,
redis-py 5.3.1, hiredis 3.4.1, FastEmbed 0.8.0 (`BAAI/bge-small-en-v1.5`),
onnxruntime 1.30.0, numpy 2.5.3, httpx 0.28.1, and pydantic 2.13.5.

| Case | Result | Budget |
| --- | ---: | ---: |
| Hashed Redis embedded / HTTP, 1,000, p95 | 147 / 150 ms | 250 ms |
| Hashed memory embedded / HTTP, 1,000, p95 | 88 / 162 ms | 250 ms |
| Hashed Redis embedded / HTTP, 100, p95 | 14 / 16 ms | 50 ms |
| Redis send during 400-member find, p95 | 31 ms | 100 ms |
| Profile update including join, memory / Redis extra lag | 0.8 / 0.4 ms | 50 ms |
| Hashed 10,000 stress extra lag | 108 ms | 500 ms |

All supported hashed store/transport/size gates passed. Cold indexing, fallback
rebuild, renewal, and expiry passed. Real neural 10/100 passed loop-lag gates;
neural latency is reported, not tested against hashed budgets. Neural 1,000 is
exploratory (161 ms p95 memory embedded); 10,000 hashed is stress only. Eight
concurrent finders were observed with one Directory worker and one embedder worker.
This is a single-Runtime workload, not a simultaneous-agent throughput guarantee.

## Local verification

Windows, CPython 3.12.8, Redis 8.10.1 on the dedicated port 6380 container:

- Final native-parser default suite: **693 passed**, 3 skipped, 5 deselected.
- All 34 migrated benchmark cases passed before the parser dependency change.
  The subsequent hiredis trial passed both Redis 1,000-member cases, with medians
  of 178/176 ms versus 186/197 ms in the earlier local matrix.
- Redis store and benchmark adapter checks: **14 passed** on CPython 3.11.12.
- Ruff lint/format, all three lockfile checks, and schema freshness passed.

## Preserved failures and limits

The [first migrated run](https://github.com/AKKI0511/AgentConnect/actions/runs/35306837186)
failed because the adapter passed Tasks to `asyncio.Runner.run` on Python 3.12.
The adapter now awaits coroutines, Tasks, and gather Futures on one loop; ordinary
CI covers pending and completed Tasks and exception propagation.

That run also missed Redis 1,000-member p95 at 260 ms. The
[adapter-corrected run](https://github.com/AKKI0511/AgentConnect/actions/runs/35311910082)
reproduced the latency miss at 267/271 ms, while all other groups passed. Both
used an older EPYC 7763 host. The reference run uses a newer CPU as well as hiredis:
it is not a controlled estimate of the parser's speedup or proof of the budget on
every host. Budgets were not changed. Investigate failures using raw samples and
host metadata; do not retry until green or turn these results into universal SLAs.

The documentation-only repeat on `a460932` returned to EPYC 7763 and missed
Redis 1,000 at 257/273 ms despite hiredis:
[run](https://github.com/AKKI0511/AgentConnect/actions/runs/35312718095).
This keeps merge blocked; the faster-host result alone does not resolve it.
Profiling identified repeated cached-vector validation as a large CPU cost.
The follow-up preserves validation and normalization, but avoids redundant type
checks/conversion for plain floats and uses a built-in iterator for dot products.
A local 10,000-call normalization probe measured 0.397 s versus 0.619 s before;
full public-path gates are required for acceptance, not this microbenchmark.
The local warm matrix passed all 12 cases after the change; Redis 1,000 p95
was embedded 150.4 ms, http 173.8 ms. Four focused vector checks passed on CPython
3.11.12. The final CPython 3.12.8 suite passed 693 tests (3 skipped,
5 deselected); Ruff passed. Linux gates are pending for this change.

[baseline.json](baseline.json) preserves the earlier `a0a89f4` results from the
retired harness as historical evidence. Its Profile-update figures timed find
only, so they are not the current join-plus-find gate. Current correctness tests
also prove that a 200 ms stall inside Profile-update join fails the lag probe.

## Reproduce

[README.md](README.md) defines workloads, measurement boundaries, and commands.
[CONTRIBUTING.md](../../CONTRIBUTING.md) sets up dedicated Redis. GitHub starts it
with DEBUG and AOF enabled. Generated results stay out of Git; accepted reference
runs are recorded here rather than replacing the baseline on every run.
