# M8 Runtime validation

Certifying revision: [`a0a89f4`](https://github.com/AKKI0511/AgentConnect/commit/a0a89f42c296c9db752056262d7be334bee34236) on `feat/m8-runtime-release-gate` ([PR 16](https://github.com/AKKI0511/AgentConnect/pull/16)). Budgets in [`budgets.py`](budgets.py) were not changed. Entry point: `python tests/m8/bench.py`. Cold-index, Profile-update, and fallback-rebuild cases run in a child process so they do not share a heap with 1,000-member finds.

Linux GitHub `CI` and `Performance` on this commit are the release evidence. Windows numbers below are local only.

## GitHub (certifying)

### CI

https://github.com/AKKI0511/AgentConnect/actions/runs/35290517112

Linux CPython **3.11, 3.12, 3.13, 3.14** with required Redis 8.2, plus Code and schema, Windows imports, and distribution install: **pass**.

Earlier commits on this branch are not that result: `c772acb` failed YAML parse (`NO_PROXY`/`no_proxy`); `95555eb` failed HTTP warmup counts and Redis restart discovery; `c9b3173` passed CI and failed Performance.

### Performance

https://github.com/AKKI0511/AgentConnect/actions/runs/35290537847  
Artifact `m8-runtime-bench` (`failed_names: []`, elapsed 52.7 s).

Provenance from the JSON:

- revision `a0a89f42c296c9db752056262d7be334bee34236`
- CPython 3.12.3, Linux 6.17.0-1022-azure x86_64 glibc 2.39
- HashedEmbedder, dim 384
- FastEmbed 0.8.0, `BAAI/bge-small-en-v1.5`, onnxruntime 1.30.0, numpy 2.5.3
- redis-py 5.3.1, httpx 0.28.1, pydantic 2.13.5
- Redis service `redis:8.2` (8.2.9 in the job log)

Public Runtime phases (20 long Profiles, extra lag vs 10 ms probe):

| case | extra lag | budget |
| --- | ---: | ---: |
| hashed memory cold | 1.7 ms | 50 ms |
| hashed memory Profile update | 2.0 ms | 50 ms |
| fallback rebuild memory | 6.3 ms | 80 ms |
| hashed redis cold | 2.3 ms | 50 ms |
| hashed redis Profile update | 0.8 ms | 50 ms |
| fallback rebuild redis | 6.0 ms | 80 ms |

Hashed warm `Team.find` p95 (budget 25/50/250 ms at 10/100/1,000):

| case | p95 | budget |
| --- | ---: | ---: |
| hashed redis embedded 1,000 | 153 ms | 250 ms |
| hashed redis HTTP 1,000 | 159 ms | 250 ms |
| hashed memory embedded 1,000 | 93 ms | 250 ms |
| hashed redis embedded 100 | 15 ms | 50 ms |
| overlap hashed redis 400 send | 35 ms | 100 ms |

Neural 10/100 passed lag gates on memory and Redis, embedded and HTTP. Neural 1,000 is measured only (memory embedded p95 108 ms). Hashed 10,000 stress extra lag 151 ms against 500 ms.

`c9b3173` used `BlockingConnectionPool` and missed hashed Redis 1,000 at 274/277 ms p95. `a0a89f4` restored `Redis.from_url` with `max_connections=64`. That is not a budget change.

## Local (Windows, not GitHub)

CPython 3.12.8, Redis 8.10.1 at `127.0.0.1:6380/15`, same FastEmbed 0.8.0 model, i7-13700H.

| check | result |
| --- | --- |
| Ruff lint + format | pass |
| `uv lock --check` | pass |
| `pytest tests/ -q` with required Redis | **692 passed**, 3 skipped, 6 deselected, 139.41 s |
| Runtime cold / update / rebuild pytest | pass (`Team.join` / `Team.find`) |

A full local `--require-neural --stress` bench on this host missed two 20-sample tails (hashed Redis 100 p95 54.9 ms vs 50 ms; overlap send 103.5 ms vs 100 ms). Extra lag passed. Those misses do not override the Linux Performance artifact.

## Reproduce

```powershell
docker start agentconnect-m8-redis
$env:REDIS_URL="redis://127.0.0.1:6380/15"
$env:AGENTCONNECT_REQUIRE_REDIS="1"
$env:NO_PROXY="127.0.0.1,localhost"
uv run --extra serve --extra cli --extra index --extra openai --extra redis pytest tests/ -q
uvx ruff@latest check agentconnect tests examples docs/generate_docs.py
uvx ruff@latest format --check agentconnect tests examples docs/generate_docs.py
uv lock --check
uv run --extra serve --extra embeddings --extra redis python tests/m8/bench.py --require-neural --stress
```

GitHub: PR CI is Linux correctness plus Redis. Performance is `.github/workflows/perf.yml` / `make perf` (`workflow_dispatch`).
