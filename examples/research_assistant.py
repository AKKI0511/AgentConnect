"""Research assistant with a Tavily search tool.

Requires ``agentconnect[aiagent]`` and the research extra (tavily-python).
Set ``TAVILY_API_KEY`` and a model key.

    poetry run python examples/research_assistant.py
"""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from agentconnect.prebuilt import AIAgent, HumanAgent, Tool
from agentconnect.team import Team


async def web_search(query: str) -> str:
    """Search the web with Tavily and return a short string."""
    from tavily import TavilyClient

    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    result = client.search(query=query, max_results=3)
    hits = result.get("results") or []
    lines = [f"{item.get('title')}: {item.get('content')}" for item in hits]
    return "\n".join(lines) or "no hits"


async def main() -> None:
    load_dotenv()
    model = os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini")
    team = await Team("research").start()
    researcher = AIAgent(
        name="researcher",
        model=model,
        instructions="Search the web when you need facts. Cite titles.",
        tools=[
            Tool(
                name="web_search",
                description="Search the public web.",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                handler=web_search,
            )
        ],
    )
    human = HumanAgent(name="operator-human")
    await researcher.join(team)
    await human.join(team)
    try:
        await human.start_interaction("researcher")
    finally:
        await human.leave()
        await researcher.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
