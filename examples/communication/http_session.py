"""Agents join by URL, talk, leave, and more agents join later.

Start the Team, then join the same way you would from another process:
``agent.join(url)``. Killing the Team and starting it again on the same
port reconnects every Agent that is still running.

Run from the repo root::

    poetry run python examples/communication/http_session.py
"""

from __future__ import annotations

import asyncio

from agentconnect.agent import BaseAgent
from agentconnect.team import Team


class Echo(BaseAgent):
    """Returns whatever ``content`` arrived on a reply-expected request."""

    async def process_message(self, msg, ctx):
        if msg.get("kind") == "request" and msg.get("deadline"):
            return {"echo": msg.get("content")}
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
        result = await researcher.ask("writer", "ping", deadline_seconds=10)
        print(
            f"first ask: {result['ticket']['state']} {result['ticket']['response']['content']}"
        )

        await writer.leave()
        print("writer left; membership remains, mailbox still accepts mail")

        pending = await researcher.ask(
            "writer", "queued", deadline_seconds=15, collect="ticket"
        )
        print(f"ask while writer is down: {pending['ticket']['state']}")

        await writer.join(url)
        for _ in range(50):
            ticket = await researcher.get_result(pending["ticket"]["id"])
            if ticket["state"] != "open":
                break
            await asyncio.sleep(0.1)
        print(
            f"after writer rejoined: {ticket['state']} {ticket.get('response', {}).get('content')}"
        )

        extra = Echo(name="editor")
        await extra.join(url)
        later = await extra.ask(
            "researcher", "hello from a new member", deadline_seconds=10
        )
        print(f"new member ask: {later['ticket']['state']}")
        await extra.leave()
    finally:
        await researcher.leave()
        await writer.leave()
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
