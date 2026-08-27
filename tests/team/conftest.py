"""Shared Team Runtime test helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
import pytest_asyncio

from agentconnect.team import Team

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def make_did(label: str) -> str:
    """Return a valid-looking did:key unique to ``label``."""
    mapped = "".join(_B58[ord(ch) % len(_B58)] for ch in label)
    body = (mapped + ("1" * 48))[:48]
    return "did:key:z" + body


def profile(
    summary: str = "Writes short drafts from notes.",
    skill: str = "drafting",
    description: str = "Turn notes into a two-paragraph draft.",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "summary": summary,
        "skills": [{"name": skill, "description": description}],
    }
    if tags is not None:
        data["tags"] = tags
    return data


def deadline(seconds: float = 30) -> str:
    instant = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return instant.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def join_member(team: Team, name: str, **kwargs: Any) -> dict[str, Any]:
    return await team.join(
        name=name,
        agent_did=kwargs.get("agent_did") or make_did(name),
        profile=kwargs.get("profile") or profile(),
        instance_id=kwargs.get("instance_id"),
        max_in_flight=kwargs.get("max_in_flight", 1),
    )


@pytest_asyncio.fixture(loop_scope="function")
async def team():
    runtime = Team(
        "content-squad",
        lease_ttl_seconds=0.4,
        session_ttl_seconds=30,
        sweep_interval_seconds=0.05,
        terminal_ticket_retention_seconds=2,
        thread_message_limit=50,
    )
    await runtime.start()
    try:
        yield runtime
    finally:
        await runtime.stop()
