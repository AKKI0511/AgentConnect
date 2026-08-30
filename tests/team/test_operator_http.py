"""Loopback HTTP operator routes for status, tokens, and traces."""

from __future__ import annotations

import asyncio

import pytest
import httpx

from tests.team.conftest import join_member

pytestmark = pytest.mark.asyncio

PREFIX = "/agentconnect/v1"


async def test_loopback_status_and_token_without_bearer(team):
    writer = await join_member(team, "writer")
    origin = await team.serve()
    async with httpx.AsyncClient() as client:
        status = await client.get(origin + PREFIX + "/status")
        assert status.status_code == 200
        body = status.json()
        assert body["team_name"] == "content-squad"
        names = {row["name"] for row in body["members"]}
        assert "writer" in names
        assert "operator" in names

        forbidden = await client.get(
            origin + PREFIX + "/status",
            headers={"Authorization": f"Bearer {writer['session_token']}"},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["code"] == "forbidden"

        issued = await client.post(
            origin + PREFIX + "/tokens",
            json={"name": "writer", "single_use": False},
        )
        assert issued.status_code == 200
        token = issued.json()["token"]
        assert token

        revoke = await client.post(
            origin + PREFIX + "/tokens/revoke", json={"token": token}
        )
        assert revoke.status_code == 204

        extra = await client.post(
            origin + PREFIX + "/tokens",
            json={"name": "writer", "publish": True},
        )
        assert extra.status_code == 400
        assert extra.json()["code"] == "invalid_request"

        unauthorized = await client.get(
            origin + PREFIX + "/status",
            headers={"Authorization": "Bearer not-a-session"},
        )
        assert unauthorized.status_code == 401


async def test_runtime_client_status_and_unreachable(team):
    await join_member(team, "writer")
    origin = await team.serve()
    from agentconnect.cli.client import RuntimeClient
    from agentconnect.team.errors import TeamError

    def snapshot() -> dict:
        with RuntimeClient(origin) as client:
            return client.status()

    body = await asyncio.to_thread(snapshot)
    assert body["team_name"] == "content-squad"

    def unreachable() -> None:
        with RuntimeClient("http://127.0.0.1:59999", timeout=0.5) as client:
            client.status()

    with pytest.raises(TeamError) as exc:
        await asyncio.to_thread(unreachable)
    assert exc.value.code == "unavailable"


async def test_http_get_trace(team):
    await join_member(team, "writer")
    researcher = await join_member(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": "77777777-7777-4777-8777-777777777777",
            "recipient": "writer",
            "kind": "event",
            "content": "hello",
        },
    )
    origin = await team.serve()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            origin + PREFIX + f"/traces/{sent['message']['trace_id']}"
        )
        assert response.status_code == 200
        assert response.json()["events"][0]["type"] == "accepted"


async def test_http_find_as_operator(team):
    await join_member(
        team,
        "writer",
        profile={
            "summary": "Writes short drafts from notes.",
            "skills": [
                {
                    "name": "drafting",
                    "description": "Turn notes into a two-paragraph draft.",
                }
            ],
        },
    )
    origin = await team.serve()
    async with httpx.AsyncClient() as client:
        found = await client.post(
            origin + PREFIX + "/directory/find",
            json={"query": "someone who can draft a summary"},
        )
        assert found.status_code == 200
        addresses = [match["address"] for match in found.json()["matches"]]
        assert any(item.startswith("writer@") for item in addresses)


async def test_watch_stream_is_not_a_trace_id(team):
    await join_member(team, "writer")
    origin = await team.serve()
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "GET", origin + PREFIX + "/traces/events", timeout=5.0
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
            async for line in response.aiter_lines():
                if line.startswith(":"):
                    break
