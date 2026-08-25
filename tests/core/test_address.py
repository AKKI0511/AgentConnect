"""Address grammar and same-Team resolution vectors."""

import pytest

from agentconnect.core.address import (
    ADDRESS_OUTSIDE_TEAM,
    INVALID_ADDRESS,
    ParsedAddress,
    parse_address,
    resolve_address,
)

TEAM = "content-squad"


@pytest.mark.parametrize(
    ("value", "name", "location"),
    [
        ("writer", "writer", None),
        ("Researcher", "researcher", None),
        ("writer@content-squad", "writer", "content-squad"),
        ("Writer@Content-Squad", "writer", "content-squad"),
        ("writer@legal.example.com", "writer", "legal.example.com"),
        ("researcher", "researcher", None),
        ("code_reviewer", "code_reviewer", None),
        ("agent-2", "agent-2", None),
        ("a", "a", None),
        ("ab", "ab", None),
        ("a_b", "a_b", None),
        ("writer@legal.acme.com", "writer", "legal.acme.com"),
    ],
)
def test_parse_address_valid(value: str, name: str, location: str | None) -> None:
    parsed = parse_address(value)
    assert parsed == ParsedAddress(name=name, location=location)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "@content-squad",
        "writer@",
        "writer@team@host",
        "writer/content-squad",
        "_writer",
        "writer-",
        "a..b",
        "writer@content-squad.",
        "writer@content_squad",
        "writer@.team",
        "writer@team..host",
        "-writer",
        "writer_",
        "wrïter",
        "writer@contént-squad",
        "a" * 64,
        "writer@" + ("a" * 254),
        "writer@content-squad/extra",
        " ",
        "writer content-squad",
    ],
)
def test_parse_address_invalid(value: str) -> None:
    assert parse_address(value) == INVALID_ADDRESS


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("writer", "writer@content-squad"),
        ("Researcher", "researcher@content-squad"),
        ("writer@content-squad", "writer@content-squad"),
        ("Writer@Content-Squad", "writer@content-squad"),
        ("researcher", "researcher@content-squad"),
    ],
)
def test_resolve_same_team(value: str, expected: str) -> None:
    assert resolve_address(value, TEAM) == expected


def test_resolve_outside_team() -> None:
    assert resolve_address("writer@legal.example.com", TEAM) == ADDRESS_OUTSIDE_TEAM
    assert (
        resolve_address("writer@content-squad.example.com", TEAM)
        == ADDRESS_OUTSIDE_TEAM
    )


@pytest.mark.parametrize(
    "value",
    [
        "@content-squad",
        "writer@",
        "writer@team@host",
        "writer/content-squad",
        "",
        "_writer",
        "writer@content-squad.",
    ],
)
def test_resolve_invalid_address(value: str) -> None:
    assert resolve_address(value, TEAM) == INVALID_ADDRESS


def test_resolve_rejects_invalid_team_name() -> None:
    with pytest.raises(ValueError):
        resolve_address("writer", "content_squad")


def test_sixty_three_character_agent_name_is_valid() -> None:
    name = "a" * 63
    parsed = parse_address(name)
    assert parsed == ParsedAddress(name=name, location=None)
