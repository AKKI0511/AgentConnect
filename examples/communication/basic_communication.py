"""Two BaseAgents join a Team, exchange a request, and leave.

Subclass ``BaseAgent``, implement ``process_message``, and call ``join``.
The same class joins an embedded Team or a Team served over HTTP.

Run from the repo root::

    poetry run python examples/communication/basic_communication.py
"""

from __future__ import annotations

import asyncio

from agentconnect.agent import BaseAgent
from agentconnect.team import Team


class Writer(BaseAgent):
    """Turns a request into a short draft and returns it."""

    async def process_message(self, msg, ctx):
        if msg.get("kind") != "request":
            return None
        task = msg.get("content")
        return f"Draft complete for {task!r}."


class Researcher(BaseAgent):
    """Asks a teammate to draft, then prints the Ticket."""

    async def process_message(self, msg, ctx):
        return None


async def main() -> None:
    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    researcher = Researcher(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        print(f"writer address:     {writer.address}")
        print(f"researcher address: {researcher.address}")

        found = await researcher.find("someone who can draft a summary")
        print("find:", [match["address"] for match in found["matches"]])

        result = await researcher.ask(
            "writer",
            {"task": "Draft a two-paragraph summary of today's notes."},
            deadline_seconds=30,
            collect="wait",
        )
        ticket = result["ticket"]
        print(f"ticket state: {ticket['state']}")
        print(f"response: {ticket['response']['content']}")
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
