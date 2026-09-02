"""A model-backed Agent discovers a teammate through Team tools.

``AIAgent`` is a ``BaseAgent`` with a LiteLLM tool loop. Team tools attach
from the Session. This script uses a recorded model so it runs without an
API key. Pass ``AGENTCONNECT_MODEL`` and a provider key to use a live model.

Run from the repo root::

    poetry run python examples/communication/aiagent.py
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from agentconnect.agent import BaseAgent
from agentconnect.prebuilt import AIAgent
from agentconnect.team import Team


class Writer(BaseAgent):
    """Turns a request into a short draft."""

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

    async def process_message(self, msg, ctx) -> Any:
        if msg.kind != "request":
            return None
        return f"Draft complete for {msg.content!r}."


def _recorded_complete():
    turns = [
        {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {
                                    "name": "find",
                                    "arguments": (
                                        '{"query": "someone who can draft a summary"}'
                                    ),
                                },
                            }
                        ],
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c2",
                                "type": "function",
                                "function": {
                                    "name": "ask",
                                    "arguments": (
                                        '{"recipient": "writer@content-squad",'
                                        ' "content": "Draft a two-paragraph summary.",'
                                        ' "deadline_seconds": 30, "wait_seconds": 10}'
                                    ),
                                },
                            }
                        ],
                    }
                }
            ]
        },
        {"choices": [{"message": {"content": "The writer finished the draft."}}]},
    ]

    async def complete(**kwargs: Any) -> dict[str, Any]:
        if not turns:
            return {"choices": [{"message": {"content": "done"}}]}
        return turns.pop(0)

    return complete


async def main() -> None:
    model = os.getenv("AGENTCONNECT_MODEL")
    if model:
        coordinator = AIAgent(
            name="researcher",
            model=model,
            instructions=(
                "Find a teammate who can draft, then ask them to do the work. "
                "Return their reply."
            ),
        )
    else:
        coordinator = AIAgent(
            name="researcher",
            model="recorded",
            complete=_recorded_complete(),
            instructions="Use find then ask.",
        )
    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    await writer.join(team)
    await coordinator.join(team)
    try:
        result = await writer.ask(
            "researcher",
            "Draft a two-paragraph summary of today's notes.",
        )
        ticket = result["ticket"]
        print(f"ticket: {ticket['state']}")
        print(f"reply: {ticket['response']['content']}")
    finally:
        await coordinator.leave()
        await writer.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
