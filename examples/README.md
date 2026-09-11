# Examples

Two uv projects. Each one installs this checkout of AgentConnect.

| Project | What it shows |
| --- | --- |
| [quickstart](quickstart/README.md) | One Team. An editor asks a writer, the writer asks a researcher, the Ticket is the draft. Deterministic by default. `--live` calls OpenAI. |
| [recipes](recipes/README.md) | One lesson per file: discovery, deferred collection, Thread history, HTTP join, MCP, and a Team file. |

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

`collect="wait"` can return an `open` Ticket. That wait is not the work deadline. The recipes keep polling `get_result` until a terminal state or the Ticket deadline. They do not print success for open, failed, declined, or expired work.
