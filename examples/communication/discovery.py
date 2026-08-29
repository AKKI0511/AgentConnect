"""Specialists join one Team and find each other by describing the work.

Semantic ``find`` is on from the first Team. No vector database and no
API key are required.

Run from the repo root::

    poetry run python examples/communication/discovery.py
"""

from __future__ import annotations

import asyncio

from agentconnect.agent import BaseAgent
from agentconnect.team import Team


class Reviewer(BaseAgent):
    """Reads a contract and returns a short risk list."""

    profile = {
        "summary": "Reviews contracts for risk and missing terms.",
        "skills": [
            {
                "name": "contract_review",
                "description": "Read a contract and list risks and missing clauses.",
                "examples": ["Check this MSA for indemnity gaps."],
            }
        ],
        "tags": ["legal", "contracts"],
    }

    async def process_message(self, msg, ctx):
        return "Reviewed. Flag the indemnity cap and the missing termination clause."


class Writer(BaseAgent):
    """Turns notes into a short draft."""

    profile = {
        "summary": "Writes short drafts from research notes.",
        "skills": [
            {
                "name": "drafting",
                "description": "Turn notes into a two-paragraph draft.",
            }
        ],
        "tags": ["writing"],
    }

    async def process_message(self, msg, ctx):
        return f"Draft complete for {msg.get('content')!r}."


class Researcher(BaseAgent):
    """Finds a teammate, then asks that teammate to do the work."""

    profile = {
        "summary": "Finds sources and hires teammates for specialized work.",
        "skills": [
            {
                "name": "research",
                "description": "Find sources and decide who should handle a task.",
            }
        ],
        "tags": ["research"],
    }

    async def process_message(self, msg, ctx):
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
        print("find:")
        for match in found["matches"]:
            print(f"  {match['address']}: {match['summary']}")

        recipient = found["matches"][0]["address"]
        result = await researcher.ask(
            recipient,
            "Review the attached MSA for missing termination terms.",
            deadline_seconds=30,
            collect="wait",
        )
        print(f"asked: {recipient}")
        print(f"reply: {result['ticket']['response']['content']}")
    finally:
        await researcher.leave()
        await writer.leave()
        await reviewer.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
