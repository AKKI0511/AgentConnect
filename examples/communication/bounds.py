"""Runtime size bounds and generic handler-failure text.

``send`` and ``reply`` bodies over ``max_message_bytes`` fail with
``payload_too_large``. An oversized reply leaves the Ticket ``open``.
An uncaught exception in ``handle`` fails the Ticket with a generic
message. Call ``ctx.ticket().fail(...)`` when the requester should see
a specific explanation.

Run from the repo root::

    poetry run python examples/communication/bounds.py
"""

from __future__ import annotations

import asyncio

from agentconnect.agent import BaseAgent
from agentconnect.agent.errors import SessionError
from agentconnect.team import Team


class Writer(BaseAgent):
    """Replies to ordinary work and raises on the token ``boom``."""

    async def handle(self, msg, ctx):
        if msg.kind != "request":
            return None
        if msg.content == "boom":
            raise RuntimeError("stack traces stay on this process")
        return {"echo": msg.content}


class Researcher(BaseAgent):
    """Sends work and does not handle inbound Messages."""

    async def handle(self, msg, ctx):
        return None


async def main() -> None:
    team = await Team("content-squad", max_message_bytes=256).start()
    writer = Writer(name="writer")
    researcher = Researcher(name="researcher")
    await writer.join(team)
    await researcher.join(team)
    try:
        print("max_message_bytes", team.limits.max_message_bytes)
        try:
            await researcher.tell("writer", "n" * 400)
        except SessionError as exc:
            print("oversized send", exc.code)
        failed = await researcher.ask("writer", "boom")
        print("raised handler", failed.state, failed.error.message)
        ok = await researcher.ask("writer", "notes")
        print("ok", ok.state, ok.content)
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
