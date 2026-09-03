"""CI proof that ``core/`` matches ``spec/schema/schema.json``.

The test reads the generated JSON Schema and the Python projection map.
It does not copy field lists. Adding a definition in ``schema.ts`` without
a Python type fails; so does a Python model whose properties drifted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal, Union, get_args, get_origin

import jsonschema
from pydantic import BaseModel, TypeAdapter, ValidationError

from agentconnect.core.base import SchemaModel, dump_public
from agentconnect.core.message import RequestMessage
from agentconnect.core.projection import PUBLIC_SCHEMA_TYPES, SCHEMA_WRAPPER_NAME

_REPO = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO / "spec" / "schema" / "schema.json"

_UUID = "00000000-0000-4000-8000-000000000001"
_TIMESTAMP = "2026-08-18T15:00:00Z"
_DID = "did:key:z6MkmEtU9Z7p7G6vbULDgMk8DXCVqW8rNyLMtd2RrAHjLD3m"


def _load_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _definitions(schema: dict[str, Any]) -> dict[str, Any]:
    return dict(schema["definitions"])


def _ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def _resolve(node: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in node and len(node) == 1:
        return _resolve(defs[_ref_name(node["$ref"])], defs)
    return node


def _object_shape(node: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any] | None:
    resolved = _resolve(node, defs)
    if resolved.get("type") == "object" and "properties" in resolved:
        return resolved
    return None


def _literal_values(py_type: Any) -> tuple[Any, ...] | None:
    origin = get_origin(py_type)
    if origin is Literal:
        return get_args(py_type)
    return None


def _is_union(py_type: Any) -> bool:
    origin = get_origin(py_type)
    return origin is Union or origin is getattr(__import__("types"), "UnionType", Union)


def _is_model(py_type: Any) -> bool:
    return isinstance(py_type, type) and issubclass(py_type, BaseModel)


def test_schema_definition_names_match_python_projection():
    defs = set(_definitions(_load_schema()))
    defs.discard(SCHEMA_WRAPPER_NAME)
    python = set(PUBLIC_SCHEMA_TYPES)
    assert (
        defs == python
    ), f"schema-only={sorted(defs - python)} python-only={sorted(python - defs)}"


def test_object_properties_match_pydantic_fields():
    schema = _load_schema()
    defs = _definitions(schema)
    mismatches: list[str] = []
    for name, py_type in PUBLIC_SCHEMA_TYPES.items():
        node = defs[name]
        shape = _object_shape(node, defs)
        if shape is None or not _is_model(py_type):
            continue
        schema_props = set(shape.get("properties") or {})
        model_fields = set(py_type.model_fields)
        if schema_props != model_fields:
            mismatches.append(
                f"{name}: schema={sorted(schema_props)} python={sorted(model_fields)}"
            )
        schema_required = set(shape.get("required") or {})
        missing = schema_required - model_fields
        if missing:
            mismatches.append(f"{name} missing required fields {sorted(missing)}")
    assert mismatches == []


def test_closed_unions_match_enum_values():
    schema = _load_schema()
    defs = _definitions(schema)
    mismatches: list[str] = []
    for name, py_type in PUBLIC_SCHEMA_TYPES.items():
        node = _resolve(defs[name], defs)
        enum_values = node.get("enum")
        literals = _literal_values(py_type)
        if enum_values is None or literals is None:
            continue
        if tuple(enum_values) != literals:
            mismatches.append(f"{name}: schema={enum_values} python={list(literals)}")
    assert mismatches == []


def _sample(
    name: str, node: dict[str, Any], defs: dict[str, Any], depth: int = 0
) -> Any:
    if depth > 12:
        return None
    if "$ref" in node:
        return _sample(
            _ref_name(node["$ref"]), defs[_ref_name(node["$ref"])], defs, depth + 1
        )
    if "const" in node:
        return node["const"]
    if "enum" in node:
        return node["enum"][0]
    if "anyOf" in node:
        if name == "JsonValue":
            return "sample"
        return _sample(name, node["anyOf"][0], defs, depth + 1)
    types = node.get("type")
    if isinstance(types, list):
        types = types[0]
    if types == "object":
        if name == "JsonObject":
            return {"k": "v"}
        props = node.get("properties") or {}
        required = node.get("required") or list(props)
        out: dict[str, Any] = {}
        for key in required:
            if key not in props:
                continue
            out[key] = _sample(key, props[key], defs, depth + 1)
        return out
    if types == "array":
        item = _sample(name, node.get("items") or {"type": "string"}, defs, depth + 1)
        min_items = int(node.get("minItems") or 0)
        count = max(min_items, 1)
        return [item] * count
    if types == "integer":
        minimum = node.get("minimum")
        return int(minimum) if minimum is not None else 1
    if types == "number":
        minimum = node.get("minimum")
        return float(minimum) if minimum is not None else 1.0
    if types == "boolean":
        return True
    if types == "null":
        return None
    pattern = node.get("pattern") or ""
    fmt = node.get("format") or ""
    if name == "Uuid" or fmt == "uuid":
        return _UUID
    if name == "Timestamp" or "date-time" in fmt:
        return _TIMESTAMP
    if name == "AgentDid" or pattern.startswith("^did:key:"):
        return _DID
    if name == "QualifiedAddress":
        return "writer@content-squad"
    if name == "Address":
        return "writer"
    if name == "TeamName":
        return "content-squad"
    if name == "AgentName":
        return "writer"
    if name == "Tag":
        return "writing"
    if name == "SkillExample":
        return "Turn notes into a draft."
    if name == "SpecVersion":
        return "1.0.0-draft"
    if name == "SessionToken":
        return "session-token"
    if fmt == "uri":
        return "https://example.com/callback"
    if pattern:
        matched = _string_for_pattern(pattern)
        if matched is not None:
            return matched
    min_len = int(node.get("minLength") or 0)
    text = "sample value"
    if min_len > len(text):
        text = "x" * min_len
    return text


def _string_for_pattern(pattern: str) -> str | None:
    """Return a value that satisfies ``pattern``, or None if none is known."""
    alphabet = "abcdefghij0123456789ABCxyz-_"
    candidates = [
        "a",
        "ab",
        "writing",
        "drafting",
        "writer",
        "content-squad",
        "samplevalue",
        "n" * 22,
        "n" * 32,
        alphabet,
        "agentconnect:content-squad",
        "https://example.com/callback",
        "session-token",
        "Turn notes into a draft.",
    ]
    for candidate in candidates:
        if re.fullmatch(pattern, candidate):
            return candidate
    for length in range(1, 65):
        candidate = (alphabet * 8)[:length]
        if re.fullmatch(pattern, candidate):
            return candidate
    return None


def _parse_python(name: str, instance: Any) -> Any:
    py_type = PUBLIC_SCHEMA_TYPES[name]
    if _is_model(py_type):
        return py_type.model_validate(instance)
    return TypeAdapter(py_type).validate_python(instance)


def test_generated_instances_round_trip_schema_and_python():
    schema = _load_schema()
    defs = _definitions(schema)
    validator_cls = jsonschema.Draft7Validator
    failures: list[str] = []
    for name, node in defs.items():
        if name == SCHEMA_WRAPPER_NAME:
            continue
        instance = _sample(name, node, defs)
        try:
            validator_cls(
                {"$ref": f"#/definitions/{name}", "definitions": defs},
                format_checker=jsonschema.Draft7Validator.FORMAT_CHECKER,
            ).validate(instance)
        except jsonschema.ValidationError as exc:
            failures.append(f"{name} jsonschema reject: {exc.message}")
            continue
        try:
            parsed = _parse_python(name, instance)
        except (ValidationError, ValueError, TypeError) as exc:
            failures.append(f"{name} python reject: {exc}")
            continue
        dumped = dump_public(parsed)
        try:
            validator_cls(
                {"$ref": f"#/definitions/{name}", "definitions": defs},
                format_checker=jsonschema.Draft7Validator.FORMAT_CHECKER,
            ).validate(dumped)
        except jsonschema.ValidationError as exc:
            failures.append(f"{name} dump jsonschema reject: {exc.message}")
    assert failures == []


def test_required_null_content_survives_python_dump():
    message = RequestMessage(
        id=_UUID,
        sender="writer@content-squad",
        recipient="researcher@content-squad",
        created_at=_TIMESTAMP,
        trace_id=_UUID,
        content=None,
        deadline=_TIMESTAMP,
    )
    dumped = message.to_public_dict()
    assert dumped["content"] is None
    jsonschema.Draft7Validator(
        {
            "$ref": "#/definitions/RequestMessage",
            "definitions": _definitions(_load_schema()),
        }
    ).validate(dumped)


def test_vision_imports_resolve():
    from agentconnect import BaseAgent, Context, Message

    assert BaseAgent is not None
    assert Context is not None
    assert Message is not None
