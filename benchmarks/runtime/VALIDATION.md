# Runtime validation

Certifying hashed warm-find, overlap, neural, and stress numbers remain the Linux Performance artifact on [`a0a89f4`](https://github.com/AKKI0511/AgentConnect/commit/a0a89f42c296c9db752056262d7be334bee34236), recorded here as [`baseline.json`](baseline.json). That run used the retired `tests/m8/bench.py` harness. Budgets in [`tests/support/budgets.py`](../../tests/support/budgets.py) were not changed.

The current harness is pytest plus pytest-benchmark 5.3.0 under `benchmarks/runtime/`. Ordinary CI collects `tests/` only. Performance runs sequential pytest groups and uploads native benchmark JSON plus JUnit even when a group fails.

## GitHub Performance (historical, unchanged cases)

https://github.com/AKKI0511/AgentConnect/actions/runs/35290537847  
Artifact `m8-runtime-bench` (`failed_names: []`, elapsed 52.7 s), revision `a0a89f4`.

- CPython 3.12.3, Linux 6.17.0-1022-azure x86_64 glibc 2.39
- HashedEmbedder dim 384; FastEmbed 0.8.0 `BAAI/bge-small-en-v1.5`; onnxruntime 1.30.0; numpy 2.5.3
- redis-py 5.3.1, httpx 0.28.1, pydantic 2.13.5
- Redis `redis:8.2` (8.2.9)

| case | result | budget |
| --- | ---: | ---: |
| hashed redis embedded 1,000 p95 | 153 ms | 250 ms |
| hashed redis HTTP 1,000 p95 | 159 ms | 250 ms |
| hashed memory embedded 1,000 p95 | 93 ms | 250 ms |
| hashed redis embedded 100 p95 | 15 ms | 50 ms |
| overlap hashed redis 400 send p95 | 35 ms | 100 ms |
| hashed memory cold extra lag | 1.7 ms | 50 ms |
| hashed redis cold extra lag | 2.3 ms | 50 ms |
| fallback rebuild memory extra lag | 6.3 ms | 80 ms |
| fallback rebuild redis extra lag | 6.0 ms | 80 ms |

Neural 10/100 passed lag gates. Neural 1,000 is measured only (memory embedded p95 108 ms). Hashed 10,000 stress extra lag 151 ms against 500 ms.

Those `a0a89f4` Profile-update extra-lag figures (2.0 ms memory / 0.8 ms Redis) timed only `Team.find` after the join. They are not the Profile-update gate.

## Profile-update correction (join inside the probed window)

CPython 3.12.8, Redis 8.10.1 at `127.0.0.1:6380/15`. The specialist `Team.join` plus the ranking find are one probed operation. Top match is `writer@`. Measured on the retired harness with `--internal-phases` before this pytest-benchmark move.

| case | extra lag | budget |
| --- | ---: | ---: |
| hashed memory Profile update (join + find) | 15.1 ms | 50 ms |
| hashed redis Profile update (join + find) | 11.3 ms | 50 ms |
| hashed memory cold | 12.8 ms | 50 ms |
| hashed redis cold | 6.5 ms | 50 ms |
| fallback rebuild memory | 15.1 ms | 80 ms |
| fallback rebuild redis | 15.6 ms | 80 ms |

`test_injected_profile_update_stall_fails_the_gate` injects a 200 ms blocking stall inside `Team.join` during that window; extra lag exceeds the 50 ms budget. Ranking after a clean update still asserts `writer@`.

Linux CI on the measurement correction passed Python 3.11–3.14 on [`d24aa25`](https://github.com/AKKI0511/AgentConnect/commit/d24aa25bc5e7a73f0ee8e75b116b8bf8b7d5647b): https://github.com/AKKI0511/AgentConnect/actions/runs/35297204179.

## Harness review

The first migrated run on `599ae74` failed in overlap teardown because
`asyncio.Runner.run` rejected a Task on Python 3.12. It also measured Redis
1,000-member p95 at 259.6/259.7 ms against 250 ms. Its four-vCPU AMD EPYC 7763
runner had Redis medians of 246.6/249.7 ms; this was not just one extreme sample.
[Failed run and artifacts](https://github.com/AKKI0511/AgentConnect/actions/runs/35306837186).

The adapter now awaits coroutines, Tasks, and gather Futures on the same loop.
A regression test covers pending work between calls, completed Tasks, and errors;
it passed on CPython 3.11.12 and in the 3.12.8 default suite. The Redis helper
no longer retries immutable configuration or picks a hard-coded unrelated container.

Advisor local verification, Windows CPython 3.12.8, Redis 8.10.1:

- Default suite with required Redis: **693 passed**, 3 skipped, 5 deselected.
- Warm hashed matrix: **12 passed**; Redis 1,000-member maxima 228/245 ms.
- Overlap: **6 passed**; Redis send maximum 86 ms against a 100 ms p95 budget.
- Cold/update/fallback: **6 passed**; real FastEmbed: **9 passed** (lag gates);
  10,000-member stress: **1 passed**. Neural latency is measured, not gated.
- Ruff lint and format, all three lock checks, and generated schema freshness passed.

Local passes do not supersede the Linux miss. Budgets and Runtime code were not
changed during this harness review. A new Linux Performance run must pass before
this migration is accepted. See [README.md](README.md) for measurement boundaries
and the commands maintained for future contributors.

## Reproduce

Use the commands in [README.md](README.md) and [CONTRIBUTING.md](../../CONTRIBUTING.md).
The review host uses the existing dedicated container `agentconnect-m8-redis` on
port 6380. GitHub uses `redis:8.2` on port 6379, with DEBUG enabled and AOF at server
startup. RedisStore has a 64-connection pool; this is not a replica scaling claim.
