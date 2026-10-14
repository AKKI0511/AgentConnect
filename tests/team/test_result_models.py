"""Team Session methods return public schema models, not plain dicts."""

from __future__ import annotations

import uuid

import pytest
from tests.team.conftest import deadline, join_member

from agentconnect.core.directory import DirectoryEntry, FindResult
from agentconnect.core.operations import (
    HeartbeatResult,
    JoinResult,
    LeaseResult,
    TicketedSendResult,
)
from agentconnect.core.ticket import OpenTicket
from agentconnect.team import Team


def _id() -> str:
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_team_session_methods_return_schema_models(team: Team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    assert isinstance(writer, JoinResult)

    beat = await team.heartbeat(researcher.session_token)
    assert isinstance(beat, HeartbeatResult)

    sent = await team.send(
        researcher.session_token,
        {
            "id": _id(),
            "recipient": "writer",
            "kind": "request",
            "content": "ping",
            "collect": "ticket",
            "deadline": deadline(20),
        },
    )
    assert isinstance(sent, TicketedSendResult)
    ticket = await team.get_result(researcher.session_token, sent.ticket.id)
    assert isinstance(ticket, OpenTicket)

    leased = await team.lease(writer.session_token)
    assert isinstance(leased, LeaseResult)

    found = await team.find(researcher.session_token, "draft notes")
    assert isinstance(found, FindResult)

    entry = await team.get_profile(researcher.session_token, "writer")
    assert isinstance(entry, DirectoryEntry)
