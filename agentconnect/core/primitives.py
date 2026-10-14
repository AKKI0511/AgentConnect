"""Wire primitive aliases and closed unions.

These strings, ids, and enumerations appear on Messages, Tickets,
Addresses, and operation bodies. An Address is an Agent name, optionally
qualified as `name@team`. A DID is the Agent's `did:key` identity. A
Ticket is the requester's durable record for one request; `TicketState`
is its closed set of states.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal, get_args

from pydantic import AfterValidator, Field

from agentconnect.core.spec import SPEC_VERSION

SpecVersion = Literal["1.0.0-draft"]
"""Exact public contract version a Client and Runtime must share."""
assert SPEC_VERSION == "1.0.0-draft"

Timestamp = Annotated[
    str,
    Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"),
]
"""UTC RFC 3339 timestamp with a trailing `Z`, such as `2026-08-18T15:00:00Z`."""
Uuid = Annotated[
    str,
    Field(
        pattern=(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        )
    ),
]
"""RFC 9562 UUID used for Messages, Threads, leases, traces, and Instances."""
AgentName = Annotated[
    str,
    Field(pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9])?$"),
]
"""Agent name input, 1 to 63 characters. ASCII uppercase is canonicalized to lowercase."""
TeamName = Annotated[
    str,
    Field(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"),
]
"""Lowercase Team name and valid DNS label, 1 to 63 characters. Underscores are not allowed."""

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


class _AddressJsonSchema:
    """JSON Schema for Address. pydantic-core cannot compile the lookahead."""

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: Any, handler: Any
    ) -> dict[str, Any]:
        """Attach maxLength and the Address pattern without a pydantic regex."""
        schema = handler(core_schema)
        schema["type"] = "string"
        schema["maxLength"] = 317
        schema["pattern"] = _ADDRESS.pattern
        return schema


class _QualifiedAddressJsonSchema:
    """JSON Schema for QualifiedAddress. pydantic-core cannot compile the lookahead."""

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: Any, handler: Any
    ) -> dict[str, Any]:
        """Attach maxLength and the QualifiedAddress pattern without a pydantic regex."""
        schema = handler(core_schema)
        schema["type"] = "string"
        schema["maxLength"] = 317
        schema["pattern"] = _QUALIFIED_ADDRESS.pattern
        return schema


Address = Annotated[str, AfterValidator(_check_address), _AddressJsonSchema()]
"""Agent name, optionally qualified by location, such as `writer` or `writer@content-squad`."""
QualifiedAddress = Annotated[
    str, AfterValidator(_check_qualified_address), _QualifiedAddressJsonSchema()
]
"""Canonical stored Address. Both parts are lowercase and the location is always present."""
AgentDid = Annotated[str, Field(pattern=r"^did:key:z[1-9A-HJ-NP-Za-km-z]+$")]
"""Agent-owned `did:key` identity backed by an Ed25519 public key."""
SessionToken = Annotated[str, Field(min_length=1)]
"""Opaque non-empty bearer credential returned by join."""
Tag = Annotated[
    str,
    Field(pattern=r"^[a-z0-9](?:[a-z0-9_-]{0,30}[a-z0-9])?$"),
]
"""Lowercase discovery label on a Profile or Skill."""
SkillExample = Annotated[str, Field(min_length=1, max_length=500, pattern=r"\S")]
"""Short natural-language example of using a Skill. Not a typed contract."""

PersistenceMode = Literal["volatile", "durable"]
"""How a Runtime survives process exit. `durable` recovers retained store data after a Runtime restart."""
CollectMode = Literal["wait", "ticket"]
"""How the sender collects a request result on `send`. Not stored on the Message."""
MembershipKind = Literal["agent", "principal"]
"""Membership kind reported by `status`."""
TicketState = Literal["open", "completed", "failed", "expired", "declined"]
"""Closed set of Ticket states. Read completion from `state`, not from missing content."""
ErrorCode = Literal[
    "unsupported_version",
    "unauthorized",
    "forbidden",
    "invalid_request",
    "invalid_address",
    "address_outside_team",
    "not_found",
    "name_conflict",
    "id_conflict",
    "busy",
    "wait_limit",
    "payload_too_large",
    "lease_expired",
    "ticket_closed",
    "unavailable",
    "internal",
    "handler_failed",
    "deadline_exceeded",
]
"""Well-known public error codes. An Agent application code belongs in `ErrorObject.details`."""
DeliveryHistoryForm = Literal["bodies", "ids"]
"""How a Session wants Thread history on each Delivery: Message bodies, or ids only."""
TraceEventType = Literal[
    "accepted",
    "ticket_opened",
    "leased",
    "completed",
    "replied",
    "ticket_closed",
]
"""Closed set of Trace timeline event types returned by `get_trace`."""
ReplyOutcome = Literal["completed", "failed"]
"""Outcome of Runtime `reply`. `completed` stores a response; `failed` stores an error."""
SendStatus = Literal["accepted", "ticketed"]
"""Discriminator on a send result. Events are `accepted`; requests are `ticketed`."""
ERROR_CODES: tuple[str, ...] = get_args(ErrorCode)
"""Tuple of every `ErrorCode` value."""
COLLECT_MODES: tuple[str, ...] = get_args(CollectMode)
"""Tuple of every `CollectMode` value."""
MEMBERSHIP_KINDS: tuple[str, ...] = get_args(MembershipKind)
"""Tuple of every `MembershipKind` value."""
