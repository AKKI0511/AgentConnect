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

## Local default suite

`uv run --extra serve --extra cli --extra index --extra openai --extra redis pytest tests/ -q` with required Redis on CPython 3.12.8: **691 passed**, 1 failed, 3 skipped, 5 deselected, 167.76 s. The failure was `test_warm_ranking_400_stays_within_loop_budget` (106 ms extra lag vs 80 ms). The same test passed in isolation (0.28 s). That Windows full-suite tail is the previously documented 400-member timer flake; Linux CI is the certifying run. Ruff lint/format on the touched Python files passed. Isolated `benchmarks/runtime/test_phases.py` on this host: 6 passed in 2.55 s, Profile update ranked `writer@content-squad`.

pytest-benchmark 5.3.0, `asyncio.Runner` bridge, one completed operation per timing sample (`pedantic(..., iterations=1)`). Loop lag is a separate `LoopProbe` around the same public operations. Cold indexing and Profile update keep join work inside the timed/probed window. Phases, warm hashed, overlap, neural, and stress run as separate pytest processes.

A fresh GitHub Performance run on this harness is recorded when that workflow finishes.

## Reproduce

```powershell
docker start agentconnect-m8-redis
$env:REDIS_URL="redis://127.0.0.1:6380/15"
$env:AGENTCONNECT_REQUIRE_REDIS="1"
$env:AGENTCONNECT_REQUIRE_NEURAL="1"
$env:NO_PROXY="127.0.0.1,localhost"
uv run --extra serve --extra cli --extra index --extra openai --extra redis pytest tests/ -q
uv sync --group benchmark --extra serve --extra embeddings --extra redis
uv run --group benchmark --extra serve --extra embeddings --extra redis pytest -q --benchmark-warmup=off benchmarks/runtime/test_phases.py --benchmark-json=benchmarks/runtime/results/phases.json --junitxml=benchmarks/runtime/results/phases.xml
```

GitHub Redis DEBUG/AOF uses the documented service `command` override (`redis-server --enable-debug-command yes --appendonly yes`). Redis 8 treats `enable-debug-command` as immutable, so `CONFIG SET` after start fails. RedisStore uses `max_connections=64`.
