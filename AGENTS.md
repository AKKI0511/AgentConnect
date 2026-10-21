# AgentConnect repository context

AgentConnect is a runtime for Teams of independent AI agents. Each agent can use its own harness, tools, and memory. The Runtime provides discovery, messaging, and work tracking; it is not a wire standard.

This file describes the codebase and its constraints. There is no required editor, agent harness, or sequence of development steps.

## Code map

| Package | Responsibility |
| --- | --- |
| `agentconnect.core` | Public data models and schema projection |
| `agentconnect.agent` | Client SDK and handler context. `BaseAgent` owns the connection. |
| `agentconnect.team` | Team Runtime, directory, mailboxes, tickets, and stores |
| `agentconnect.transport` | Client Session transports |
| `agentconnect.mcp` | Team MCP server |
| `agentconnect.cli` | Command-line entry point |
| `agentconnect.config` | Team configuration |
| `agentconnect.prebuilt` | Optional agent helpers and integrations |
| `agentconnect.index` | Optional published-directory Index |

Tests mirror these packages under `tests/`. Runnable examples are independent uv projects under `examples/`. Qualitative Team MCP research lives under `experiments/`. The public website and generated Python reference live in `docs-v2/`. Handwritten pages remaining under `docs/source/` are an inactive migration reference.

## Contracts and boundaries

- `spec/` describes the public contract. `spec/schema/schema.ts` owns public structure; `agentconnect/core/` is its Python projection. Public field changes affect both.
- Public Python models are frozen Pydantic models with matching field names, rejected extra fields, and discriminated tagged unions. Schema round-trip tests cover that correspondence.
- Validation happens at transport boundaries. Trusted internal construction avoids repeated validation. Model-facing tools return JSON.
- `core` imports no sibling packages. `agent` and `team` do not import each other; neither do `agent` and `mcp`. Those packages do not depend on `prebuilt`. Import tests cover these boundaries.
- Model-provider integrations stay behind extras and lazy imports. Public annotations and `py.typed` support SDK consumers.
- Team, Runtime, Membership, Session, Message, Delivery, Ticket, Thread, Address, and Skill have distinct meanings in the public contract.

## Generated content

When changing model-facing tool descriptions, parameter guidance, prompts, or
public SDK docstrings, use [agent-tool-design](.agents/skills/agent-tool-design/SKILL.md)
for tool-facing text and [python-api-reference](.agents/skills/python-api-reference/SKILL.md)
for Python reference documentation.
Preserve tested wording unless behavior or evidence calls for a change. Public
documentation explains current usage, not implementation history. Inspect the
delivered interface when changing model-facing text.

For website work, follow [docs-v2/AGENTS.md](docs-v2/AGENTS.md).

`spec/schema/schema.json` is generated from `schema.ts`. Generated Python reference pages under `docs-v2/api/` come from `docs-v2/scripts/generate_api.py`. Edit SDK docstrings, then regenerate; do not edit those MDX files by hand.

Website pages are self-contained. The root `CHANGELOG.md` is the canonical release history; other repository references use links.

## Verification

[CONTRIBUTING.md](CONTRIBUTING.md) has environment setup, checks, Redis,
lockfiles and release procedures. Tests mirror the package tree.

Runtime performance is separate from correctness and retrieval quality:
[Runtime benchmarks](benchmarks/runtime/README.md),
[request/reply](benchmarks/runtime/request_reply/README.md),
[public SDK collaboration](benchmarks/runtime/public_sdk/README.md).
Keep fixed budgets, real backends and failed evidence.

Run [discovery retrieval](benchmarks/discovery/README.md) locally when Profile
text or Directory ranking changes. Keep failed neural loads in artifacts;
do not substitute hashed ranks or retune gates after a run.

For schema changes, run `npm --prefix spec/schema ci`, then `npm --prefix
spec/schema run generate` and `npm --prefix spec/schema run check`.
For website changes, follow [docs-v2/AGENTS.md](docs-v2/AGENTS.md).

## Review context

The support matrix is in `.github/workflows/main.yml`; package metadata is
in `pyproject.toml`. Report local results separately from hosted CI.

Before committing Python or toolchain changes, run the full suite and both Ruff
checks on the final changes. Verify compatibility-sensitive changes on the minimum
supported Python version. Refresh affected locks and generated files. Validate
what will actually be committed, including in a shared checkout; do not weaken
assertions or bypass hooks to make a check pass. Report the Python versions and
checks actually run, distinguishing local results from GitHub CI. Repeat checks
only when subsequent changes or failures justify it.

A shared checkout may contain unrelated changes. Keeping those separate makes the resulting diff reviewable. [CONTRIBUTING.md](CONTRIBUTING.md) has more setup and contribution information.
