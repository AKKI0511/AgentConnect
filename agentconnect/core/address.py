"""Address grammar and same-Team resolution.

An Address is an Agent name, optionally qualified by a location. The current
draft resolves a qualified Address only when its location equals the Runtime's
Team name. Invalid syntax is ``invalid_address``. A valid location that is not
this Team is ``address_outside_team``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional, Union

INVALID_ADDRESS = "invalid_address"
ADDRESS_OUTSIDE_TEAM = "address_outside_team"

AddressErrorCode = Literal["invalid_address", "address_outside_team"]

# 1 to 63 characters; start and end alphanumeric; middle may include - and _.
_AGENT_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9])?$")
# DNS label: 1 to 63 characters; start and end alphanumeric; middle may include -.
_DNS_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


@dataclass(frozen=True)
class ParsedAddress:
    """Canonical Agent name and optional location after parse."""

    name: str
    location: Optional[str] = None


def parse_agent_name(value: str) -> Optional[str]:
    """Return the canonical Agent name, or None when the grammar fails."""
    if not value or not value.isascii() or _AGENT_NAME.fullmatch(value) is None:
        return None
    return value.lower()


def parse_team_name(value: str) -> Optional[str]:
    """Return the canonical Team name, or None when the grammar fails."""
    if not value or not value.isascii() or _DNS_LABEL.fullmatch(value) is None:
        return None
    return value.lower()


def parse_location(value: str) -> Optional[str]:
    """Return a canonical location, or None when the grammar fails."""
    if not value or not value.isascii() or value.endswith(".") or len(value) > 253:
        return None
    labels = value.split(".")
    if any(_DNS_LABEL.fullmatch(label) is None for label in labels):
        return None
    return ".".join(label.lower() for label in labels)


def parse_address(value: str) -> Union[ParsedAddress, Literal["invalid_address"]]:
    """Parse an Address string into a name and optional location.

    Input may contain uppercase ASCII letters. Non-ASCII input is invalid.
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

    An unqualified name becomes ``name@team_name``. A qualified Address whose
    location equals ``team_name`` is returned in canonical form. Any other
    valid location is ``address_outside_team``.
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
