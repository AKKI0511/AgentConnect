# Tool experience

A small Team of deterministic specialists. Use it to judge AgentConnect's
Team MCP tools from a coding harness.

There is no experiment CLI, custom MCP client, or control server.

## Developer flow

1. Start the Team:

   ```bash
   cd examples/tool_experience
   uv sync
   uv run python team.py
   ```

   It prints an MCP URL such as `http://127.0.0.1:8765/mcp` and stays in
   the foreground. Ctrl+C stops the Team. Starting it again resets the
   memory-backed run.

   Port 8765 is the default so you can reuse the same URL. If that port
   is taken, the process exits with an error. Pass `--port` only when you
   need a different local port.

2. Add the printed URL with your harness's native MCP support. Do not
   paste a Session token for this loopback flow.

3. Give the coding agent [PROMPT.md](PROMPT.md) first (business
   assignment only). After that pass, give [CHECKLIST.md](CHECKLIST.md).
   Both phases belong in one Markdown report under `reports/`. Do not
   overwrite an earlier report.

## Operator, not a member

Loopback calls with no `Authorization` header use the Team's trusted
operator Membership. Operator has no mailbox and no Profile. Tool calls
in this setup are not an authenticated ordinary member Session, and they
do not test member Session recovery.

## What the Team contains

Five in-process `BaseAgent` teammates on Team `ship-desk`:

| Name | Role |
| --- | --- |
| `incident-triage` | Canary timeline, delayed forensics, hold recommendation |
| `metrics-analyst` | SLO numbers, valid zeros and empty lists |
| `changelog-scribe` | Paged 2.4.1 changes |
| `risk-reviewer` | Hold or ship from supplied facts |
| `press-liaison` | Customer status; later drafts include `tell` notices |

They overlap on purpose. Discovery rank is not a guarantee that the
first match can do the work. Use `get_profiles` to read selected
Profiles in one call.

A prior custom-CLI pass is recorded in
[reports/legacy-cli-baseline.md](reports/legacy-cli-baseline.md). That
run did not use native MCP.
