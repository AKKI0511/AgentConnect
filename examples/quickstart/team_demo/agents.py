"""Specialists on the demo Team.

Customize four things on each class:

- ``profile`` for discovery
- ``instructions`` for the harness
- ``harness`` passed into ``__init__``
- ``handle`` for what an incoming Message does
"""

from __future__ import annotations

from agentconnect import AgentProfile, BaseAgent, Context, MailboxMessage, Skill
from agentconnect.core.ticket import Ticket

from team_demo.harness import Harness
from team_demo.tickets import until_terminal


class Editor(BaseAgent):
    """Requester. Sends work from ``main``; inbound mail is unused."""

    profile = AgentProfile(
        summary="Sends writing jobs to the team.",
        skills=[
            Skill(
                name="assign_writing",
                description="Hand a writing job to a specialist.",
            )
        ],
        tags=["editing"],
    )

    async def handle(self, msg: MailboxMessage, ctx: Context) -> None:
        return None


class Researcher(BaseAgent):
    """Helper the writer asks for notes."""

    profile = AgentProfile(
        summary="Gathers short factual notes a writer can draft from.",
        description="Use when a teammate needs a few facts before drafting.",
        skills=[
            Skill(
                name="research",
                description="Return short notes for a drafting teammate.",
                examples=["Facts for a product launch note."],
            )
        ],
        tags=["research"],
    )

    def __init__(self, name: str, harness: Harness) -> None:
        super().__init__(name=name)
        self.harness = harness
        self.instructions = (
            "Return short factual notes the writer can use. "
            "Do not draft the final piece."
        )

    async def handle(self, msg: MailboxMessage, ctx: Context) -> str | None:
        if msg.kind != "request":
            return None
        return await self.harness.complete(
            instructions=self.instructions,
            task=str(msg.content),
            notes="",
            history=ctx.history,
        )


class Writer(BaseAgent):
    """Specialist. Asks the researcher, then runs the harness."""

    profile = AgentProfile(
        summary="Writes short drafts from research notes.",
        description="Use for launch notes and similar short copy.",
        skills=[
            Skill(
                name="drafting",
                description="Turn research notes into a short draft.",
                examples=["Draft a launch note from these facts."],
            )
        ],
        tags=["writing"],
    )

    def __init__(self, name: str, harness: Harness) -> None:
        super().__init__(name=name)
        self.harness = harness
        self.instructions = (
            "Write a short draft from the research notes. "
            "Stay faithful to those notes."
        )

    async def handle(self, msg: MailboxMessage, ctx: Context) -> str | None:
        if msg.kind != "request":
            return None
        child = await ctx.ask("researcher", msg.content)
        child = await until_terminal(self, child)
        return await self._use_notes(msg, ctx, child)

    async def _use_notes(
        self,
        msg: MailboxMessage,
        ctx: Context,
        child: Ticket,
    ) -> str | None:
        if child.state == "completed":
            print("writer asked researcher for notes")
            return await self.harness.complete(
                instructions=self.instructions,
                task=str(msg.content),
                notes=str(child.response.content),
                history=ctx.history,
            )
        if child.state == "declined":
            return None
        pending = ctx.defer()
        if child.state == "failed":
            await pending.fail(f"researcher failed: {child.error.message}")
        elif child.state == "expired":
            await pending.fail("researcher expired before notes arrived")
        else:
            await pending.fail("researcher did not finish before the work deadline")
        return None
