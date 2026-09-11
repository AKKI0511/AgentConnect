"""Hosted Writer started by ``agentconnect up``."""

from __future__ import annotations

from agentconnect import AgentProfile, BaseAgent, Context, MailboxMessage, Skill


class Writer(BaseAgent):
    """Turns a request into a short draft."""

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
