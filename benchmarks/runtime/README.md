# Runtime benchmarks

These benchmarks measure completed public Runtime operations, including memory
and Redis storage and embedded and HTTP access. They are separate from the
ordinary correctness suite under `tests/`.

## Run

Start the dedicated test Redis described in [CONTRIBUTING.md](../../CONTRIBUTING.md).
Install the benchmark dependencies, then choose a group:

```bash
uv sync --locked --group benchmark --extra serve --extra embeddings --extra redis
uv run --no-sync pytest benchmarks/runtime/test_warm_find.py -q --benchmark-json=benchmarks/runtime/results/warm.json
```

| File | What it checks |
| --- | --- |
| `test_phases.py` | Cold indexing, Profile update including join, fallback rebuild |
| `test_warm_find.py` | Hashed search latency and loop responsiveness at 10, 100, 1,000 members |
| `test_overlap.py` | Send, lease renewal, and expiry while discovery runs |
| `test_neural.py` | Real local FastEmbed at 10 and 100; 1,000 is exploratory |
| `test_stress.py` | 10,000 hashed members; responsiveness only |

Use `make perf` where Make is installed to run all five groups in separate,
sequential processes. Otherwise run each file with the command above, or choose
the branch in GitHub Actions → **Performance** → **Run workflow**. FastEmbed
downloads its model on first use; no hosted provider or API key is needed.

## Measurements and evidence

pytest-benchmark owns timing, statistics, and JSON output. Warm tests use 20 rounds
with one completed request per round. Setup and warmup stay outside warm timings.
A small `asyncio.Runner` adapter keeps each Team on one event loop. The separate
10 ms loop probe measures extra scheduling delay while work runs. Cold and update
phase timings include that probe's final tick; their gate is loop lag, not latency.

Budgets live in [tests/support/budgets.py](../../tests/support/budgets.py). These
are workload-specific regression gates, not latency guarantees for every machine
or a claim that 1,000 agents can all execute simultaneously. Do not increase a
budget or retry until green to hide a failure. Check the failed samples and host
conditions; explain any rerun or changed workload.

Performance runs automatically for relevant Runtime, benchmark, and dependency
changes, and can be dispatched before a release. Each group runs even if an earlier
group fails. Actions saves raw JSON samples and JUnit pass/fail reports as the
`runtime-bench` artifact, including failures. Ordinary CI checks correctness on
Python 3.11–3.14 with real Redis, plus schema, locks, imports, and distribution.

Generated results are ignored by Git. [VALIDATION.md](VALIDATION.md) records
accepted runs and limitations; [baseline.json](baseline.json) is a small historical
reference, not an automatically updated target. Compare results with their commit,
hardware, Python, and backend versions. Benchmark tools are development dependencies
and are not installed for library users.
