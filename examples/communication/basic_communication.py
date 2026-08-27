"""Two members of one Team exchanging a reply-expected request.

This example talks to the Team Runtime directly: join, send, lease, reply,
and get_result. It does not start model-backed agents. Those join through
a session in a later milestone.

Run from the repo root::

    poetry run python examples/communication/basic_communication.py
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from agentconnect.team import Team, TeamError


WRITER_DID = "did:key:z6MkmEtU9Z7p7G6vbULDgMk8DXCVqW8rNyLMtd2RrAHjLD3m"
RESEARCHER_DID = "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK"

WRITER_PROFILE = {
    "summary": "Writes short drafts from research notes.",
    "skills": [
        {
            "name": "drafting",
            "description": "Turn notes into a two-paragraph draft.",
            "examples": ["Draft a summary of these findings."],
        }
    ],
    "tags": ["writing"],
}

RESEARCHER_PROFILE = {
    "summary": "Researches technical topics and returns cited findings.",
    "skills": [
        {
            "name": "technical_research",
            "description": "Find sources and summarize them with citations.",
        }
    ],
    "tags": ["research"],
}


def _deadline(seconds: int = 30) -> str:
    instant = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


async def main() -> None:
    team = await Team("content-squad").start()
    try:
        writer = await team.join(
            name="writer",
            agent_did=WRITER_DID,
            profile=WRITER_PROFILE,
        )
        researcher = await team.join(
            name="researcher",
            agent_did=RESEARCHER_DID,
            profile=RESEARCHER_PROFILE,
        )
        print(f"writer address:     {writer['address']}")
        print(f"researcher address: {researcher['address']}")
        print(f"persistence:        {writer['persistence']}")

        found = await team.find(
            researcher["session_token"],
            "someone who can draft a summary",
            limit=5,
        )
        print("find:", [match["address"] for match in found["matches"]])

        request_id = str(uuid.uuid4())
        sent = await team.send(
            researcher["session_token"],
            {
                "id": request_id,
                "recipient": "writer",
                "kind": "request",
                "content": {"task": "Draft a two-paragraph summary of today's notes."},
                "collect": "ticket",
                "deadline": _deadline(30),
            },
        )
        print(f"ticket state after send: {sent['ticket']['state']}")

        leased = await team.lease(writer["session_token"])
        delivery = leased["deliveries"][0]
        print(f"writer leased attempt {delivery['attempt']} id={delivery['message']['id']}")

        replied = await team.reply(
            writer["session_token"],
            {
                "id": str(uuid.uuid4()),
                "lease_id": delivery["lease_id"],
                "outcome": "completed",
                "content": "Draft complete.",
            },
        )
        print(f"ticket state after reply: {replied['ticket']['state']}")
        print(f"response: {replied['ticket']['response']['content']}")

        ticket = await team.get_result(researcher["session_token"], request_id)
        print(f"get_result: {ticket['state']}")

        try:
            await team.get_result(writer["session_token"], request_id)
        except TeamError as exc:
            print(f"writer cannot read researcher's ticket: {exc.code}")
    finally:
        await team.stop()


if __name__ == "__main__":
    asyncio.run(main())
