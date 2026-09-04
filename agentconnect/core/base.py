"""Frozen pydantic base for public schema objects.

Validation belongs at the transport edge. Runtime-owned documents that
already passed acceptance can be built with :meth:`SchemaModel.model_validate`
or the union parsers, which coerce nested objects without a second
hand-written check.
"""

from __future__ import annotations

from typing import Any, Union

from pydantic import BaseModel, ConfigDict, ValidationError
from typing_extensions import TypeAliasType

JsonValue = TypeAliasType(
    "JsonValue",
    Union[str, int, float, bool, None, list["JsonValue"], dict[str, "JsonValue"]],
)
JsonObject = dict[str, JsonValue]


class SchemaModel(BaseModel):
    """Public schema object. Undeclared fields are rejected. Instances are frozen."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def to_public_dict(self) -> dict[str, Any]:
        """JSON-ready mapping. Optional fields that were omitted stay missing.

        Required fields whose JSON value is ``null`` are kept. That matters
        for Message ``content``, which may be null.
        """
        out: dict[str, Any] = {}
        for name, field in type(self).model_fields.items():
            value = getattr(self, name)
            if value is None and not field.is_required():
                continue
            out[name] = dump_public(value)
        return out

    def __getitem__(self, key: str) -> Any:
        """Allow ``result["ticket"]`` on operation results and Messages."""
        if key not in type(self).model_fields:
            raise KeyError(key)
        value = getattr(self, key)
        if value is None and key not in self.model_fields_set:
            raise KeyError(key)
        return value

    def get(self, key: str, default: Any = None) -> Any:
        """Return ``self[key]`` or ``default`` when the field is absent."""
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: object) -> bool:
        """Return True when ``self[key]`` succeeds."""
        if not isinstance(key, str):
            return False
        try:
            self[key]
        except KeyError:
            return False
        return True


def dump_public(value: Any) -> Any:
    """Convert schema models to JSON-ready data.

    MCP tools and Session-bound tools serialize through this helper. A
    tool result is context for a model, and the MCP SDK rejects a typed
    return. Session and ``BaseAgent`` methods return typed objects.
    """
    if isinstance(value, SchemaModel):
        return value.to_public_dict()
    if isinstance(value, dict):
        return {str(key): dump_public(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [dump_public(item) for item in value]
    return value


def validation_message(exc: ValidationError) -> str:
    """Short ``invalid_request`` text from a pydantic error."""
    errors = exc.errors()
    if not errors:
        return "request is invalid"
    first = errors[0]
    loc = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
    msg = str(first.get("msg") or "invalid")
    if loc:
        return f"{loc} {msg}"
    return msg
