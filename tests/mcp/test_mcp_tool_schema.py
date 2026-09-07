"""Advertised MCP tool schemas match the raw tools/call argument boundary."""

from __future__ import annotations

import json
from typing import Any

import jsonschema
import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.shared.exceptions import MCPError
from mcp_types import INVALID_PARAMS

from agentconnect.agent import BaseAgent
from agentconnect.core.base import parse_schema, public_json_schema
from agentconnect.core.directory import FindRequest
from agentconnect.core.operations import (
    AskToolRequest,
    GetHistoryRequest,
    GetResultRequest,
    TellToolRequest,
)
from agentconnect.core.primitives import ERROR_CODES
from agentconnect.mcp.server import create_team_mcp
from agentconnect.mcp.tool_schema import advertise_tool_schema
from agentconnect.team import Team

_QUERY = "someone who can draft a summary"
_UUID = "00000000-0000-4000-8000-000000000099"
_TOOL_MODELS = {
    "find": FindRequest,
    "ask": AskToolRequest,
    "tell": TellToolRequest,
    "get_result": GetResultRequest,
    "get_history": GetHistoryRequest,
}


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

    async def handle(self, message, ctx) -> Any:
        if message.kind == "request" and getattr(message, "deadline", None):
            return {"echo": message.content}
        return None


async def ping() -> dict[str, str]:
    """Return a heartbeat for extra-tool tests."""
    return {"status": "ok"}


async def annotate(text: str, **attrs: Any) -> dict[str, Any]:
    """Accept a note plus arbitrary keyword attributes."""
    return {"text": text, **attrs}


def _listed_schema(tool: Any) -> dict[str, Any]:
    schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None)
    if hasattr(schema, "model_dump"):
        schema = schema.model_dump()
    assert isinstance(schema, dict)
    return schema


def _schema_accepts(schema: dict[str, Any], instance: Any) -> bool:
    return jsonschema.Draft202012Validator(schema).is_valid(instance)


def _parse_ok(model: type, instance: Any) -> bool:
    try:
        parse_schema(model, instance)
        return True
    except (ValueError, TypeError):
        return False


def _body(result: Any) -> dict[str, Any]:
    if result.structured_content:
        return dict(result.structured_content)
    if result.content:
        return json.loads(result.content[0].text)
    raise AssertionError("empty tool result")


def _walk_error(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        nested = value.get("error")
        if isinstance(nested, dict) and nested.get("code") in ERROR_CODES:
            return nested
        if value.get("code") in ERROR_CODES:
            return value
        for item in value.values():
            found = _walk_error(item)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _walk_error(item)
            if found is not None:
                return found
    elif isinstance(value, str):
        try:
            return _walk_error(json.loads(value))
        except json.JSONDecodeError:
            for code in ERROR_CODES:
                if code in value:
                    return {"code": code, "message": value}
    return None


def _error(result: Any) -> dict[str, Any]:
    assert result.is_error
    dumped = result.model_dump(mode="json") if hasattr(result, "model_dump") else {}
    found = _walk_error(dumped)
    if found is not None:
        return found
    return {"code": "tool_error", "message": json.dumps(dumped)}


def _mcp_error_codes(exc: BaseException) -> list[int]:
    if isinstance(exc, BaseExceptionGroup):
        codes: list[int] = []
        for item in exc.exceptions:
            codes.extend(_mcp_error_codes(item))
        return codes
    if isinstance(exc, MCPError):
        return [exc.code]
    return []


async def _invoke(
    client: Client, name: str, arguments: dict[str, Any]
) -> tuple[str, Any]:
    invalid = False
    codes: list[int] = []
    result: Any = None
    try:
        result = await client.call_tool(name, arguments)
    except* MCPError as group:
        invalid = True
        codes = _mcp_error_codes(group)
    if invalid:
        assert INVALID_PARAMS in codes, codes
        return "invalid_params", None
    if getattr(result, "is_error", False):
        err = _error(result)
        return str(err.get("code") or "tool_error"), result
    return "ok", result


@pytest.mark.asyncio
async def test_advertise_tool_schema_replaces_handler_signature_schema():
    async def find(
        query: str, limit: int | None = None, detail: str = "summary"
    ) -> dict[str, str]:
        return {}

    mcp = MCPServer("schema-adapter")
    mcp.add_tool(find, name="find")
    inferred = mcp._tool_manager.get_tool("find").parameters
    assert _schema_accepts(inferred, {"query": _QUERY, "limit": None})
    assert _schema_accepts(inferred, {"query": _QUERY, "limit": 101})

    assigned = advertise_tool_schema(mcp, "find", FindRequest)
    assert assigned == public_json_schema(FindRequest)
    async with Client(mcp) as client:
        tools = {item.name: item for item in (await client.list_tools()).tools}
        listed = _listed_schema(tools["find"])
    assert listed == assigned
    assert not _schema_accepts(listed, {"query": _QUERY, "limit": None})
    assert not _schema_accepts(listed, {"query": _QUERY, "limit": 101})
    assert _schema_accepts(listed, {"query": _QUERY})


@pytest.mark.asyncio
async def test_listed_schemas_agree_with_raw_call_for_builtin_tools():
    team = await Team("content-squad").start()
    writer = Writer(name="writer")
    await writer.join(team)
    mcp = create_team_mcp(team)
    try:
        async with Client(mcp) as client:
            tools = {item.name: item for item in (await client.list_tools()).tools}
            schemas = {name: _listed_schema(tools[name]) for name in _TOOL_MODELS}

            for name, schema in schemas.items():
                projected = public_json_schema(_TOOL_MODELS[name])
                assert schema.get("additionalProperties") is False
                assert schema.get("required") == projected.get("required")

            found = _body(await client.call_tool("find", {"query": _QUERY}))
            assert found["matches"]
            recipient = next(
                str(item["address"])
                for item in found["matches"]
                if str(item["address"]).startswith("writer@")
            )

            static: list[tuple[str, dict[str, Any], str]] = [
                ("find", {"query": _QUERY}, "ok"),
                ("find", {"query": _QUERY, "limit": 5, "detail": "summary"}, "ok"),
                ("find", {"query": _QUERY, "limit": None}, "invalid_params"),
                ("find", {"query": _QUERY, "limit": 101}, "invalid_params"),
                ("find", {"query": _QUERY, "limit": 0}, "invalid_params"),
                ("find", {"query": _QUERY, "limit": "5"}, "invalid_params"),
                ("find", {"query": _QUERY, "unknown": True}, "invalid_params"),
                ("find", {"query": _QUERY, "detail": "brief"}, "invalid_params"),
                (
                    "ask",
                    {
                        "recipient": recipient,
                        "content": "draft this",
                        "deadline_seconds": 30,
                    },
                    "ok",
                ),
                (
                    "ask",
                    {
                        "recipient": recipient,
                        "content": None,
                        "deadline_seconds": 30,
                    },
                    "ok",
                ),
                (
                    "ask",
                    {
                        "recipient": recipient,
                        "content": "draft this",
                        "deadline_seconds": 30,
                        "collect": "wait",
                    },
                    "ok",
                ),
                (
                    "ask",
                    {
                        "recipient": recipient,
                        "content": "draft this",
                        "deadline_seconds": 30,
                        "thread_id": None,
                    },
                    "invalid_params",
                ),
                (
                    "ask",
                    {
                        "recipient": recipient,
                        "content": "draft this",
                        "deadline_seconds": "30",
                    },
                    "invalid_params",
                ),
                (
                    "ask",
                    {
                        "recipient": recipient,
                        "content": "draft this",
                        "deadline_seconds": 0,
                    },
                    "invalid_params",
                ),
                (
                    "ask",
                    {
                        "recipient": recipient,
                        "content": "draft this",
                        "deadline_seconds": 86401,
                    },
                    "invalid_params",
                ),
                (
                    "ask",
                    {
                        "recipient": recipient,
                        "content": "draft this",
                        "deadline_seconds": 30,
                        "collect": "nope",
                    },
                    "invalid_params",
                ),
                (
                    "ask",
                    {
                        "recipient": "!!!",
                        "content": "draft this",
                        "deadline_seconds": 30,
                    },
                    "invalid_params",
                ),
                (
                    "ask",
                    {
                        "recipient": recipient,
                        "content": "draft this",
                        "deadline_seconds": 30,
                        "extra": True,
                    },
                    "invalid_params",
                ),
                (
                    "ask",
                    {
                        "recipient": "missing-agent",
                        "content": "draft this",
                        "deadline_seconds": 30,
                    },
                    "not_found",
                ),
                ("tell", {"recipient": recipient, "content": "note"}, "ok"),
                (
                    "tell",
                    {"recipient": recipient, "content": "note", "thread_id": None},
                    "invalid_params",
                ),
                ("get_result", {"ticket_id": "not-a-uuid"}, "invalid_params"),
                ("get_result", {"ticket_id": _UUID}, "not_found"),
                ("get_history", {"thread_id": "not-a-uuid"}, "invalid_params"),
                ("get_history", {"thread_id": _UUID, "limit": None}, "invalid_params"),
                ("get_history", {"thread_id": _UUID, "limit": 201}, "invalid_params"),
                ("get_history", {"thread_id": _UUID, "before": None}, "invalid_params"),
                ("get_history", {"thread_id": _UUID}, "not_found"),
            ]

            ticket_body = None
            for name, arguments, expected in static:
                schema = schemas[name]
                model = _TOOL_MODELS[name]
                schema_ok = _schema_accepts(schema, arguments)
                parse_ok = _parse_ok(model, arguments)
                assert schema_ok is parse_ok, (name, arguments)
                kind, result = await _invoke(client, name, arguments)
                if expected == "invalid_params":
                    assert not schema_ok, (name, arguments)
                    assert kind == "invalid_params", (name, arguments, kind)
                    continue
                assert schema_ok, (name, arguments)
                assert kind == expected, (name, arguments, kind)
                if expected == "ok" and name == "ask" and ticket_body is None:
                    ticket_body = _body(result)
                    assert ticket_body.get("id")
                    assert ticket_body.get("thread_id")

            assert ticket_body is not None
            kind, result = await _invoke(
                client, "get_result", {"ticket_id": ticket_body["id"]}
            )
            assert _schema_accepts(schemas["get_result"], {"ticket_id": ticket_body["id"]})
            assert kind == "ok"
            assert _body(result)["id"] == ticket_body["id"]

            history_args = {"thread_id": ticket_body["thread_id"]}
            kind, result = await _invoke(client, "get_history", history_args)
            assert _schema_accepts(schemas["get_history"], history_args)
            assert kind == "ok"
            assert "messages" in _body(result)

            omitted_limit = {
                "thread_id": ticket_body["thread_id"],
            }
            kind, result = await _invoke(client, "get_history", omitted_limit)
            assert _schema_accepts(schemas["get_history"], omitted_limit)
            assert kind == "ok"
    finally:
        await writer.leave()
        await team.stop()


@pytest.mark.asyncio
async def test_kwargs_extra_tool_keeps_open_declared_schema():
    team = await Team("content-squad", tools=[annotate, ping]).start()
    mcp = create_team_mcp(team)
    try:
        async with Client(mcp) as client:
            tools = {item.name: item for item in (await client.list_tools()).tools}
            open_schema = _listed_schema(tools["annotate"])
            assert open_schema.get("additionalProperties") is not False
            closed_schema = _listed_schema(tools["ping"])
            assert closed_schema.get("additionalProperties") is False
            kind, result = await _invoke(client, "ping", {})
            assert kind == "ok"
            assert _body(result).get("status") == "ok"
            kind, _ = await _invoke(client, "ping", {"extra": True})
            assert kind == "invalid_params"
            assert not _schema_accepts(closed_schema, {"extra": True})
    finally:
        await team.stop()
