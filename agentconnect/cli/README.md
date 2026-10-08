# AgentConnect CLI

The `agentconnect` program is a person talking to a Team. Every verb an
Agent has, a person has. `up` starts the Runtime from
`agentconnect.toml` or `[tool.agentconnect]` in `pyproject.toml`.
The other commands call that Runtime over loopback HTTP as the reserved
`operator` Membership.

```bash
agentconnect init
agentconnect up
```

In another terminal:

```bash
agentconnect status
agentconnect find "someone who can draft a summary"
agentconnect ask assistant "What can you do?"
agentconnect trace <trace-id>
```

## Commands

- `init` — write `agentconnect.toml`, `agents/assistant.py`, and `tools/shared.py`
- `up` / `down` — start or stop the Team and hosted Agents
- `status` — members, kind, online state, Agent mailbox depths, open tickets
- `token issue` / `token revoke` — join credentials
- `find` — Directory search
- `ask` — send reply-expected work and wait
- `trace` — print the timeline for one causal operation
- `watch` — print new Trace events
- `doctor` — Team file, keys, and whether the Runtime is reachable
- `version` — package version

`up --detach` starts in the background. `down` stops the process started
for the selected Team file after verifying a matching start-time token.
Terminated and zombie processes count as gone; an unreadable identity
does not. State lives next to that file in `.agentconnect/<filename>.json`.
Failed stops and identity-query failures keep the state file. `up` will
not overwrite a record whose owner cannot be verified. A failed or
exiting `up` does not remove another launch's record. `up` prints the
Team file it selected and refuses if that Team is already running.

`--url` points any command at a Runtime that is already serving. `--file`
selects a Team file. Precedence is `--url`, then `--file`, then saved
state, then the nearest discovered Team file, then
`http://127.0.0.1:9000`. A missing or invalid `--file` fails; it does
not fall back to another Team.

`--json` prints machine-readable output on `status`, `find`,
`ask`, `trace`, and `token issue`.

## Team files

Discovery is nearest-directory first. In each directory,
`agentconnect.toml` beats `[tool.agentconnect]` in `pyproject.toml`.
YAML is last-resort compatibility after no ancestor TOML Team file
exists. Files are never merged. Relative `module:Name` imports resolve
from the selected file's directory.

`init` refuses when a Team file already exists. Use `--force` to replace
the starter files. Independently deployed Agents are not listed in the
file; they join with a token:

```bash
agentconnect token issue --name researcher
```

Then, in another process:

```python
await Researcher(name="researcher").join(
    "http://127.0.0.1:9000",
    join_token=issued_token,
)
```

## Hosted Agents

Each `[[tool.agentconnect.agents]]` entry is constructed by `up`.
`class` is a `BaseAgent` subclass, or a function
`create(name) -> BaseAgent` that returns an unjoined Agent. The starter
uses the factory:

```toml
[[tool.agentconnect.agents]]
class = "agents.assistant:create_assistant"
name = "assistant"
```

Use a factory when the Agent needs constructor arguments the Team file
cannot supply, such as a model id. The Team file is not a generic
constructor language.

`up` and `Team.serve` bind loopback only. To serve an authenticated Team
behind your own HTTP server, build the ASGI app with
`create_runtime_app(team)` from `agentconnect.team.http`.

## Extra MCP tools

`tools = ["tools.shared:ping"]` publishes extra callables on Team MCP.
Joining does not attach those extras to a model's tool list.
`team_tools()` and the prebuilt helper attach the six coordination
tools. Connecting a harness is a separate step: add the Team MCP URL
there, or call extras from Agent code yourself.
