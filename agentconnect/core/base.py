"""Parse and serialize public schema objects.

`parse_schema` validates untrusted JSON as a schema type. `dump_public`
returns JSON-ready data. Optional fields that were omitted stay missing.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from typing import Any, TypeVar, Union, get_args, get_origin

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    TypeAdapter,
    ValidationError,
    model_validator,
)
from typing_extensions import Annotated, TypeAliasType

JsonValue = TypeAliasType(  # type: ignore[misc]
    "JsonValue",
    Union[str, int, float, bool, None, list["JsonValue"], dict[str, "JsonValue"]],  # type: ignore[misc]
)
JsonObject = dict[str, JsonValue]  # type: ignore[misc]

TSchema = TypeVar("TSchema", bound="SchemaModel")


def _json_int(value: Any) -> Any:
    """Accept JSON numbers that are finite whole values. Reject bool and str."""
    if isinstance(value, bool):
        raise ValueError("must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError("must be an integer")
        return int(value)
    raise ValueError("must be an integer")


def _json_float(value: Any) -> Any:
    """Accept JSON numbers, including integers. Reject bool, str, and inf."""
    if isinstance(value, bool):
        raise ValueError("must be a number")
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("must be a finite number")
        return value
    raise ValueError("must be a number")


def _promote_numeric_bounds(node: dict[str, Any]) -> None:
    """Rewrite pydantic ``ge``/``le`` to JSON Schema minimum/maximum."""
    mapping = (
        ("ge", "minimum"),
        ("le", "maximum"),
        ("gt", "exclusiveMinimum"),
        ("lt", "exclusiveMaximum"),
    )
    for source, dest in mapping:
        if source in node:
            node.setdefault(dest, node.pop(source))


class _JsonIntJsonSchema:
    """Wire schema for ``JsonInt``: a JSON number that is a whole value."""

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: Any, handler: Any
    ) -> dict[str, Any]:
        """Emit a JSON number with ``multipleOf: 1``."""
        schema = handler(core_schema)
        schema["type"] = "number"
        schema["multipleOf"] = 1
        _promote_numeric_bounds(schema)
        return schema


JsonInt = Annotated[int, BeforeValidator(_json_int), _JsonIntJsonSchema()]
JsonFloat = Annotated[float, BeforeValidator(_json_float)]


def _annotation_allows_json_null(annotation: Any) -> bool:
    """Return True when the field's JSON type includes null, such as content."""
    candidates = [annotation, *get_args(annotation)]
    origin = get_origin(annotation)
    if origin is not None:
        candidates.append(origin)
    for item in candidates:
        if item is JsonValue:
            return True
        if getattr(item, "__name__", None) == "JsonValue":
            return True
    return False


class SchemaModel(BaseModel):
    """Frozen public schema object. Undeclared fields are rejected.

    Parse untrusted JSON with `parse_schema`. Serialize with `dump_public`
    or `to_public_dict`. Wire input is strict: a string is not an integer,
    `true` is not `1`, and an optional field must be omitted rather than
    sent as JSON null.

    Mapping-style access (`result["ticket"]`, `.get`, `in`) works on
    operation results and Messages. An omitted optional field is absent.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    @model_validator(mode="before")
    @classmethod
    def reject_json_null_on_omitted_fields(cls, data: Any) -> Any:
        """Reject JSON null on fields that JSON Schema treats as omit-only."""
        return _reject_null_for_omitted_fields(cls, data)

    def to_public_dict(self) -> dict[str, Any]:
        """JSON-ready mapping. Optional fields that were omitted stay missing.

        Required fields whose JSON value is `null` are kept. That matters
        for Message `content`, which may be null.

        Returns:
            A dict suitable for JSON encoding.
        """
        out: dict[str, Any] = {}
        for name, field in type(self).model_fields.items():
            value = getattr(self, name)
            if value is None and not field.is_required():
                continue
            out[name] = dump_public(value)
        return out

    def __getitem__(self, key: str) -> Any:
        """Return a declared field by name, as `result["ticket"]`.

        Args:
            key: Field name on this model.

        Returns:
            The field value.

        Raises:
            KeyError: `key` is not a field, or an optional field was omitted.
        """
        if key not in type(self).model_fields:
            raise KeyError(key)
        value = getattr(self, key)
        if value is None and key not in self.model_fields_set:
            raise KeyError(key)
        return value

    def get(self, key: str, default: Any = None) -> Any:
        """Return `self[key]` or `default` when the field is absent.

        Args:
            key: Field name on this model.
            default: Value when `key` is missing or omitted.

        Returns:
            The field value, or `default`.
        """
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: object) -> bool:
        """Return True when `self[key]` succeeds.

        Args:
            key: Field name to test.

        Returns:
            True when the field is present and was not omitted.
        """
        if not isinstance(key, str):
            return False
        try:
            self[key]
        except KeyError:
            return False
        return True


def _reject_null_for_omitted_fields(cls: type[SchemaModel], data: Any) -> Any:
    """Reject JSON null on fields that JSON Schema treats as omit-only."""
    if not isinstance(data, Mapping):
        return data
    for name, field in cls.model_fields.items():
        if name not in data or data[name] is not None:
            continue
        if _annotation_allows_json_null(field.annotation):
            continue
        raise ValueError(f"{name} must be omitted rather than null")
    return data


def _unwrap_optional_annotation(annotation: Any) -> Any:
    """Return the non-None member of ``Optional[T]``, else ``annotation``."""
    origin = get_origin(annotation)
    if origin is Union:
        rest = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(rest) == 1:
            return rest[0]
    return annotation


def _annotation_is_json_int(annotation: Any) -> bool:
    """Return True when the field is ``JsonInt`` or ``Optional[JsonInt]``."""
    return _unwrap_optional_annotation(annotation) is JsonInt


def _is_null_type_schema(node: Mapping[str, Any]) -> bool:
    """Return True when ``node`` is a JSON Schema that only accepts null."""
    if node.get("type") == "null" and set(node) <= {"type", "title"}:
        return True
    types = node.get("type")
    return isinstance(types, list) and types == ["null"]


def _unwrap_omit_only(node: dict[str, Any]) -> dict[str, Any]:
    """Replace ``T | null`` with ``T`` for omit-only optional fields."""
    types = node.get("type")
    if isinstance(types, list) and "null" in types:
        others = [item for item in types if item != "null"]
        if len(others) == 1:
            node = dict(node)
            node["type"] = others[0]
            if node.get("default") is None:
                node.pop("default", None)
            return node
    key = "anyOf" if "anyOf" in node else "oneOf" if "oneOf" in node else None
    if key is None:
        return node
    variants = node[key]
    if not isinstance(variants, list) or len(variants) != 2:
        return node
    nulls = [item for item in variants if _is_null_type_schema(item)]
    others = [item for item in variants if not _is_null_type_schema(item)]
    if len(nulls) != 1 or len(others) != 1:
        return node
    unwrapped = dict(others[0])
    for name, value in node.items():
        if name == key:
            continue
        if name == "default" and value is None:
            continue
        if name not in unwrapped:
            unwrapped[name] = value
    if unwrapped.get("default") is None:
        unwrapped.pop("default", None)
    return unwrapped


def _schema_allows_json_null(node: Mapping[str, Any]) -> bool:
    """Return True when this schema node accepts JSON null."""
    if _is_null_type_schema(node):
        return True
    types = node.get("type")
    if isinstance(types, list) and "null" in types:
        return True
    for key in ("anyOf", "oneOf"):
        variants = node.get(key)
        if isinstance(variants, list) and any(
            isinstance(item, Mapping) and _is_null_type_schema(item)
            for item in variants
        ):
            return True
    return False


def _rewrite_json_schema(node: Any) -> Any:
    """Walk a pydantic JSON Schema and encode omit-only optional fields."""
    if isinstance(node, list):
        return [_rewrite_json_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    rewritten = {key: _rewrite_json_schema(value) for key, value in node.items()}
    rewritten = _unwrap_omit_only(rewritten)
    _promote_numeric_bounds(rewritten)
    if rewritten.get("default") is None and "default" in rewritten:
        if not _schema_allows_json_null(rewritten):
            rewritten.pop("default", None)
    return rewritten


def _as_json_int_schema(node: dict[str, Any]) -> dict[str, Any]:
    """Apply the public ``JsonInt`` wire shape to one property schema."""
    node = dict(node)
    node["type"] = "number"
    node["multipleOf"] = 1
    _promote_numeric_bounds(node)
    if node.get("default") is None:
        node.pop("default", None)
    return node


def _apply_json_int_fields(model: type[SchemaModel], schema: dict[str, Any]) -> None:
    """Force ``JsonInt`` properties to number + multipleOf after omit-only unwrap."""
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return
    for name, field in model.model_fields.items():
        if name not in properties or not _annotation_is_json_int(field.annotation):
            continue
        prop = properties[name]
        if isinstance(prop, dict):
            properties[name] = _as_json_int_schema(prop)


def public_json_schema(model: type[SchemaModel]) -> dict[str, Any]:
    """JSON Schema for ``model`` as sent on the wire.

    Optional fields are omit-only: JSON null is not in the type, and
    ``default: null`` is not advertised. ``JsonInt`` is a JSON number with
    ``multipleOf: 1``. Undeclared properties are forbidden. Unmodified
    pydantic ``model_json_schema()`` output does not encode omit-only
    fields this way.
    """
    schema = _rewrite_json_schema(copy.deepcopy(model.model_json_schema()))
    if not isinstance(schema, dict):
        raise TypeError("model JSON Schema must be an object")
    schema.setdefault("type", "object")
    schema.setdefault("additionalProperties", False)
    _apply_json_int_fields(model, schema)
    return schema


def public_result_schema(model: Any) -> dict[str, Any]:
    """JSON Schema for a tool success result, including tagged unions.

    MCP structuredContent may be any JSON value. Team tool results are
    JSON objects, so this projection advertises ``type: object``. Tagged
    unions of public objects keep ``oneOf``/``anyOf``; the wrapper does
    not set ``additionalProperties``, which would make variants
    uninhabitable.
    """
    if isinstance(model, type) and issubclass(model, SchemaModel):
        return public_json_schema(model)
    schema = _rewrite_json_schema(copy.deepcopy(TypeAdapter(model).json_schema()))
    if not isinstance(schema, dict):
        raise TypeError("result JSON Schema must be an object")
    if schema.get("type") == "object" or "properties" in schema:
        schema.setdefault("type", "object")
        schema.setdefault("additionalProperties", False)
        return schema
    if "anyOf" in schema or "oneOf" in schema:
        schema["type"] = "object"
    return schema


def dump_public(value: Any) -> Any:
    """Convert schema models to JSON-ready data.

    Omit-only optional fields stay missing. Nested models, lists, and
    dicts are converted recursively. MCP tools and Session-bound tools
    serialize through this helper. Session and `BaseAgent` methods
    return typed objects.

    Args:
        value: A `SchemaModel`, mapping, sequence, or JSON scalar.

    Returns:
        JSON-ready data with the same shape.

    Examples:
        ```python
        from agentconnect.core.base import dump_public
        from agentconnect.core.profile import AgentProfile, Skill

        profile = AgentProfile(
            summary="Writes short drafts from notes.",
            skills=[Skill(name="drafting", description="Turn notes into a draft.")],
        )
        dump_public(profile)["summary"]
        ```
    """
    if isinstance(value, SchemaModel):
        return value.to_public_dict()
    if isinstance(value, dict):
        return {str(key): dump_public(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [dump_public(item) for item in value]
    return value


def parse_schema(model: type[TSchema], data: Any) -> TSchema:
    """Parse a mapping as `model` at an untrusted edge.

    An instance of `model` is returned unchanged. Any other non-mapping
    value fails.

    Args:
        model: Schema class to validate against.
        data: JSON object, or an existing `model` instance.

    Returns:
        A frozen `model` instance.

    Raises:
        ValueError: `data` is not an object, or it fails validation.

    Examples:
        ```python
        from agentconnect.core.base import parse_schema
        from agentconnect.core.operations import LeaseRequest

        lease = parse_schema(LeaseRequest, {"max_items": 2})
        ```
    """
    if isinstance(data, model):
        return data
    if not isinstance(data, Mapping):
        raise ValueError("request body must be an object")
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ValueError(validation_message(exc)) from exc


def validation_message(exc: ValidationError) -> str:
    """Short `invalid_request` text from a pydantic error.

    Args:
        exc: Pydantic validation failure.

    Returns:
        One-line text naming the first field and its problem.
    """
    errors = exc.errors()
    if not errors:
        return "request is invalid"
    first = errors[0]
    loc = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
    msg = str(first.get("msg") or "invalid")
    if loc:
        return f"{loc} {msg}"
    return msg
