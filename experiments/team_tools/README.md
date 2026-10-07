# Team tools experiment

A durable, harness-independent environment for qualitative Team MCP
tool-use research. It is not a user example, an automated benchmark, or
a mandatory LLM release gate. CI checks deterministic startup, fixture
behavior, and MCP reachability.

## When to run it

Use this after Team MCP tools, advertised descriptions, or ship-desk
fixture behavior change. Skip it for unrelated Runtime or packaging work.

## Start

```bash
cd experiments/team_tools
uv sync
uv run python team.py
```

The process prints an MCP URL such as `http://127.0.0.1:8765/mcp` and
stays in the foreground.

Port 8765 is the default so you can keep the same URL. If that port is
taken, the process exits with an error. Pass `--port` only when you need
a different local port.

Ctrl+C stops the Team. Starting it again resets the memory-backed run.
Tickets and history from the previous process are gone.

## Connect

Add the printed URL with the coding harness's native MCP support. Do not
paste a Session token for this loopback flow.

After descriptor changes, verify the descriptions the judging agent
actually loaded. HTTP `tools/list` is not enough. Refresh native MCP,
then confirm the six tools and their text. If the catalog is stale, stop.
Do not rotate ports or edit harness configuration to force a refresh.

## Judge

1. Give [PROMPT.md](PROMPT.md). The assignment is uncoached. The judge
   must not read fixture source or earlier reports.
2. After that pass, give [CHECKLIST.md](CHECKLIST.md).
3. Save one Markdown report under `reports/`. That directory is
   gitignored and is created when you write the first file. Do not
   overwrite an earlier report.

Do not add LLM teammates, custom MCP clients, proxies, an experiment
CLI, harness configuration editors, provider adapters, or an evaluator
framework.

## Operator, not a member

Loopback calls with no `Authorization` header use the Team's trusted
operator Membership. Operator has no mailbox and no Profile. Tool calls
here are not an authenticated member Session, and they do not test
member Session recovery.

## Teammates

Five in-process `BaseAgent` specialists on Team `ship-desk`:

| Name | Role |
| --- | --- |
| `incident-triage` | Canary timeline, delayed forensics, hold recommendation |
| `metrics-analyst` | SLO numbers, including a valid zero and empty lists |
| `changelog-scribe` | Paged 2.4.1 changes |
| `risk-reviewer` | Hold or ship from supplied facts |
| `press-liaison` | Customer status; later drafts can include `tell` notices |

They overlap on purpose. Rank from `find` is not a guarantee that the
first card can do the work. Use `get_profiles` to read selected Profiles
in one call.
