"""Wire JSON Schema projection for public schema models."""

from __future__ import annotations

from typing import Any

import jsonschema

from agentconnect.core.base import parse_schema, public_json_schema
from agentconnect.core.directory import FindRequest
from agentconnect.core.operations import (
    AskToolRequest,
    GetHistoryRequest,
    GetResultRequest,
    TellToolRequest,
)

_UUID = "00000000-0000-4000-8000-000000000001"


def _accepts(schema: dict[str, Any], instance: Any) -> bool:
    return jsonschema.Draft202012Validator(schema).is_valid(instance)


def _parse_ok(model: type, instance: Any) -> bool:
    try:
        parse_schema(model, instance)
        return True
    except (ValueError, TypeError):
        return False


def test_unmodified_pydantic_schema_allows_omit_only_null():
    schema = FindRequest.model_json_schema()
    assert _accepts(schema, {"query": "someone who can draft a summary", "limit": None})
    limit = schema["properties"]["limit"]
    assert limit.get("default") is None


def test_find_public_schema_matches_parse_boundary():
    schema = public_json_schema(FindRequest)
    limit = schema["properties"]["limit"]
    assert schema.get("additionalProperties") is False
    assert schema.get("required") == ["query"]
    assert "null" not in (limit.get("type") or "")
    assert limit.get("default") is not None or "default" not in limit
    assert limit.get("minimum") == 1
    assert limit.get("maximum") == 100
    assert limit.get("multipleOf") == 1

    cases = [
        ({"query": "someone who can draft a summary"}, True),
        ({"query": "someone who can draft a summary", "limit": 5}, True),
        ({"query": "someone who can draft a summary", "detail": "full"}, True),
        ({"query": "someone who can draft a summary", "limit": None}, False),
        ({"query": "someone who can draft a summary", "limit": 101}, False),
        ({"query": "someone who can draft a summary", "limit": 0}, False),
        ({"query": "someone who can draft a summary", "limit": "5"}, False),
        ({"query": "someone who can draft a summary", "unknown": True}, False),
        ({"query": "someone who can draft a summary", "detail": "brief"}, False),
        ({"query": "   "}, False),
    ]
    for instance, accept in cases:
        assert _accepts(schema, instance) is accept, instance
        assert _parse_ok(FindRequest, instance) is accept, instance


def test_ask_public_schema_omit_null_bounds_and_identifiers():
    schema = public_json_schema(AskToolRequest)
    valid = {
        "recipient": "writer",
        "content": "draft this",
        "deadline_seconds": 30,
    }
    cases = [
        (valid, True),
        ({**valid, "content": None}, True),
        ({**valid, "collect": "wait"}, True),
        ({**valid, "collect": "callback"}, True),
        ({**valid, "thread_id": _UUID}, True),
        ({**valid, "thread_id": None}, False),
        ({**valid, "idempotency_key": None}, False),
        ({**valid, "deadline_seconds": 0}, False),
        ({**valid, "deadline_seconds": 86401}, False),
        ({**valid, "deadline_seconds": "30"}, False),
        ({**valid, "collect": "nope"}, False),
        ({**valid, "recipient": "!!!"}, False),
        ({**valid, "unknown": True}, False),
        ({"recipient": "writer", "content": "draft this"}, False),
    ]
    for instance, accept in cases:
        assert _accepts(schema, instance) is accept, instance
        assert _parse_ok(AskToolRequest, instance) is accept, instance


def test_tell_get_result_and_history_public_schemas():
    tell = public_json_schema(TellToolRequest)
    result = public_json_schema(GetResultRequest)
    history = public_json_schema(GetHistoryRequest)
    tell_ok = {"recipient": "writer", "content": {"notice": "changed"}}
    assert _accepts(tell, tell_ok)
    assert _parse_ok(TellToolRequest, tell_ok)
    assert not _accepts(tell, {**tell_ok, "thread_id": None})
    assert not _parse_ok(TellToolRequest, {**tell_ok, "thread_id": None})

    assert _accepts(result, {"ticket_id": _UUID})
    assert not _accepts(result, {"ticket_id": "not-a-uuid"})
    assert not _parse_ok(GetResultRequest, {"ticket_id": "not-a-uuid"})

    history_ok = {"thread_id": _UUID}
    assert _accepts(history, history_ok)
    assert _accepts(history, {**history_ok, "limit": 50})
    assert not _accepts(history, {**history_ok, "limit": None})
    assert not _accepts(history, {**history_ok, "limit": 201})
    assert not _accepts(history, {**history_ok, "before": None})
    assert not _parse_ok(GetHistoryRequest, {**history_ok, "limit": 201})
    assert history["properties"]["limit"].get("maximum") == 200
