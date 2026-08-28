"""Two Agents share a Thread. History rides with each Delivery.

``ask(..., thread_id=...)`` groups turns. The handler reads recent turns
from ``ctx.history`` and pages the rest with ``get_history``.
``collect="ticket"`` returns immediately; ``collect="wait"`` returns a
terminal Ticket, even if the Runtime's wait hold elapsed first.

Run from the repo root::

    poetry run python examples/communication/threads.py
"""

from __future__ import annotations

import asyncio
import uuid

from agentconnect.agent import BaseAgent
from agentconnect.team import Team


class Writer(BaseAgent):
    """Replies with the prior Thread contents it was given on this Delivery."""

    async def process_message(self, msg, ctx):
        if msg.get("kind") != "request":
            return None
        prior = [item.get("content") for item in ctx.history]
        return {"this": msg.get("content"), "prior": prior}


class Researcher(BaseAgent):
    """Sends threaded work and prints Tickets. Does not handle inbound work."""

    async def process_message(self, msg, ctx):
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
        print("first:", first["ticket"]["response"]["content"])

        pending = await researcher.ask(
            "writer",
            "expand section 2",
            collect="ticket",
            thread_id=thread_id,
        )
        print("ticket state:", pending["ticket"]["state"])
        ticket = await researcher.get_result(pending["ticket"]["id"])
        while ticket["state"] == "open":
            await asyncio.sleep(0.05)
            ticket = await researcher.get_result(pending["ticket"]["id"])
        print("second:", ticket["response"]["content"])

        page = await researcher.get_history(thread_id)
        print("history kinds:", [msg["kind"] for msg in page["messages"]])
        print("has_more:", page["has_more"])
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
