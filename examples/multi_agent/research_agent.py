"""Researcher ``AIAgent`` with an optional Tavily search tool."""

from __future__ import annotations

import os
from typing import Any

from agentconnect.prebuilt import AIAgent, Tool


async def web_search(query: str) -> str:
    """Search the public web. Requires ``TAVILY_API_KEY`` and the research extra."""
    from tavily import TavilyClient

    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    result = client.search(query=query, max_results=3)
    hits = result.get("results") or []
    lines = [f"{item.get('title')}: {item.get('content')}" for item in hits]
    return "\n".join(lines) or "no hits"


def create_research_agent(model: str, **kwargs: Any) -> AIAgent:
    """Return a researcher. Pass ``complete=`` in tests to skip a live model."""
    tools: list[Tool] = []
    if os.getenv("TAVILY_API_KEY"):
        tools.append(
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
        )
    return AIAgent(
        name="researcher",
        model=model,
        instructions="Search when you need facts. Cite titles. Keep replies short.",
        tools=tools,
        **kwargs,
    )
