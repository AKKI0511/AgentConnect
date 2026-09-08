"""Shared schema rejection corpus against JSON Schema and Python."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import TypeAdapter, ValidationError

from agentconnect.core.base import parse_schema
from agentconnect.core.directory import FindRequest
from agentconnect.core.message import EventMessage, parse_message
from agentconnect.core.operations import (
    AskToolRequest,
    CompleteRequest,
    JoinRequest,
    LeaseRequest,
    RenewRequest,
    ReplySuccessRequest,
    parse_send_request,
)
from agentconnect.core.projection import PUBLIC_SCHEMA_TYPES

_REPO = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO / "spec" / "schema" / "schema.json"
_CORPUS_PATH = _REPO / "spec" / "schema" / "rejection.json"

_PARSERS = {
    "RequestMessage": parse_message,
    "EventMessage": parse_message,
    "ResponseMessage": parse_message,
    "ErrorMessage": parse_message,
    "RequestSendRequest": parse_send_request,
    "EventSendRequest": parse_send_request,
    "SendRequest": parse_send_request,
    "FindRequest": lambda data: parse_schema(FindRequest, data),
    "LeaseRequest": lambda data: parse_schema(LeaseRequest, data),
    "CompleteRequest": lambda data: parse_schema(CompleteRequest, data),
    "RenewRequest": lambda data: parse_schema(RenewRequest, data),
    "JoinRequest": lambda data: parse_schema(JoinRequest, data),
    "AskToolRequest": lambda data: parse_schema(AskToolRequest, data),
    "ReplySuccessRequest": lambda data: parse_schema(ReplySuccessRequest, data),
}


def _load_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_corpus() -> list[dict[str, Any]]:
    payload = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
    return list(payload["vectors"])


def _jsonschema_ok(name: str, instance: Any, schema: dict[str, Any]) -> bool:
    validator = jsonschema.Draft7Validator(
        {"$ref": f"#/definitions/{name}", "definitions": schema["definitions"]},
        format_checker=jsonschema.Draft7Validator.FORMAT_CHECKER,
    )
    return validator.is_valid(instance)


def _python_ok(name: str, instance: Any) -> bool:
    parser = _PARSERS.get(name)
    try:
        if parser is not None:
            parser(instance)
            return True
        py_type = PUBLIC_SCHEMA_TYPES[name]
        if hasattr(py_type, "model_validate"):
            py_type.model_validate(instance)
            return True
        TypeAdapter(py_type).validate_python(instance)
        return True
    except (ValidationError, ValueError, TypeError):
        return False


@pytest.mark.parametrize(
    "vector",
    _load_corpus(),
    ids=lambda item: item["id"],
)
def test_rejection_corpus_jsonschema_and_python_agree(vector: dict[str, Any]) -> None:
    schema = _load_schema()
    name = vector["type"]
    instance = vector["instance"]
    accept = bool(vector["accept"])
    json_ok = _jsonschema_ok(name, instance, schema)
    py_ok = _python_ok(name, instance)
    assert json_ok is accept, f"{vector['id']} jsonschema accept={json_ok}"
    assert py_ok is accept, f"{vector['id']} python accept={py_ok}"


def test_schema_json_binds_thread_and_seq() -> None:
    defs = _load_schema()["definitions"]
    for name in ("RequestMessage", "EventMessage", "ResponseMessage", "ErrorMessage"):
        all_of = defs[name].get("allOf") or []
        dumped = json.dumps(all_of)
        assert "thread_id" in dumped and "seq" in dumped


def test_seq_without_thread_is_invalid() -> None:
    with pytest.raises(ValueError, match="seq"):
        parse_message(
            {
                "id": "00000000-0000-4000-8000-000000000001",
                "sender": "researcher@content-squad",
                "sender_did": "did:key:z6MkmEtU9Z7p7G6vbULDgMk8DXCVqW8rNyLMtd2RrAHjLD3m",
                "recipient": "writer@content-squad",
                "kind": "event",
                "content": "note",
                "created_at": "2026-08-18T15:00:00Z",
                "trace_id": "00000000-0000-4000-8000-000000000002",
                "seq": 1,
            }
        )


def test_event_message_requires_kind_on_the_wire() -> None:
    data = {
        "id": "00000000-0000-4000-8000-000000000001",
        "sender": "researcher@content-squad",
        "sender_did": "did:key:z6MkmEtU9Z7p7G6vbULDgMk8DXCVqW8rNyLMtd2RrAHjLD3m",
        "recipient": "writer@content-squad",
        "content": "note",
        "created_at": "2026-08-18T15:00:00Z",
        "trace_id": "00000000-0000-4000-8000-000000000002",
    }
    with pytest.raises(ValidationError):
        EventMessage.model_validate(data)
    with pytest.raises(ValueError, match="kind"):
        parse_message(data)
