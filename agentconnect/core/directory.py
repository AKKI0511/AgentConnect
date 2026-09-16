"""Directory entry, ranked match, and find result types."""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from agentconnect.core.base import JsonInt, SchemaModel
from agentconnect.core.primitives import (
    Address,
    AgentDid,
    FindDetail,
    QualifiedAddress,
    Tag,
)
from agentconnect.core.profile import AgentProfile

__all__ = [
    "DirectoryEntry",
    "DirectoryMatch",
    "FindRequest",
    "FindResult",
    "GetProfileRequest",
]


class DirectoryEntry(SchemaModel):
    """Full Directory record for one Membership.

    Runtime ``get_profile`` returns Address, DID, and Profile together.
    The Client method is :meth:`~agentconnect.agent.base.BaseAgent.get_entry`.

    .. code-block:: python

        entry = await agent.get_entry("writer")
        entry.profile.summary
        entry.profile.description
    """

    address: QualifiedAddress
    agent_did: AgentDid
    profile: AgentProfile


class DirectoryMatch(SchemaModel):
    """One ranked discovery result.

    Light by default: Address, ``summary``, Skill names, and Profile tags.
    ``detail='full'`` adds ``agent_did`` and the complete Profile.
    """

    address: QualifiedAddress
    summary: str
    skill_names: list[str]
    tags: Optional[list[Tag]] = None
    agent_did: Optional[AgentDid] = None
    profile: Optional[AgentProfile] = None


class FindRequest(SchemaModel):
    """Local Directory search input."""

    query: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    limit: Optional[JsonInt] = Field(default=None, ge=1, le=100)
    detail: FindDetail = "summary"


class FindResult(SchemaModel):
    """Ordered local Directory search result.

    Matches are best-first. The result does not name the embedding
    backend or a fallback.

    .. code-block:: python

        found = await agent.find("someone who can draft a summary")
        found.matches[0].address
        found.matches[0].summary
    """

    matches: list[DirectoryMatch]


class GetProfileRequest(SchemaModel):
    """Directory lookup used by non-HTTP bindings."""

    address: Address
