"""Deterministic structural mutations of the hand-authored rejection corpus.

Expected invalidity comes from the mutation kind, not from validating the
mutated instance against the schema under test. Valid corpus controls must
parse successfully.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterator

import jsonschema
import pytest
from pydantic import TypeAdapter, ValidationError

from agentconnect.core.base import parse_schema
from agentconnect.core.directory import FindRequest
from agentconnect.core.message import parse_message
from agentconnect.core.operations import (
    AskToolRequest,
    CompleteRequest,
    JoinRequest,
    LeaseRequest,
    ReplySuccessRequest,
    parse_send_request,
)
from agentconnect.core.projection import PUBLIC_SCHEMA_TYPES

_REPO = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO / "spec" / "schema" / "schema.json"
_CORPUS_PATH = _REPO / "spec" / "schema" / "rejection.json"
_MESSAGE_TYPES = {
    "RequestMessage",
    "EventMessage",
    "ResponseMessage",
    "ErrorMessage",
}
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
    "JoinRequest": lambda data: parse_schema(JoinRequest, data),
    "AskToolRequest": lambda data: parse_schema(AskToolRequest, data),
    "ReplySuccessRequest": lambda data: parse_schema(ReplySuccessRequest, data),
}


def _load_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_corpus() -> list[dict[str, Any]]:
    payload = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
    return list(payload["vectors"])


def _shape(name: str, schema: dict[str, Any]) -> dict[str, Any]:
    node = schema["definitions"][name]
    if node.get("type") == "object" and "properties" in node:
        return node
    return {}


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


def _is_json_value(prop: dict[str, Any]) -> bool:
    ref = str(prop.get("$ref") or "")
    return ref.endswith("/JsonValue") or ref.endswith("/JsonObject")


def _prop_types(prop: dict[str, Any]) -> set[str]:
    declared = prop.get("type")
    if isinstance(declared, str):
        return {declared}
    if isinstance(declared, list):
        return {str(item) for item in declared}
    return set()


def _wrong_type(prop: dict[str, Any]) -> Any | None:
    if _is_json_value(prop):
        return None
    types = _prop_types(prop)
    if types == {"integer"} or types == {"number"}:
        return "2"
    if types == {"string"}:
        return 2
    if types == {"boolean"}:
        return "true"
    if "const" in prop:
        return 0
    if "enum" in prop:
        return 0
    return None


def _boundary(prop: dict[str, Any]) -> Any | None:
    if _is_json_value(prop):
        return None
    types = _prop_types(prop)
    if types not in ({"integer"}, {"number"}):
        return None
    if "minimum" in prop:
        return prop["minimum"] - 1
    if "maximum" in prop:
        return prop["maximum"] + 1
    return None


def _allows_null(prop: dict[str, Any]) -> bool:
    if _is_json_value(prop):
        return True
    return "null" in _prop_types(prop)


def _mutations(
    vector: dict[str, Any], schema: dict[str, Any]
) -> Iterator[tuple[str, dict[str, Any]]]:
    name = vector["type"]
    instance = vector["instance"]
    if not isinstance(instance, dict):
        return
    shape = _shape(name, schema)
    properties = dict(shape.get("properties") or {})
    required = list(shape.get("required") or [])

    extra = copy.deepcopy(instance)
    extra["unexpected_field"] = True
    yield f"{vector['id']}:extra-field", extra

    for field in required:
        if field not in instance:
            continue
        missing = copy.deepcopy(instance)
        missing.pop(field)
        yield f"{vector['id']}:missing-{field}", missing

    for field, value in list(instance.items()):
        prop = properties.get(field) or {}
        wrong = _wrong_type(prop)
        if wrong is not None and value != wrong:
            mutated = copy.deepcopy(instance)
            mutated[field] = wrong
            yield f"{vector['id']}:wrong-type-{field}", mutated
            break

    for field, value in list(instance.items()):
        prop = properties.get(field) or {}
        bound = _boundary(prop)
        if bound is not None and value != bound:
            mutated = copy.deepcopy(instance)
            mutated[field] = bound
            yield f"{vector['id']}:boundary-{field}", mutated
            break

    for field in list(instance):
        prop = properties.get(field) or {}
        if field in required or _allows_null(prop):
            continue
        mutated = copy.deepcopy(instance)
        mutated[field] = None
        yield f"{vector['id']}:null-{field}", mutated
        break

    if name in _MESSAGE_TYPES and "thread_id" in instance and "seq" in instance:
        drop_thread = copy.deepcopy(instance)
        drop_thread.pop("thread_id")
        yield f"{vector['id']}:thread-without-seq-inverse", drop_thread
        drop_seq = copy.deepcopy(instance)
        drop_seq.pop("seq")
        yield f"{vector['id']}:seq-without-thread-inverse", drop_seq


def _valid_vectors() -> list[dict[str, Any]]:
    return [item for item in _load_corpus() if item["accept"]]


def _generated_cases() -> list[tuple[str, str, dict[str, Any]]]:
    schema = _load_schema()
    cases: list[tuple[str, str, dict[str, Any]]] = []
    for vector in _valid_vectors():
        for case_id, instance in _mutations(vector, schema):
            cases.append((case_id, vector["type"], instance))
    return cases


@pytest.mark.parametrize(
    "vector",
    _valid_vectors(),
    ids=lambda item: f"valid-{item['id']}",
)
def test_valid_corpus_controls_parse(vector: dict[str, Any]) -> None:
    schema = _load_schema()
    name = vector["type"]
    instance = vector["instance"]
    assert _jsonschema_ok(name, instance, schema)
    parser = _PARSERS.get(name)
    if parser is not None:
        parsed = parser(instance)
        assert parsed is not None
    else:
        py_type = PUBLIC_SCHEMA_TYPES[name]
        parsed = py_type.model_validate(instance)
        assert parsed is not None


@pytest.mark.parametrize(
    "case",
    _generated_cases(),
    ids=lambda item: item[0],
)
def test_generated_mutations_are_rejected(case: tuple[str, str, dict[str, Any]]) -> None:
    case_id, name, instance = case
    schema = _load_schema()
    assert not _jsonschema_ok(name, instance, schema), case_id
    assert not _python_ok(name, instance), case_id
