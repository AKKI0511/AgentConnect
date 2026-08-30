"""Team MCP package: one server per Team.

``create_team_mcp(team)`` builds the server. ``Team.serve()`` mounts it at
``/mcp``. Point Cursor at ``team.mcp_url``. Frameworks that do not speak MCP
use ``BaseAgent.team_tools()`` instead.
"""

from agentconnect.mcp.server import create_team_mcp

__all__ = ["create_team_mcp"]
