# Recipes

Small programs for one lesson each. From this directory:

```bash
uv sync
uv run python discover.py
uv run python collect.py
uv run python history.py
uv run python http_join.py
uv run python team_mcp.py --once
```

`http_join.py` and `team_mcp.py` need the `serve` extra, which this project's
`uv sync` installs.

`team_mcp.py` without `--once` stays up so you can add `team.mcp_url` to
Cursor. Ctrl+C stops it.

`_wait.py` is a small Ticket helper used by the recipes. It polls until
a terminal state or the Ticket deadline. It is not a public SDK API.

Hosted Team file: [hosted/README.md](hosted/README.md).
