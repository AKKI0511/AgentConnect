"""Let an existing MCP harness discover teammates and ask them for help.

Connect the harness to `team.mcp_url` after `Team.serve()` starts the listener.
The harness owns installing the discovered tools into its model. Python
harnesses without MCP can adapt the Session-bound descriptors returned by
`BaseAgent.team_tools()`.

Custom hosts use `create_team_mcp` with a started Team to build an MCP Server;
construction does not start an HTTP listener. See `create_runtime_app` for
HTTP hosting and Session credential requirements.
"""

from agentconnect.mcp.server import create_team_mcp

__all__ = ["create_team_mcp"]
