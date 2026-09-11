"""Find a teammate by describing the work, then use that Address.

Light cards carry summary and Profile tags. ``get_entry`` reads the
full Profile, including ``description`` and Skill tags.

Run from ``examples/recipes``::

    uv run python discover.py
"""

from __future__ import annotations

import asyncio

from agentconnect import AgentProfile, BaseAgent, Context, MailboxMessage, Skill, Team

from _wait import show_ticket, until_terminal


class Reviewer(BaseAgent):
    """Reads a contract and returns a short risk list."""

    profile = AgentProfile(
        summary="Reviews contracts for risk and missing terms.",
        description="Use for MSAs and similar commercial contracts.",
        skills=[
            Skill(
                name="contract_review",
                description="Read a contract and list risks and missing clauses.",
                examples=["Check this MSA for indemnity gaps."],
                tags=["msa"],
            )
        ],
        tags=["legal", "contracts"],
    )

    async def handle(self, msg: MailboxMessage, ctx: Context) -> str | None:
        if msg.kind != "request":
            return None
        return "Flag the indemnity cap and the missing termination clause."


class Writer(BaseAgent):
    """Turns notes into a short draft."""

    profile = AgentProfile(
        summary="Writes short drafts from research notes.",
        skills=[
            Skill(
                name="drafting",
                description="Turn notes into a two-paragraph draft.",
            )
        ],
        tags=["writing"],
    )

    async def handle(self, msg: MailboxMessage, ctx: Context) -> str | None:
        if msg.kind != "request":
            return None
        return f"Draft complete for {msg.content!r}."


class Researcher(BaseAgent):
    """Finds a teammate, then asks that Address."""

    profile = AgentProfile(
        summary="Finds sources and hires teammates for specialized work.",
        skills=[
            Skill(
                name="research",
                description="Find sources and decide who should handle a task.",
            )
        ],
        tags=["research"],
    )

    async def handle(self, msg: MailboxMessage, ctx: Context) -> None:
        return None


async def main() -> None:
    team = await Team("content-squad").start()
    reviewer = Reviewer(name="reviewer")
    writer = Writer(name="writer")
    researcher = Researcher(name="researcher")
    await reviewer.join(team)
    await writer.join(team)
    await researcher.join(team)
    try:
        found = await researcher.find("someone who can verify a contract")
        print(f"ranking: {found.ranking}")
        print("find:")
        for match in found.matches:
            print(f"  {match.address}: {match.summary} tags={match.tags}")
        recipient = found.matches[0].address
        entry = await researcher.get_entry(recipient)
        print(f"full profile: {entry.profile.description}")
        ticket = await researcher.ask(
            recipient,
            "Review the attached MSA for missing termination terms.",
            deadline_seconds=30,
        )
        ticket = await until_terminal(researcher, ticket)
        print(f"asked: {recipient}")
        show_ticket(ticket)
    finally:
        await researcher.leave()
        await writer.leave()
        await reviewer.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
