"""Human and AIAgent on one Team.

Join both, then type to the assistant. Requires ``agentconnect[aiagent,cli]``.

    poetry run python examples/example_usage.py
"""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from agentconnect.prebuilt import AIAgent, HumanAgent
from agentconnect.team import Team


async def main() -> None:
    load_dotenv()
    model = os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini")
    team = await Team("content-squad").start()
    human = HumanAgent(name="operator-human")
    assistant = AIAgent(
        name="assistant",
        model=model,
        instructions="You are a concise assistant on this Team.",
    )
    await human.join(team)
    await assistant.join(team)
    try:
        await human.start_interaction("assistant")
    finally:
        await human.leave()
        await assistant.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
