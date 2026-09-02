"""Public primitive aliases and closed unions from the specification schema."""

from __future__ import annotations

import re
from typing import Annotated, Literal, get_args

from pydantic import AfterValidator, Field

from agentconnect.core.spec import SPEC_VERSION

SpecVersion = Literal["1.0.0-draft"]
assert SPEC_VERSION == "1.0.0-draft"

Timestamp = Annotated[
    str,
    Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"),
]
Uuid = Annotated[
    str,
    Field(
        pattern=(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        )
    ),
]
AgentName = Annotated[
    str,
    Field(pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9])?$"),
]
TeamName = Annotated[
    str,
    Field(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"),
]

_ADDRESS = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9])?"
    r"(?:@(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*)?$"
)
_QUALIFIED_ADDRESS = re.compile(
    r"^[a-z0-9](?:[a-z0-9_-]{0,61}[a-z0-9])?@"
    r"(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$"
)


def _check_address(value: str) -> str:
    """Reject a value that is not a public Address."""
    if len(value) > 317 or _ADDRESS.fullmatch(value) is None:
        raise ValueError("not a valid Address")
    return value


def _check_qualified_address(value: str) -> str:
    """Reject a value that is not a canonical qualified Address."""
    if len(value) > 317 or _QUALIFIED_ADDRESS.fullmatch(value) is None:
        raise ValueError("not a valid QualifiedAddress")
    return value


Address = Annotated[str, AfterValidator(_check_address)]
QualifiedAddress = Annotated[str, AfterValidator(_check_qualified_address)]
AgentDid = Annotated[str, Field(pattern=r"^did:key:z[1-9A-HJ-NP-Za-km-z]+$")]
SessionToken = Annotated[str, Field(min_length=1)]
Tag = Annotated[
    str,
    Field(pattern=r"^[a-z0-9](?:[a-z0-9_-]{0,30}[a-z0-9])?$"),
]
SkillExample = Annotated[str, Field(min_length=1, max_length=500, pattern=r"\S")]

PersistenceMode = Literal["volatile", "durable"]
CollectMode = Literal["wait", "ticket", "callback", "stream"]
TicketState = Literal["open", "completed", "failed", "expired", "declined"]
ErrorCode = Literal[
    "unsupported_version",
    "unsupported_collect_mode",
    "unauthorized",
    "forbidden",
    "invalid_request",
    "invalid_address",
    "address_outside_team",
    "not_found",
    "name_conflict",
    "id_conflict",
    "busy",
    "payload_too_large",
    "lease_expired",
    "ticket_closed",
    "unavailable",
    "internal",
    "handler_failed",
    "deadline_exceeded",
]
TraceEventType = Literal[
    "accepted",
    "ticket_opened",
    "leased",
    "completed",
    "replied",
    "ticket_closed",
]
FindDetail = Literal["summary", "full"]
ReplyOutcome = Literal["completed", "failed"]
SendStatus = Literal["accepted", "ticketed"]
ERROR_CODES: tuple[str, ...] = get_args(ErrorCode)
COLLECT_MODES: tuple[str, ...] = get_args(CollectMode)
