"""Researcher and writer on one Team.

The researcher is an ``AIAgent``. The writer is a ``BaseAgent``. Requires
``agentconnect[aiagent]``.

    poetry run python examples/example_multi_agent.py
"""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from agentconnect.agent import BaseAgent
from agentconnect.prebuilt import AIAgent
from agentconnect.team import Team


class Writer(BaseAgent):
    """Returns a short draft."""

    profile = {
        "summary": "Writes short drafts from notes.",
        "skills": [
            {
                "name": "drafting",
                "description": "Turn notes into a two-paragraph draft.",
            }
        ],
        "tags": ["writing"],
    }

    async def process_message(self, msg, ctx):
        if msg.kind != "request":
            return None
        return f"Draft complete for {msg.content!r}."


async def main() -> None:
    load_dotenv()
    model = os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini")
    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    researcher = AIAgent(
        name="researcher",
        model=model,
        instructions=(
            "Find a teammate who can draft, ask them to write, and return the draft."
        ),
    )
    await writer.join(team)
    await researcher.join(team)
    try:
        result = await researcher.ask(
            "writer",
            "Draft two paragraphs on Q3 ecommerce conversion.",
        )
        print(result["ticket"]["response"]["content"])
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
