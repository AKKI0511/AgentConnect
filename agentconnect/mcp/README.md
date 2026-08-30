# AgentConnect MCP

One MCP server per Team. `Team.serve()` mounts it at `{origin}/mcp`. Point Cursor, Claude, or any MCP client at `team.mcp_url`.

Python hosts that do not speak MCP use `BaseAgent.team_tools()` instead. Those callables are bound to the Agent Session and do not go through MCP.

```python
from agentconnect.team import Team

team = await Team("content-squad").start()
url = await team.serve()
print(team.mcp_url)  # http://127.0.0.1:<port>/mcp
```

Cursor MCP config:

```json
{
  "mcpServers": {
    "content-squad": {
      "url": "http://127.0.0.1:9000/mcp"
    }
  }
}
```

## Tools

`find`, `ask`, `tell`, `get_result`, and `get_history`. Slow work returns a Ticket. Keep `ticket.id` for `get_result` and `thread_id` for `get_history`. The roster is the resource `agentconnect://team/roster`.

Loopback calls with no `Authorization` header run as the reserved `operator` Membership. A Bearer token is that member's `session_token`. Tool arguments never include `sender` or `session_token`.

See `examples/communication/mcp.py` and `examples/communication/tools.py`.
