"""Two Agents share a Thread. History rides with each Delivery.

``ask(..., thread_id=...)`` groups turns. The handler reads recent turns
from ``ctx.history`` and pages the rest with ``get_history``.
``collect="ticket"`` returns immediately; ``collect="wait"`` returns the
current Ticket after the Runtime hold, which may still be ``open``.

The Runtime assigns ``seq`` when it accepts a Message, in the same
commit as the Message itself.

Run from the repo root::

    poetry run python examples/communication/threads.py
"""

from __future__ import annotations

import asyncio
import uuid

from agentconnect.agent import BaseAgent, Context
from agentconnect.core.base import JsonValue
from agentconnect.core.message import MailboxMessage
from agentconnect.team import Team


class Writer(BaseAgent):
    """Replies with the prior Thread contents it was given on this Delivery."""

    async def handle(self, msg: MailboxMessage, ctx: Context) -> JsonValue | None:
        if msg.kind != "request":
            return None
        prior = [item.content for item in ctx.history]
        return {"this": msg.content, "prior": prior}


class Researcher(BaseAgent):
    """Sends threaded work and prints Tickets. Does not handle inbound work."""

    async def handle(self, msg: MailboxMessage, ctx: Context) -> JsonValue | None:
        return None


async def main() -> None:
    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    researcher = Researcher(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    thread_id = str(uuid.uuid4())
    try:
        first = await researcher.ask(
            "writer",
            "outline the draft",
            thread_id=thread_id,
        )
        print("first state:", first.state)
        if first.state == "completed":
            print("first:", first.response.content)

        pending = await researcher.ask(
            "writer",
            "expand section 2",
            collect="ticket",
            thread_id=thread_id,
        )
        print("ticket state:", pending.state)
        ticket = await researcher.get_result(pending.id)
        while ticket.state == "open":
            await asyncio.sleep(0.05)
            ticket = await researcher.get_result(pending.id)
        print("second state:", ticket.state)
        if ticket.state == "completed":
            print("second:", ticket.response.content)

        page = await researcher.get_history(thread_id)
        print("history:", [(msg.kind, msg.seq) for msg in page.messages])
        print("has_more:", page.has_more)
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
