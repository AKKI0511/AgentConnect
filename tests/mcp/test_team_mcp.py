"""Team MCP tools: find, ask, tell, get_result, get_history, roster, extras."""

from __future__ import annotations

import json
from typing import Any

import pytest
from mcp import Client

from agentconnect.agent import BaseAgent
from agentconnect.mcp.actions import resolve_session
from agentconnect.mcp.ids import message_id_for_tool
from agentconnect.mcp.server import create_team_mcp
from agentconnect.team import Team, TeamError
from tests.team.conftest import make_did, profile


class Writer(BaseAgent):
    """Echoes reply-expected work so tests can collect a Ticket."""

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

    async def process_message(self, message: dict[str, Any], ctx) -> Any:
        if message.get("kind") == "request" and message.get("deadline"):
            return {"echo": message.get("content")}
        return None


async def ping() -> dict[str, str]:
    """Return a heartbeat for extra-tool tests."""
    return {"status": "ok"}


def _body(result) -> dict[str, Any]:
    if result.structured_content:
        return dict(result.structured_content)
    if result.content:
        return json.loads(result.content[0].text)
    raise AssertionError("empty tool result")


def _error(result) -> dict[str, Any]:
    assert result.is_error
    structured = result.structured_content
    if isinstance(structured, dict) and "error" in structured:
        return structured["error"]
    texts = [getattr(item, "text", "") or "" for item in result.content or []]
    blob = "".join(texts)
    if blob:
        try:
            payload = json.loads(blob)
        except json.JSONDecodeError:
            assert "not_found" in blob
            return {"code": "not_found", "message": blob}
        if isinstance(payload, dict) and "error" in payload:
            return payload["error"]
        if isinstance(payload, dict) and "code" in payload:
            return payload
    dumped = result.model_dump(mode="json") if hasattr(result, "model_dump") else {}
    blob = json.dumps(dumped)
    assert "not_found" in blob
    return {"code": "not_found", "message": blob}


@pytest.mark.asyncio
async def test_reserved_tool_name_rejected():
    async def find() -> dict[str, str]:
        return {}

    with pytest.raises(ValueError, match="reserved"):
        Team("content-squad", tools=[find])


@pytest.mark.asyncio
async def test_operator_name_is_reserved():
    team = await Team("content-squad").start()
    try:
        with pytest.raises(TeamError) as exc:
            await team.join(
                name="operator",
                agent_did=make_did("human"),
                profile=profile(),
            )
        assert exc.value.code == "name_conflict"
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_message_id_includes_rpc_id_when_key_omitted():
    first = message_id_for_tool(
        "ask",
        "operator@content-squad",
        recipient="writer",
        content="same",
        request_id="1",
    )
    retry = message_id_for_tool(
        "ask",
        "operator@content-squad",
        recipient="writer",
        content="same",
        request_id="1",
    )
    other = message_id_for_tool(
        "ask",
        "operator@content-squad",
        recipient="writer",
        content="same",
        request_id="2",
    )
    keyed = message_id_for_tool(
        "ask",
        "operator@content-squad",
        idempotency_key="draft-1",
    )
    keyed_again = message_id_for_tool(
        "ask",
        "operator@content-squad",
        idempotency_key="draft-1",
        recipient="other",
    )
    assert first == retry
    assert first != other
    assert keyed == keyed_again


@pytest.mark.asyncio
async def test_in_memory_tools_find_ask_tell_result_history_and_roster():
    team = await Team("content-squad", tools=[ping]).start()
    writer = Writer(name="writer")
    await writer.join(team)
    mcp = create_team_mcp(team)
    try:
        async with Client(mcp) as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            assert names >= {"find", "ask", "tell", "get_result", "get_history", "ping"}

            found = _body(
                await client.call_tool(
                    "find", {"query": "someone who can draft a summary"}
                )
            )
            addresses = [match["address"] for match in found["matches"]]
            assert any(item.startswith("writer@") for item in addresses)
            assert all(not item.startswith("operator@") for item in addresses)
            recipient = next(item for item in addresses if item.startswith("writer@"))

            ticket = _body(
                await client.call_tool(
                    "ask",
                    {
                        "recipient": recipient,
                        "content": "draft this",
                        "deadline_seconds": 30,
                        "wait_seconds": 8,
                    },
                )
            )
            assert ticket["state"] == "completed"
            assert ticket["response"]["content"] == {"echo": "draft this"}
            ticket_id = ticket["id"]
            thread_id = ticket["thread_id"]

            again = _body(
                await client.call_tool("get_result", {"ticket_id": ticket_id})
            )
            assert again["id"] == ticket_id
            assert again["state"] == "completed"

            history = _body(
                await client.call_tool("get_history", {"thread_id": thread_id})
            )
            assert history["messages"]

            told = _body(
                await client.call_tool(
                    "tell", {"recipient": recipient, "content": {"notice": "changed"}}
                )
            )
            assert told["status"] == "accepted"

            roster = await client.read_resource("agentconnect://team/roster")
            body = json.loads(roster.contents[0].text)
            member_names = [
                item["address"].split("@", 1)[0] for item in body["members"]
            ]
            assert body["team_name"] == "content-squad"
            assert "writer" in member_names
            assert "operator" in member_names

            pinged = _body(await client.call_tool("ping", {}))
            assert pinged.get("status") == "ok" or "ok" in json.dumps(pinged)
    finally:
        await writer.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_identical_asks_open_two_tickets_unless_keyed():
    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    await writer.join(team)
    mcp = create_team_mcp(team)
    args = {
        "recipient": "writer",
        "content": "same",
        "deadline_seconds": 30,
        "wait_seconds": 8,
    }
    try:
        async with Client(mcp) as client:
            first = _body(await client.call_tool("ask", args))
            second = _body(await client.call_tool("ask", args))
            assert first["id"] != second["id"]

            keyed = dict(args)
            keyed["idempotency_key"] = "draft-1"
            one = _body(await client.call_tool("ask", keyed))
            two = _body(await client.call_tool("ask", keyed))
            assert one["id"] == two["id"]
    finally:
        await writer.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_runtime_error_is_tool_error():
    team = await Team("content-squad").start()
    mcp = create_team_mcp(team)
    try:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "ask",
                {
                    "recipient": "missing",
                    "content": "draft this",
                    "deadline_seconds": 30,
                },
            )
            error = _error(result)
            assert error["code"] == "not_found"
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_missing_auth_is_operator_and_bad_bearer_is_not():
    team = await Team("content-squad").start()
    try:
        token = await resolve_session(team, None)
        address = await team.caller_address(token)
        assert address.startswith("operator@")

        with pytest.raises(TeamError) as exc:
            await resolve_session(team, {"Authorization": "Bearer not-a-session"})
        assert exc.value.code == "unauthorized"

        with pytest.raises(TeamError) as exc:
            await resolve_session(team, {"Authorization": "not-bearer"})
        assert exc.value.code == "unauthorized"
    finally:
        await team.stop()
