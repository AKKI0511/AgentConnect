"""Operator status snapshot."""

from __future__ import annotations

import pytest

from tests.team.conftest import deadline, join_member

pytestmark = pytest.mark.asyncio


async def test_status_lists_members_and_open_tickets(team):
    writer = await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    await team.send(
        researcher["session_token"],
        {
            "id": "66666666-6666-4666-8666-666666666666",
            "recipient": "writer",
            "kind": "request",
            "content": "work",
            "collect": "ticket",
            "deadline": deadline(20),
        },
    )
    operator = await team.ensure_operator_session()
    snapshot = await team.status(operator)
    assert snapshot["team_name"] == "content-squad"
    assert snapshot["open_tickets"] == 1
    by_name = {row["name"]: row for row in snapshot["members"]}
    assert by_name["writer"]["online"] is True
    assert by_name["writer"]["mailbox_depth"] == 1
    assert by_name["writer"]["open_tickets"] == 1
    assert by_name["researcher"]["mailbox_depth"] == 0
    with pytest.raises(Exception) as exc:
        await team.status(writer["session_token"])
    assert exc.value.code == "forbidden"
