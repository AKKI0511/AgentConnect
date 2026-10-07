"""Advertised MCP output schemas match public result types and live results."""

from __future__ import annotations

import asyncio
from typing import Any

import jsonschema
import pytest
from mcp import Client
from mcp_types.methods import serialize_server_result

from agentconnect.agent import BaseAgent
from agentconnect.core.base import public_result_schema
from agentconnect.core.team_tools import TEAM_TOOL_SPECS
from agentconnect.core.ticket import TicketView
from agentconnect.mcp.server import create_team_mcp
from agentconnect.team import Team


class Writer(BaseAgent):
    profile = {
        "summary": "Writes short drafts from notes.",
        "skills": [{"name": "drafting", "description": "Turn notes into a draft."}],
    }

    async def handle(self, message, ctx) -> Any:
        if message.kind == "request" and getattr(message, "deadline", None):
            text = str(message.content)
            if "decline" in text:
                return None
            if "fail" in text:
                raise RuntimeError("handler boom")
            return {"echo": message.content}
        return None


class Hold(BaseAgent):
    async def handle(self, message, ctx) -> Any:
        ctx.defer()
        return None


def test_ticket_view_output_schema_serializes_on_tools_list():
    schema = public_result_schema(TicketView)
    tool = {
        "name": "ask",
        "description": "Ask a teammate",
        "inputSchema": {"type": "object", "properties": {}},
        "outputSchema": schema,
    }
    payloads = {
        "2025-11-25": {"tools": [tool]},
        "2026-07-28": {
            "tools": [tool],
            "cacheScope": "private",
            "resultType": "complete",
            "ttlMs": 0,
        },
    }
    for version, payload in payloads.items():
        dumped = serialize_server_result("tools/list", version, payload)
        output = dumped["tools"][0]["outputSchema"]
        assert output["type"] == "object"
        assert "oneOf" in output or "anyOf" in output


def _listed_output(tool: Any) -> dict[str, Any]:
    schema = getattr(tool, "outputSchema", None) or getattr(tool, "output_schema", None)
    if hasattr(schema, "model_dump"):
        schema = schema.model_dump(by_alias=True)
    assert isinstance(schema, dict)
    return schema


def _body(result: Any) -> dict[str, Any]:
    if result.structured_content:
        return dict(result.structured_content)
    raise AssertionError("expected structured content")


def _accepts(schema: dict[str, Any], instance: Any) -> bool:
    return jsonschema.Draft202012Validator(schema).is_valid(instance)


async def _until_state(client: Client, ticket: dict[str, Any]) -> dict[str, Any]:
    until = asyncio.get_running_loop().time() + 2.0
    while ticket["state"] == "open" and asyncio.get_running_loop().time() < until:
        await asyncio.sleep(0.05)
        ticket = _body(
            await client.call_tool("get_result", {"ticket_id": ticket["ticket_id"]})
        )
    return ticket


@pytest.mark.asyncio
async def test_listed_output_schemas_match_public_results_and_live_bodies():
    team = await Team("content-squad", wait_hold_seconds=0.05).start()
    writer = Writer(name="writer")
    holder = Hold(name="holder")
    await writer.join(team)
    await holder.join(team)
    mcp = create_team_mcp(team)
    try:
        async with Client(mcp) as client:
            tools = {item.name: item for item in (await client.list_tools()).tools}
            outputs = {name: _listed_output(tools[name]) for name in tools}
            for spec in TEAM_TOOL_SPECS:
                advertised = outputs[spec.name]
                expected = public_result_schema(spec.output_model)
                assert advertised == expected
                assert advertised.get("type") == "object"
                assert advertised.get("additionalProperties") is not True
                assert "DictOutput" not in str(advertised.get("title") or "")

            found = _body(
                await client.call_tool(
                    "find", {"query": "someone who can draft a summary"}
                )
            )
            assert _accepts(outputs["find"], found)
            assert not _accepts(outputs["find"], {"matches": [{"address": "writer"}]})

            profiles = _body(
                await client.call_tool(
                    "get_profiles",
                    {"addresses": ["writer", "missing-agent"]},
                )
            )
            assert _accepts(outputs["get_profiles"], profiles)
            assert profiles["items"][0]["status"] == "ok"
            assert profiles["items"][1]["status"] == "error"
            assert not _accepts(outputs["get_profiles"], {"address": "writer"})

            completed = await _until_state(
                client,
                _body(
                    await client.call_tool(
                        "ask",
                        {
                            "recipient": "writer",
                            "content": "draft this",
                            "deadline_seconds": 30,
                        },
                    )
                ),
            )
            assert completed["state"] == "completed"
            assert _accepts(outputs["ask"], completed)
            malformed = dict(completed)
            malformed.pop("ticket_id", None)
            assert not _accepts(outputs["ask"], malformed)

            declined = await _until_state(
                client,
                _body(
                    await client.call_tool(
                        "ask",
                        {
                            "recipient": "writer",
                            "content": "please decline this",
                            "deadline_seconds": 30,
                        },
                    )
                ),
            )
            assert declined["state"] == "declined"
            assert _accepts(outputs["ask"], declined)
            assert _accepts(outputs["get_result"], declined)

            failed = await _until_state(
                client,
                _body(
                    await client.call_tool(
                        "ask",
                        {
                            "recipient": "writer",
                            "content": "please fail this",
                            "deadline_seconds": 30,
                        },
                    )
                ),
            )
            assert failed["state"] == "failed"
            assert _accepts(outputs["ask"], failed)

            opened = _body(
                await client.call_tool(
                    "ask",
                    {
                        "recipient": "holder",
                        "content": "later",
                        "deadline_seconds": 8,
                        "collect": "ticket",
                    },
                )
            )
            assert opened["state"] == "open"
            assert _accepts(outputs["ask"], opened)
            assert "deadline" in opened

            pending = _body(
                await client.call_tool(
                    "ask",
                    {
                        "recipient": "holder",
                        "content": "too late",
                        "deadline_seconds": 1,
                        "collect": "ticket",
                    },
                )
            )
            await asyncio.sleep(1.2)
            expired = _body(
                await client.call_tool(
                    "get_result", {"ticket_id": pending["ticket_id"]}
                )
            )
            assert expired["state"] == "expired"
            assert _accepts(outputs["get_result"], expired)

            told = _body(
                await client.call_tool(
                    "tell", {"recipient": "writer", "content": {"notice": "n"}}
                )
            )
            assert told["status"] == "accepted"
            assert _accepts(outputs["tell"], told)
            assert not _accepts(outputs["tell"], {"status": "accepted", "message": {}})

            history = _body(
                await client.call_tool(
                    "get_history", {"thread_id": completed["thread_id"]}
                )
            )
            assert _accepts(outputs["get_history"], history)
            replies = [
                turn for turn in history["messages"] if turn["kind"] == "response"
            ]
            assert replies
            assert all("parent_id" in turn for turn in replies)
            missing_parent = dict(replies[0])
            missing_parent.pop("parent_id", None)
            assert not _accepts(
                outputs["get_history"],
                {**history, "messages": [missing_parent]},
            )

            error_result = await client.call_tool(
                "get_result",
                {"ticket_id": "00000000-0000-4000-8000-000000000099"},
            )
            assert error_result.is_error
            assert error_result.structured_content["error"]["code"] == "not_found"
    finally:
        await holder.leave()
        await writer.leave()
        await team.stop()
