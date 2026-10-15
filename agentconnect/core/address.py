"""Parse Agent names and resolve Addresses within one Team.

Names are case-insensitive ASCII. Qualified Addresses resolve only when their
location matches this Team; this resolver does not route to other Teams.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional, Union

INVALID_ADDRESS: Literal["invalid_address"] = "invalid_address"
"""Returned when an Address string fails the grammar."""
ADDRESS_OUTSIDE_TEAM: Literal["address_outside_team"] = "address_outside_team"
"""Returned when a valid location is not this Team."""

AddressErrorCode = Literal["invalid_address", "address_outside_team"]
"""Error codes `resolve_address` returns instead of a canonical Address."""

# 1 to 63 characters; start and end alphanumeric; middle may include - and _.
_AGENT_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9])?$")
# DNS label: 1 to 63 characters; start and end alphanumeric; middle may include -.
_DNS_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


@dataclass(frozen=True)
class ParsedAddress:
    """Canonical Agent name and location parsed from an Address.

    Attributes:
        name: Lowercase name suitable for same-Team lookup.
        location: Lowercase location for qualified input; None for a local name.
    """

    name: str
    location: Optional[str] = None


def parse_agent_name(value: str) -> Optional[str]:
    """Return a lowercase Agent name, or None for invalid syntax.

    Accepts 1 to 63 ASCII characters with alphanumeric ends and `-` or `_` inside.
    """
    if not value or not value.isascii() or _AGENT_NAME.fullmatch(value) is None:
        return None
    return value.lower()


def parse_team_name(value: str) -> Optional[str]:
    """Return a lowercase Team name, or None for invalid syntax.

    Accepts a DNS label of 1 to 63 ASCII characters with alphanumeric ends and
    hyphens inside. Underscores are invalid.
    """
    if not value or not value.isascii() or _DNS_LABEL.fullmatch(value) is None:
        return None
    return value.lower()


def parse_location(value: str) -> Optional[str]:
    """Return a lowercase location, or None for invalid syntax.

    Accepts dot-separated DNS labels, at most 253 characters and no trailing dot.
    """
    if not value or not value.isascii() or value.endswith(".") or len(value) > 253:
        return None
    labels = value.split(".")
    if any(_DNS_LABEL.fullmatch(label) is None for label in labels):
        return None
    return ".".join(label.lower() for label in labels)


def parse_address(value: str) -> Union[ParsedAddress, Literal["invalid_address"]]:
    """Split a name or qualified Address, canonicalizing ASCII uppercase.

    Returns `invalid_address` for invalid syntax, including non-ASCII input.
    """
    if not isinstance(value, str) or not value or not value.isascii():
        return INVALID_ADDRESS
    if value.count("@") > 1:
        return INVALID_ADDRESS
    if "@" in value:
        name_part, location_part = value.split("@", 1)
        name = parse_agent_name(name_part)
        location = parse_location(location_part)
        if name is None or location is None:
            return INVALID_ADDRESS
        return ParsedAddress(name=name, location=location)
    name = parse_agent_name(value)
    if name is None:
        return INVALID_ADDRESS
    return ParsedAddress(name=name, location=None)


def resolve_address(value: str, team_name: str) -> Union[str, AddressErrorCode]:
    """Return a canonical qualified Address within the supplied Team.

    Local names gain the Team location. Invalid syntax returns `invalid_address`;
    a valid different location returns `address_outside_team`.

    Args:
        team_name: Team against which the input is resolved.

    Raises:
        ValueError: The Address parses but the Team name is invalid.

    Examples:
        ```python
        from agentconnect.core.address import resolve_address

        resolve_address("Writer", "content-squad")  # "writer@content-squad"
        resolve_address("writer@legal.example.com", "content-squad")
        # "address_outside_team"
        ```
    """
    parsed = parse_address(value)
    if not isinstance(parsed, ParsedAddress):
        return INVALID_ADDRESS
    canonical_team = parse_team_name(team_name)
    if canonical_team is None:
        raise ValueError("team_name is not a valid Team name")
    if parsed.location is None or parsed.location == canonical_team:
        return f"{parsed.name}@{canonical_team}"
    return ADDRESS_OUTSIDE_TEAM
