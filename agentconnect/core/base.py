"""Parse and serialize public schema objects.

`parse_schema` validates untrusted JSON as a schema type. `dump_public`
returns JSON-ready data. Optional fields that were omitted stay missing.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    TypeAlias,
    Any,
    TypeVar,
    Union,
    get_args,
    get_origin,
    overload,
)

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    GetJsonSchemaHandler,
    TypeAdapter,
    ValidationError,
    model_validator,
)
from typing_extensions import Annotated, TypeAliasType
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

if TYPE_CHECKING:
    JsonValue: TypeAlias = Union[
        str, int, float, bool, None, list["JsonValue"], dict[str, "JsonValue"]
    ]
    """Application JSON content, including null and nested arrays or objects."""
else:
    JsonValue = TypeAliasType(
        "JsonValue",
        Union[str, int, float, bool, None, list["JsonValue"], dict[str, "JsonValue"]],
    )
"""Application JSON content, including null and nested arrays or objects."""
JsonObject = dict[str, JsonValue]
"""Application JSON object with string keys."""

TSchema = TypeVar("TSchema", bound="SchemaModel")


def _json_int(value: object) -> int:
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


def _json_float(value: object) -> float:
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


def _promote_numeric_bounds(node: JsonSchemaValue) -> None:
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
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """Emit a JSON number with ``multipleOf: 1``."""
        schema = handler(core_schema)
        schema["type"] = "number"
        schema["multipleOf"] = 1
        _promote_numeric_bounds(schema)
        return schema


JsonInt = Annotated[int, BeforeValidator(_json_int), _JsonIntJsonSchema()]
"""Whole JSON number; booleans and numeric strings are rejected."""
JsonFloat = Annotated[float, BeforeValidator(_json_float)]
"""Finite JSON number; booleans and numeric strings are rejected."""


def _annotation_allows_json_null(annotation: object) -> bool:
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
    def reject_json_null_on_omitted_fields(cls, data: object) -> object:
        """Reject JSON null on fields that JSON Schema treats as omit-only."""
        return _reject_null_for_omitted_fields(cls, data)

    def to_public_dict(self) -> JsonObject:
        """Return JSON-ready fields, omitting optional values that are absent.

        Required JSON-null content is kept. Nested models are serialized recursively.
        """
        out: JsonObject = {}
        for name, field in type(self).model_fields.items():
            value = getattr(self, name)
            if value is None and not field.is_required():
                continue
            out[name] = dump_public(value)
        return out

    def __getitem__(self, key: str) -> Any:
        """Read a declared field by name.

        Raises:
            KeyError: The field is undeclared or was omitted.
        """
        if key not in type(self).model_fields:
            raise KeyError(key)
        value = getattr(self, key)
        if value is None and key not in self.model_fields_set:
            raise KeyError(key)
        return value

    def get(self, key: str, default: Any = None) -> Any:
        """Read a field, using `default` when it is undeclared or omitted."""
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: object) -> bool:
        """Return whether a declared field is present rather than omitted."""
        if not isinstance(key, str):
            return False
        try:
            self[key]
        except KeyError:
            return False
        return True


def _reject_null_for_omitted_fields(cls: type[SchemaModel], data: object) -> object:
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


def _unwrap_optional_annotation(annotation: object) -> object:
    """Return the non-None member of ``Optional[T]``, else ``annotation``."""
    origin = get_origin(annotation)
    if origin is Union:
        rest = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(rest) == 1:
            return rest[0]
    return annotation


def _annotation_is_json_int(annotation: object) -> bool:
    """Return True when the field is ``JsonInt`` or ``Optional[JsonInt]``."""
    return _unwrap_optional_annotation(annotation) is JsonInt


def _is_null_type_schema(node: Mapping[str, object]) -> bool:
    """Return True when ``node`` is a JSON Schema that only accepts null."""
    if node.get("type") == "null" and set(node) <= {"type", "title"}:
        return True
    types = node.get("type")
    return isinstance(types, list) and types == ["null"]


def _unwrap_omit_only(node: JsonSchemaValue) -> JsonSchemaValue:
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


def _schema_allows_json_null(node: Mapping[str, object]) -> bool:
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


def _rewrite_json_schema(node: object) -> object:
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


def _as_json_int_schema(node: JsonSchemaValue) -> JsonSchemaValue:
    """Apply the public ``JsonInt`` wire shape to one property schema."""
    node = dict(node)
    node["type"] = "number"
    node["multipleOf"] = 1
    _promote_numeric_bounds(node)
    if node.get("default") is None:
        node.pop("default", None)
    return node


def _apply_json_int_fields(model: type[SchemaModel], schema: JsonSchemaValue) -> None:
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


def public_json_schema(model: type[SchemaModel]) -> JsonSchemaValue:
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


def public_result_schema(model: object) -> JsonSchemaValue:
    """Return a JSON Schema for a Team tool success result.

    Tagged object unions keep their variants and advertise an object result.
    Omit-only optional fields do not accept JSON null.
    """
    if isinstance(model, type) and issubclass(model, SchemaModel):
        return public_json_schema(model)
    adapter: TypeAdapter[object] = TypeAdapter(model)
    schema = _rewrite_json_schema(copy.deepcopy(adapter.json_schema()))
    if not isinstance(schema, dict):
        raise TypeError("result JSON Schema must be an object")
    if schema.get("type") == "object" or "properties" in schema:
        schema.setdefault("type", "object")
        schema.setdefault("additionalProperties", False)
        return schema
    if "anyOf" in schema or "oneOf" in schema:
        schema["type"] = "object"
    return schema


@overload
def dump_public(value: SchemaModel) -> JsonObject: ...


@overload
def dump_public(value: Any) -> Any: ...


def dump_public(value: Any) -> Any:
    """Serialize public models, nested dicts and lists to JSON-ready data.

    Omit-only optional fields stay missing; required JSON-null content stays null.
    Use this for wire or tool output rather than a model dump that adds absent keys.

    Examples:
        For `profile`, an existing AgentProfile with no description:

        ```python
        from agentconnect.core.base import dump_public

        body = dump_public(profile)
        assert "description" not in body
        ```
    """
    if isinstance(value, SchemaModel):
        return value.to_public_dict()
    if isinstance(value, dict):
        return {str(key): dump_public(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [dump_public(item) for item in value]
    return value


def parse_schema(model: type[TSchema], data: object) -> TSchema:
    """Validate a mapping as a public model; return an existing instance unchanged.

    Raises:
        ValueError: Input is not an object or fails the model's validation.
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
