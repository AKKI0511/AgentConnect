# M8 Runtime validation

Tracked on `feat/m8-runtime-release-gate` from `2983c4e`. M8 stays open until Linux CPython 3.11–3.14 `CI` and the `Performance` workflow pass on this revision.

Budgets are unchanged in [`budgets.py`](budgets.py). Entry point: `python tests/m8/bench.py`. Cold-index, Profile-update, and fallback-rebuild cases run in a child process so they do not share a heap with 1,000-member finds.

## Provenance (local CPython 3.12.8)

- HashedEmbedder, dim 384
- FastEmbed 0.8.0, `BAAI/bge-small-en-v1.5`, onnxruntime 1.30.0, numpy 2.5.3
- redis-py 5.3.1, httpx 0.28.1, pydantic 2.13.5
- Redis 8.10.1 at `127.0.0.1:6380/15`
- Host: Windows 11 10.0.26200, i7-13700H

Those versions are also written into the bench JSON `provenance` object.

## Local checks (this tree, not GitHub)

| check | result |
| --- | --- |
| Ruff lint + format | pass |
| `uv lock --check` | pass |
| `pytest tests/ -q` with required Redis | **692 passed**, 3 skipped, 6 deselected, 139.41 s |
| `tests/m8/test_discovery_gate.py` Runtime cold / update / rebuild | pass (public `Team.join` / `Team.find`) |
| Isolated Directory rebuild unit test | preserved |
| Full `bench.py --require-neural --stress` | see below |
| GitHub `CI` (Linux 3.11–3.14) | not run |
| GitHub `Performance` | not run |

Schema was not edited; npm schema freshness was not rerun.

## Public Runtime phases (20 long Profiles, embedded)

Lag is extra delay beyond the 10 ms probe. Rebuild uses the existing 80 ms extra-lag budget. Cold and Profile-update use the 50 ms budget at 20 members. Warm long ranking is labeled warm and is not a rebuild.

| case | extra lag | budget | notes |
| --- | ---: | ---: | --- |
| hashed memory cold index + first find | 14.5 ms | 50 ms | wall 96 ms |
| hashed memory warm | 2.2 ms | 50 ms | p95 3.8 ms |
| hashed memory Profile update | 1.2 ms | 50 ms | top `writer@` after reconnect |
| fallback rebuild memory | 13.5 ms | 80 ms | 23 embed calls, then hashed |
| hashed redis cold index + first find | 6.4 ms | 50 ms | wall 347 ms includes joins |
| hashed redis warm | 0 ms | 50 ms | p95 13.9 ms |
| hashed redis Profile update | 12.7 ms | 50 ms | top `writer@` |
| fallback rebuild redis | 15.2 ms | 80 ms | hashed fallback confirmed |

Pytest covers the same three public paths on MemoryStore in the default suite.

## Latest local full bench

Windows CPython 3.12.8, required Redis and FastEmbed, `--stress`. Phase cases above passed. Hashed Redis 1,000 p95 was 244 ms embedded and 248 ms HTTP against 250 ms. Redis overlap send p95 was **103.5 ms** against 100 ms. Hashed Redis embedded 100 p95 was **54.9 ms** against 50 ms (p50 26 ms; extra lag 5 ms). Those two misses are local 20-sample tails on this host; extra lag stayed inside the loop budgets. Neural 10/100 passed lag gates. Neural 1,000 remains measured/unsupported (p95 273 ms). Hashed 10,000 stress extra lag 81 ms against 500 ms.

Earlier advisor-review JSON remains historical; do not mix its HTTP burst numbers with this run.

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

PR CI is Linux correctness plus Redis. Performance is `.github/workflows/perf.yml` / `make perf`.

## Remaining before M8 Done

- Push the intended commit and verify GitHub `CI` on CPython 3.11–3.14 with Redis, then a `Performance` run with FastEmbed required.
- Record those GitHub outcomes separately from the Windows numbers above.
- Keep neural 1,000 and hashed 10,000 labeled unsupported / stress.
- Do not start M9.
