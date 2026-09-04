"""Serve a Team and print the MCP URL for Cursor or any MCP client.

``Team.serve()`` mounts the Team MCP server at ``{origin}/mcp``. Loopback
calls with no Authorization header run as the reserved ``operator``
Membership.

Run from the repo root::

    poetry run python examples/communication/mcp.py
"""

from __future__ import annotations

import asyncio
import json

from agentconnect.agent import BaseAgent
from agentconnect.team import Team


class Writer(BaseAgent):
    """Turns a request into a short draft and returns it."""

    profile = {
        "summary": "Writes short drafts from notes.",
        "skills": [
            {
                "name": "drafting",
                "description": "Turn research notes into a two-paragraph draft.",
            }
        ],
        "tags": ["writing"],
    }

    async def handle(self, msg, ctx):
        if msg.kind != "request":
            return None
        return f"Draft complete for {msg.content!r}."


async def main() -> None:
    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    await writer.join(team)
    try:
        origin = await team.serve()
        snippet = {
            "mcpServers": {
                "content-squad": {"url": team.mcp_url},
            }
        }
        print(f"Team origin: {origin}")
        print(f"MCP URL:     {team.mcp_url}")
        print("Add this to Cursor MCP config (.cursor/mcp.json):")
        print(json.dumps(snippet, indent=2))
        print("Leave this process running, then ask Cursor to find a writer.")
        await asyncio.Event().wait()
    finally:
        await writer.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
