"""Serve a Team and print the MCP URL for Cursor or any MCP client.

``Team.serve()`` mounts the Team MCP server at ``{origin}/mcp``.
Loopback calls with no Authorization header run as the reserved
``operator`` Membership when the HTTP peer is loopback. A reverse
proxy in front of that listener needs a Session token.

Run from ``examples/recipes``::

    uv run python team_mcp.py
    uv run python team_mcp.py --once
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from agentconnect import AgentProfile, BaseAgent, Context, MailboxMessage, Skill, Team


class Writer(BaseAgent):
    """Turns a request into a short draft and returns it."""

    profile = AgentProfile(
        summary="Writes short drafts from notes.",
        skills=[
            Skill(
                name="drafting",
                description="Turn research notes into a two-paragraph draft.",
            )
        ],
        tags=["writing"],
    )

    async def handle(self, msg: MailboxMessage, ctx: Context) -> str | None:
        if msg.kind != "request":
            return None
        return f"Draft complete for {msg.content!r}."


async def main(*, once: bool) -> None:
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
        if once:
            return
        print("Leave this process running, then ask Cursor to find a writer.")
        await asyncio.Event().wait()
    finally:
        await writer.leave()
        await team.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--once",
        action="store_true",
        help="Print the MCP URL and exit.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    try:
        asyncio.run(main(once=args.once))
    except KeyboardInterrupt:
        raise SystemExit(0) from None
