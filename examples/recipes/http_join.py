"""Join a Team by URL, leave, and collect work after reconnect.

``Team.serve()`` needs the ``serve`` extra. Agents join the same way
they would from another process. Loopback serving still accepts a join
without a token. The Session sends an identity proof so the Runtime
can stamp the Agent DID.

Run from ``examples/recipes``::

    uv run python http_join.py
"""

from __future__ import annotations

import asyncio
import logging

from agentconnect import BaseAgent, Context, MailboxMessage, Team

from _wait import show_ticket, until_terminal


class Echo(BaseAgent):
    """Returns whatever ``content`` arrived on a reply-expected request."""

    async def handle(
        self, msg: MailboxMessage, ctx: Context
    ) -> dict[str, object] | None:
        if msg.kind == "request":
            return {"echo": msg.content}
        return None


async def main() -> None:
    team = await Team("content-squad").start()
    url = await team.serve()
    print(f"team serving at {url}")

    writer = Echo(name="writer")
    researcher = Echo(name="researcher")
    await writer.join(url)
    await researcher.join(url)
    print(f"joined: {writer.address}, {researcher.address}")

    try:
        first = await researcher.ask("writer", "ping", deadline_seconds=10)
        first = await until_terminal(researcher, first)
        show_ticket(first, label="first ask")

        await writer.leave()
        print("writer left; membership remains, mailbox still accepts mail")

        pending = await researcher.ask(
            "writer",
            "queued",
            deadline_seconds=15,
            collect="ticket",
        )
        print(f"ask while writer is down: {pending.state}")

        await writer.join(url)
        ticket = await until_terminal(researcher, pending)
        show_ticket(ticket, label="after writer rejoined")

        extra = Echo(name="editor")
        await extra.join(url)
        later = await extra.ask(
            "researcher",
            "hello from a new member",
            deadline_seconds=10,
        )
        later = await until_terminal(extra, later)
        show_ticket(later, label="new member ask")
        await extra.leave()
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
