"""A coordinator discovers a teammate through Session-bound tools.

The coordinator never hardcodes a recipient Address. ``team_tools()`` is
``find``, ``ask``, ``tell``, ``get_result``, and ``get_history`` bound to this
Agent's Session. Use it from LangGraph, ADK, or any other tool loop.

Run from the repo root::

    poetry run python examples/communication/tools.py
"""

from __future__ import annotations

import asyncio

from agentconnect.agent import BaseAgent
from agentconnect.team import Team


class Writer(BaseAgent):
    """Turns a request into a short draft and returns it."""

    profile = {
        "summary": "Writes short drafts from notes.",
        "skills": [
            {
                "name": "drafting",
                "description": "Turn research notes into a two-paragraph draft.",
            }
        ],
        "tags": ["writing"],
    }

    async def process_message(self, msg, ctx):
        if msg.get("kind") != "request":
            return None
        return f"Draft complete for {msg.get('content')!r}."


class Coordinator(BaseAgent):
    """Finds a teammate, then asks that teammate to do the work."""

    profile = {
        "summary": "Finds teammates and hires them for specialized work.",
        "skills": [
            {
                "name": "research",
                "description": "Find sources and decide who should handle a task.",
            }
        ],
        "tags": ["research"],
    }

    def __init__(self, name: str):
        super().__init__(name=name)
        self.tools = self.team_tools()

    async def process_message(self, msg, ctx):
        found = await self.tools.find(query=str(msg["content"]))
        peer = found["matches"][0]["address"]
        return await self.tools.ask(
            recipient=peer,
            content=msg["content"],
            deadline_seconds=30,
            wait_seconds=10,
        )


async def main() -> None:
    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    coordinator = Coordinator(name="researcher")
    await writer.join(team)
    await coordinator.join(team)
    try:
        found = await coordinator.tools.find(query="someone who can draft a summary")
        print("find:")
        for match in found["matches"]:
            print(f"  {match['address']}: {match['summary']}")

        recipient = next(
            match["address"]
            for match in found["matches"]
            if match["address"].startswith("writer@")
        )
        ticket = await coordinator.tools.ask(
            recipient=recipient,
            content="Draft a two-paragraph summary of today's notes.",
            deadline_seconds=30,
            wait_seconds=10,
        )
        print(f"asked: {recipient}")
        print(f"ticket: {ticket['state']}")
        print(f"reply: {ticket['response']['content']}")
    finally:
        await coordinator.leave()
        await writer.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
