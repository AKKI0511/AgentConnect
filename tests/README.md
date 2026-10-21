# Tests

The default suite lives under `tests/` and is collected by `pytest tests/`.
It covers public SDK, Team Runtime, MCP, CLI, schema, and installed-package
behavior. Memory and Redis stores, plus embedded and HTTP access, are part
of that suite.

```powershell
uv sync --locked --extra redis --extra embeddings --extra prebuilt
uv run --no-sync pytest tests/ -q
```

Replace `tests/` with a file or directory for a focused run. Redis cases skip
when Redis is down unless `AGENTCONNECT_REQUIRE_REDIS=1` or `CI=1`. Start the
dedicated test Redis from [CONTRIBUTING.md](../CONTRIBUTING.md).

| Area | What it checks |
| --- | --- |
| `tests/agent/` | Session, handlers, tickets, executed public examples |
| `tests/team/` | Runtime join, send, leases, retention, HTTP, Directory |
| `tests/mcp/` | Team MCP tools, advertised schemas, extra callables |
| `tests/cli/` | `init` / `up` / `down`, ownership, hosted construction |
| `tests/core/` | Schema projection and boundary rejection |
| `tests/prebuilt/` | Optional helpers with recorded models, no hosted LLM |
| `tests/imports/` | Package layout and lazy extras |
| `tests/support/` | Shared stores, LoopProbe, budgets. Not collected as tests |
| `tests/experiments/` | Ship-desk startup, MCP, messaging, and shutdown smoke |

Runtime latency and throughput are under `benchmarks/runtime/`. Retrieval
quality is under `benchmarks/discovery/`. Neither is part of `pytest tests/`.
