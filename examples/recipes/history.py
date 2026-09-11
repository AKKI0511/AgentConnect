"""Continue a conversation and read Team-owned history.

``ask(..., thread_id=...)`` groups turns. The handler reads recent
turns from ``ctx.history``. That window is Team storage, not the
harness's private memory. Older turns are paged with ``get_history``.

Run from ``examples/recipes``::

    uv run python history.py
"""

from __future__ import annotations

import asyncio
import uuid

from agentconnect import AgentProfile, BaseAgent, Context, MailboxMessage, Skill, Team

from _wait import show_ticket, until_terminal


class Writer(BaseAgent):
    """Replies with the prior Thread contents on this Delivery."""

    profile = AgentProfile(
        summary="Writes short drafts and uses Thread history.",
        skills=[
            Skill(
                name="drafting",
                description="Continue a draft using earlier turns.",
            )
        ],
        tags=["writing"],
    )

    async def handle(
        self, msg: MailboxMessage, ctx: Context
    ) -> dict[str, object] | None:
        if msg.kind != "request":
            return None
        prior = [getattr(item, "content", item.kind) for item in ctx.history]
        return {"this": msg.content, "prior": prior}


class Researcher(BaseAgent):
    """Sends threaded work. Does not handle inbound work."""

    async def handle(self, msg: MailboxMessage, ctx: Context) -> None:
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
        first = await until_terminal(researcher, first)
        show_ticket(first, label="first")

        pending = await researcher.ask(
            "writer",
            "expand section 2",
            collect="ticket",
            thread_id=thread_id,
        )
        second = await until_terminal(researcher, pending)
        show_ticket(second, label="second")

        page = await researcher.get_history(thread_id)
        print("history:", [(msg.kind, msg.seq) for msg in page.messages])
        print("has_more:", page.has_more)
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
