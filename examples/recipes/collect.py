"""Delegate work and collect the Ticket later.

``collect="ticket"`` returns immediately. ``collect="wait"`` returns
when the Ticket is terminal or when the Runtime wait hold ends. That
wait is not the work deadline; an ``open`` Ticket is still accepted
work. ``get_result`` reads the later state.

The writer asks the researcher from ``handle``. If that child is not
finished, the writer defers and replies after the child Ticket lands.
The researcher defers on purpose so collection is visible.

Run from ``examples/recipes``::

    uv run python collect.py
"""

from __future__ import annotations

import asyncio

from agentconnect import AgentProfile, BaseAgent, Context, MailboxMessage, Skill, Team
from agentconnect.agent.context import DeferredReply

from _wait import show_ticket, until_terminal


class Researcher(BaseAgent):
    """Defers, then replies. Completes the Delivery after ``handle`` returns."""

    profile = AgentProfile(
        summary="Gathers short notes after a brief delay.",
        skills=[
            Skill(
                name="research",
                description="Return short notes for a drafting teammate.",
            )
        ],
        tags=["research"],
    )

    async def handle(self, msg: MailboxMessage, ctx: Context) -> None:
        if msg.kind != "request":
            return None
        pending = ctx.defer()
        asyncio.create_task(self._finish(pending, str(msg.content)))
        return None

    async def _finish(self, pending: DeferredReply, task: str) -> None:
        await asyncio.sleep(0.2)
        await pending.reply(f"Notes for {task}.")


class Writer(BaseAgent):
    """Asks the researcher, then drafts from the child Ticket."""

    profile = AgentProfile(
        summary="Writes short drafts from research notes.",
        skills=[
            Skill(
                name="drafting",
                description="Turn notes into a short draft.",
            )
        ],
        tags=["writing"],
    )

    async def handle(self, msg: MailboxMessage, ctx: Context) -> str | None:
        if msg.kind != "request":
            return None
        child = await ctx.ask("researcher", msg.content, collect="ticket")
        if child.state == "completed":
            return f"Draft from {child.response.content}"
        pending = ctx.defer()
        asyncio.create_task(self._finish(pending, child.id))
        return None

    async def _finish(self, pending: DeferredReply, child_id: str) -> None:
        child = await self.get_result(child_id)
        child = await until_terminal(self, child)
        if child.state == "completed":
            await pending.reply(f"Draft from {child.response.content}")
            return
        if child.state == "declined":
            await pending.decline()
            return
        if child.state == "failed":
            await pending.fail(f"researcher failed: {child.error.message}")
            return
        if child.state == "expired":
            await pending.fail("researcher expired before notes arrived")
            return
        await pending.fail("researcher did not finish before the work deadline")


class Editor(BaseAgent):
    """Sends work and collects Tickets."""

    async def handle(self, msg: MailboxMessage, ctx: Context) -> None:
        return None


async def main() -> None:
    team = await Team("content-squad", wait_hold_seconds=0.05).start()
    researcher = Researcher(name="researcher")
    writer = Writer(name="writer")
    editor = Editor(name="editor")
    await researcher.join(team)
    await writer.join(team)
    await editor.join(team)
    try:
        pending = await editor.ask(
            "writer",
            "outline the launch note",
            collect="ticket",
            deadline_seconds=30,
        )
        print(f"immediate collect: {pending.state}")
        ticket = await until_terminal(editor, pending)
        show_ticket(ticket, label="delegated")

        waited = await editor.ask(
            "writer",
            "expand the opening",
            deadline_seconds=30,
        )
        print(f"wait hold returned: {waited.state}")
        waited = await until_terminal(editor, waited)
        show_ticket(waited, label="after wait")
    finally:
        await editor.leave()
        await writer.leave()
        await researcher.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
