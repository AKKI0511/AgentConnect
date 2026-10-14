"""Address grammar and same-Team resolution.

An Address is an Agent name, optionally qualified by a location, such as
`writer` or `writer@content-squad`. A qualified Address resolves only
when its location equals the Runtime's Team name. Invalid syntax is
`invalid_address`. A valid location that is not this Team is
`address_outside_team`.
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
    """Canonical Agent name and optional location after parse.

    Attributes:
        name: Lowercase Agent name.
        location: Lowercase location when the input was qualified, else omitted.
    """

    name: str
    location: Optional[str] = None


def parse_agent_name(value: str) -> Optional[str]:
    """Return the canonical Agent name, or None when the grammar fails.

    Length is 1 to 63 ASCII characters. The name must start and end
    alphanumeric; `-` and `_` may appear in the middle. ASCII uppercase
    is lowercased.

    Args:
        value: Submitted Agent name.

    Returns:
        Lowercase name, or None when the grammar fails.
    """
    if not value or not value.isascii() or _AGENT_NAME.fullmatch(value) is None:
        return None
    return value.lower()


def parse_team_name(value: str) -> Optional[str]:
    """Return the canonical Team name, or None when the grammar fails.

    A Team name is a DNS label: 1 to 63 ASCII characters, alphanumeric
    at each end, `-` allowed in the middle. Underscores are invalid.
    ASCII uppercase is lowercased.

    Args:
        value: Submitted Team name.

    Returns:
        Lowercase Team name, or None when the grammar fails.
    """
    if not value or not value.isascii() or _DNS_LABEL.fullmatch(value) is None:
        return None
    return value.lower()


def parse_location(value: str) -> Optional[str]:
    """Return a canonical location, or None when the grammar fails.

    A location is one or more dot-separated DNS labels, at most 253
    characters, with no trailing dot. ASCII uppercase is lowercased.

    Args:
        value: Location part of a qualified Address, without `@`.

    Returns:
        Lowercase location, or None when the grammar fails.
    """
    if not value or not value.isascii() or value.endswith(".") or len(value) > 253:
        return None
    labels = value.split(".")
    if any(_DNS_LABEL.fullmatch(label) is None for label in labels):
        return None
    return ".".join(label.lower() for label in labels)


def parse_address(value: str) -> Union[ParsedAddress, Literal["invalid_address"]]:
    """Parse an Address string into a name and optional location.

    Input may contain uppercase ASCII letters. Non-ASCII input is invalid.

    Args:
        value: Unqualified name such as `writer`, or `writer@content-squad`.

    Returns:
        A `ParsedAddress`, or `invalid_address` when the grammar fails.

    Examples:
        ```python
        from agentconnect.core.address import parse_address

        parse_address("Writer")
        parse_address("writer@content-squad")
        ```
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
    """Resolve an Address against one Team.

    An unqualified name becomes `name@team_name`. A qualified Address whose
    location equals `team_name` is returned in canonical form. Any other
    valid location is `address_outside_team`.

    Args:
        value: Local name or qualified Address.
        team_name: Canonical Team this Runtime serves.

    Returns:
        Canonical `name@team`, `invalid_address`, or `address_outside_team`.

    Raises:
        ValueError: `team_name` is not a valid Team name.

    Examples:
        ```python
        from agentconnect.core.address import resolve_address

        resolve_address("writer", "content-squad")
        resolve_address("writer@legal.example.com", "content-squad")
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
