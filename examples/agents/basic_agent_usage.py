"""Create an AIAgent and call chat() without a Team.

poetry run python examples/agents/basic_agent_usage.py
"""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from agentconnect.prebuilt import AIAgent


async def main() -> None:
    load_dotenv()
    model = os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini")
    agent = AIAgent(
        name="assistant",
        model=model,
        instructions="Answer briefly.",
    )
    first = await agent.chat("What is a Team in AgentConnect?")
    print(first)
    follow = await agent.chat("What does join do?")
    print(follow)


if __name__ == "__main__":
    asyncio.run(main())
