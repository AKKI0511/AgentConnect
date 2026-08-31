"""Researcher and optional Telegram bot on one Team, driven from stdin.

Requires ``agentconnect[aiagent,cli]``. Telegram needs ``TELEGRAM_BOT_TOKEN``.
Web search needs ``TAVILY_API_KEY``. Payments need ``agentconnect[payments]``
and CDP keys.

    poetry run python examples/autonomous_workflow/run_workflow_demo.py
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from dotenv import load_dotenv

from agentconnect.prebuilt import AIAgent, HumanAgent, Tool
from agentconnect.team import Team


async def web_search(query: str) -> str:
    """Search the public web. Requires ``TAVILY_API_KEY``."""
    from tavily import TavilyClient

    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    result = client.search(query=query, max_results=3)
    hits = result.get("results") or []
    lines = [f"{item.get('title')}: {item.get('content')}" for item in hits]
    return "\n".join(lines) or "no hits"


def _researcher(model: str, enable_payments: bool) -> AIAgent:
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
        enable_payments=enable_payments,
        instructions=(
            "You research companies and topics. Search when you need facts. "
            "If a Telegram teammate exists, ask them to broadcast a short summary."
        ),
        tools=tools,
        profile={
            "summary": "Researches a topic and returns a short report.",
            "skills": [
                {
                    "name": "general_research",
                    "description": "Research a company, project, or URL and return a structured report.",
                }
            ],
            "tags": ["research"],
        },
    )


async def main() -> None:
    load_dotenv()
    model = os.getenv("AGENTCONNECT_MODEL", "gpt-4o-mini")
    enable_payments = os.getenv("CDP_API_KEY_NAME") is not None
    team = await Team("workflow").start()
    researcher = _researcher(model, enable_payments)
    human = HumanAgent(name="operator-human")
    telegram = None
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if telegram_token:
        from agentconnect.prebuilt import TelegramAIAgent

        telegram = TelegramAIAgent(
            name="telegram-bot",
            model=model,
            telegram_token=telegram_token,
            enable_payments=enable_payments,
            instructions=(
                "Broadcast short summaries to registered Telegram groups when asked."
            ),
            profile={
                "summary": "Broadcasts a short message to Telegram groups.",
                "skills": [
                    {
                        "name": "telegram_broadcast",
                        "description": "Send a summary to registered Telegram groups.",
                    }
                ],
                "tags": ["telegram"],
            },
        )
    members = [researcher, human]
    if telegram is not None:
        members.append(telegram)
    for member in members:
        await member.join(team)
    telegram_task: asyncio.Task[Any] | None = None
    if telegram is not None:
        telegram_task = asyncio.create_task(telegram.run())
    try:
        print("Talk to the researcher. Type exit to stop.")
        await human.start_interaction("researcher")
    finally:
        if telegram_task is not None:
            telegram_task.cancel()
            try:
                await telegram_task
            except (asyncio.CancelledError, Exception):
                pass
        for member in reversed(members):
            await member.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
