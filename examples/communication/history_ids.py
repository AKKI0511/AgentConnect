"""Delivery history as Message ids, paged with get_history.

``BaseAgent(..., delivery_history="ids")`` tells the Runtime to put
earlier Message ids on each Delivery instead of Message bodies.
``ctx.history`` is then empty. Read ``ctx.history_ids`` and page bodies
with ``get_history`` when you need them.

Run from the repo root::

    poetry run python examples/communication/history_ids.py
"""

from __future__ import annotations

import asyncio
import uuid

from agentconnect.agent import BaseAgent
from agentconnect.team import Team


class Writer(BaseAgent):
    """Replies with the earlier Message ids it was given on this Delivery."""

    def __init__(self) -> None:
        super().__init__(name="writer", delivery_history="ids")

    async def handle(self, msg, ctx):
        if msg.kind != "request":
            return None
        prior_ids = list(ctx.history_ids or [])
        return {"this": msg.content, "prior_ids": prior_ids}


class Researcher(BaseAgent):
    """Sends threaded work and prints Tickets. Does not handle inbound work."""

    async def handle(self, msg, ctx):
        return None


async def main() -> None:
    team = await Team("content-squad").start()
    writer = Writer()
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
        print("first:", first.content)

        second = await researcher.ask(
            "writer",
            "expand section 2",
            thread_id=thread_id,
        )
        print("second:", second.content)

        page = await researcher.get_history(thread_id)
        print("history:", [(msg.kind, msg.seq) for msg in page.messages])
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
