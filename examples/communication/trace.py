"""Print the Trace timeline after a handler failure.

Run from the repo root::

    poetry run python examples/communication/trace.py
"""

from __future__ import annotations

import asyncio

from agentconnect.agent import BaseAgent
from agentconnect.team import Team
from agentconnect.team.errors import TeamError


class Writer(BaseAgent):
    """Fails reply-expected work so the Trace shows ``replied`` with an error."""

    profile = {
        "summary": "Writes short drafts from notes.",
        "skills": [
            {
                "name": "drafting",
                "description": "Turn notes into a two-paragraph draft.",
            }
        ],
    }

    async def process_message(self, msg, ctx):
        if msg.kind == "request":
            raise TeamError("handler_failed", "the draft could not be written")
        return None


class Researcher(BaseAgent):
    """Sends one request and does not handle inbound work."""

    async def process_message(self, msg, ctx):
        return None


async def main() -> None:
    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    researcher = Researcher(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        result = await researcher.ask(
            "writer",
            "Draft a summary",
            deadline_seconds=15,
            collect="wait",
        )
        ticket = result["ticket"]
        print(f"ticket state: {ticket['state']}")
        print(f"error: {ticket['error']['code']}")
        trace_id = result["message"]["trace_id"]
        operator = await team.ensure_operator_session()
        timeline = await team.get_trace(operator, trace_id)
        print("trace:", [event["type"] for event in timeline["events"]])
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
