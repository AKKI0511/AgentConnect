"""A handler fans work out to another Agent without sharing Thread history.

``ctx.ask`` names the current Message as ``parent_id``, inherits an
omitted child deadline from that request, and starts a new Thread because
``editor`` is not in the incoming conversation. ``editor`` cannot read the
researcher/writer Thread.

Run from the repo root::

    poetry run python examples/communication/fanout.py
"""

from __future__ import annotations

import asyncio

from agentconnect.agent import BaseAgent, Context
from agentconnect.core.base import JsonValue
from agentconnect.core.message import MailboxMessage
from agentconnect.team import Team


class Editor(BaseAgent):
    """Tightens a draft. Has no history of the researcher/writer Thread."""

    profile = {
        "summary": "Edits short drafts for clarity.",
        "skills": [
            {
                "name": "editing",
                "description": "Tighten a draft without changing its meaning.",
            }
        ],
        "tags": ["writing"],
    }

    async def handle(self, msg: MailboxMessage, ctx: Context) -> JsonValue | None:
        if msg.kind != "request":
            return None
        return {"edit": msg.content, "parent_id": msg.parent_id}


class Writer(BaseAgent):
    """Drafts, then asks the editor on a new Thread."""

    profile = {
        "summary": "Writes short drafts from notes.",
        "skills": [
            {
                "name": "drafting",
                "description": "Turn notes into a two-paragraph draft.",
            }
        ],
        "tags": ["writing"],
    }

    async def handle(self, msg: MailboxMessage, ctx: Context) -> JsonValue | None:
        if msg.kind != "request":
            return None
        edited = await ctx.ask("editor", f"tighten: {msg.content}")
        if edited.state != "completed":
            ctx.defer()
            return None
        return {
            "draft": msg.content,
            "edited": edited.response.content,
            "child_parent": msg.id,
        }


class Researcher(BaseAgent):
    """Sends work and prints Tickets. Does not handle inbound work."""

    async def handle(self, msg: MailboxMessage, ctx: Context) -> JsonValue | None:
        return None


async def main() -> None:
    team = await Team("content-squad").start()
    editor = Editor(name="editor")
    writer = Writer(name="writer")
    researcher = Researcher(name="researcher")
    await editor.join(team)
    await writer.join(team)
    await researcher.join(team)
    try:
        ticket = await researcher.ask("writer", "outline the launch note")
        print("ticket:", ticket.state)
        if ticket.state == "completed":
            print("content:", ticket.response.content)
    finally:
        await researcher.leave()
        await writer.leave()
        await editor.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
