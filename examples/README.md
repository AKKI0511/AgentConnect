# Examples

Three uv projects. Each one installs this checkout of AgentConnect.

| Project | What it shows |
| --- | --- |
| [quickstart](quickstart/README.md) | One Team. An editor asks a writer, the writer asks a researcher, the Ticket is the draft. Deterministic by default. `--live` calls OpenAI. |
| [recipes](recipes/README.md) | One lesson per file: discovery, deferred collection, Thread history, HTTP join, MCP, and a Team file. |
| [tool_experience](tool_experience/README.md) | Foreground ship-desk Team. Copy the printed MCP URL into a coding harness and judge the Team tools with [PROMPT.md](tool_experience/PROMPT.md). |

```bash
cd examples/quickstart
uv sync
uv run python -m team_demo
```

```bash
cd examples/recipes
uv sync
uv run python discover.py
```

```bash
cd examples/tool_experience
uv sync
uv run python team.py
```

`collect="wait"` can return an `open` Ticket. That wait is not the work deadline. The recipes keep polling `get_result` until a terminal state or the Ticket deadline. They do not print success for open, failed, declined, or expired work.
