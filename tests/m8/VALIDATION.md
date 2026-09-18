# M8 Runtime validation

Certifying hashed warm-find, overlap, neural, and stress numbers remain the Linux Performance artifact on [`a0a89f4`](https://github.com/AKKI0511/AgentConnect/commit/a0a89f42c296c9db752056262d7be334bee34236). Profile-update extra lag below is a later measurement: `Team.join` of the specialist Profile is inside the probed window, then `Team.find` ranks `writer@`. Budgets in [`budgets.py`](budgets.py) were not changed.

## GitHub Performance (unchanged cases)

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

Those `a0a89f4` Profile-update extra-lag figures (2.0 ms memory / 0.8 ms Redis) timed only `Team.find` after the join. They are not the Profile-update gate anymore.

Linux CI on HEAD after this correction is recorded when that run finishes. Earlier: Python 3.11–3.14 passed on [`4b64e45`](https://github.com/AKKI0511/AgentConnect/commit/4b64e45) https://github.com/AKKI0511/AgentConnect/actions/runs/35291348448

## Local Profile-update correction (this change)

CPython 3.12.8, Redis 8.10.1 at `127.0.0.1:6380/15`. `python tests/m8/bench.py --internal-phases`. Join of the specialist Profile plus the ranking find are one probed operation. Top match is `writer@`.

| case | extra lag | budget |
| --- | ---: | ---: |
| hashed memory Profile update (join + find) | 15.1 ms | 50 ms |
| hashed redis Profile update (join + find) | 11.3 ms | 50 ms |
| hashed memory cold | 12.8 ms | 50 ms |
| hashed redis cold | 6.5 ms | 50 ms |
| fallback rebuild memory | 15.1 ms | 80 ms |
| fallback rebuild redis | 15.6 ms | 80 ms |

`test_injected_profile_update_stall_fails_the_gate` injects a 200 ms blocking stall inside `Team.join` during that window; extra lag exceeds the 50 ms budget. Ranking after a clean update still asserts `writer@`.

## Local default suite

`uv run --extra serve --extra cli --extra index --extra openai --extra redis pytest tests/ -q` with required Redis: **692 passed**, 3 skipped, 8 deselected, 152.60 s. Ruff lint/format on the touched Python files passed.

## Reproduce

```powershell
docker start agentconnect-m8-redis
$env:REDIS_URL="redis://127.0.0.1:6380/15"
$env:AGENTCONNECT_REQUIRE_REDIS="1"
$env:NO_PROXY="127.0.0.1,localhost"
uv run --extra serve --extra cli --extra index --extra openai --extra redis pytest tests/ -q
uv run --extra serve --extra embeddings --extra redis python tests/m8/bench.py --internal-phases
```

GitHub Redis DEBUG/AOF is `CONFIG SET` after the stock `redis:8.2` image starts. RedisStore uses `max_connections=64`.
