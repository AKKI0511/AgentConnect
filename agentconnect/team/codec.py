"""JSON, timestamp, id, and identity helpers used by the Team Runtime."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

_DID_KEY = re.compile(r"^did:key:z[1-9A-HJ-NP-Za-km-z]+$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")


def utc_now() -> datetime:
    """Return the current UTC time with tzinfo set."""
    return datetime.now(timezone.utc)


def format_timestamp(value: datetime) -> str:
    """Format a datetime as RFC 3339 UTC with a trailing ``Z``.

    Fractional seconds are always six digits so lexicographic order matches
    chronological order.
    """
    instant = value.astimezone(timezone.utc)
    return instant.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_timestamp(value: str) -> datetime:
    """Parse a Runtime timestamp. Raises ValueError when the form is invalid."""
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        raise ValueError("timestamp must be RFC 3339 UTC ending in Z")
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def require_uuid(value: Any, *, field: str = "id") -> str:
    """Return ``value`` when it is an RFC 9562 UUID string."""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a UUID string")
    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be a UUID") from exc
    return value


def new_uuid() -> str:
    """Return a new UUID4 string."""
    return str(uuid.uuid4())


def require_did(value: Any) -> str:
    """Return ``value`` when it is a ``did:key`` identifier."""
    if not isinstance(value, str) or _DID_KEY.fullmatch(value) is None:
        raise ValueError("agent_did must be a did:key identifier")
    return value


def _normalize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if value.is_integer() and abs(value) < 2**53:
            return int(value)
        return value
    return value


def canonical_json(value: Any) -> str:
    """Return a stable JSON encoding for idempotency comparison.

    Object keys are sorted. Numbers that are equal in value (``1``, ``1.0``,
    ``1e0``) normalize to the same integer when they fit in IEEE-754 binary64
    as whole numbers. Array order is kept. Missing optional fields stay
    missing.
    """
    return json.dumps(
        _normalize_json(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def semantic_hash(value: Any) -> str:
    """SHA-256 of :func:`canonical_json` for cheap idempotency lookup."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def json_size(value: Any) -> int:
    """UTF-8 byte length of JSON encoding, used for payload limits."""
    return len(
        json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
