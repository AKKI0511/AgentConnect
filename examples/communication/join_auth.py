"""Join a served Team with a join token and a DID proof.

Embedded ``join(team)`` needs no credentials. Joining by URL against a
Team started with ``require_join_auth=True`` needs both a token the
operator issued and an identity proof the Session builds from the Agent
key.

Run from the repo root::

    poetry run python examples/communication/join_auth.py
"""

from __future__ import annotations

import asyncio

from agentconnect.agent import BaseAgent
from agentconnect.team import Team


class Echo(BaseAgent):
    """Returns whatever ``content`` arrived on a reply-expected request."""

    async def handle(self, msg, ctx):
        if msg.kind == "request" and getattr(msg, "deadline", None):
            return {"echo": msg.content}
        return None


async def main() -> None:
    team = await Team("content-squad", require_join_auth=True).start()
    url = await team.serve()
    print(f"team serving at {url}")
    print(f"team did: {team.team_did}")

    writer = Echo(name="writer")
    researcher = Echo(name="researcher")
    writer_tok = await team.issue_join_token(name="writer", agent_did=writer.agent_did)
    researcher_tok = await team.issue_join_token(
        name="researcher", agent_did=researcher.agent_did
    )

    stolen = Echo(name="writer")
    try:
        await stolen.join(url, join_token=writer_tok["token"])
        print("stolen token unexpectedly succeeded")
        return
    except Exception as exc:
        print(f"stolen token rejected: {exc}")

    await writer.join(url, join_token=writer_tok["token"])
    await researcher.join(url, join_token=researcher_tok["token"])
    print(f"joined: {writer.address}, {researcher.address}")

    result = await researcher.ask("writer", "ping", deadline_seconds=10)
    print(f"ask: {result.state} {result.content}")

    attestation = await team.membership_attestation("writer")
    print(f"writer attestation issued: {bool(attestation)}")

    await team.revoke_join_token(writer_tok["token"])
    print("writer join token revoked; session dropped")

    await researcher.leave()
    await writer.leave()
    await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
