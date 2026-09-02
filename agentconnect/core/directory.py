"""Directory entry, ranked match, and find result types."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from agentconnect.core.base import SchemaModel
from agentconnect.core.primitives import Address, AgentDid, QualifiedAddress, Tag
from agentconnect.core.profile import AgentProfile

__all__ = [
    "DirectoryEntry",
    "DirectoryMatch",
    "FindRequest",
    "FindResult",
    "GetProfileRequest",
]


class DirectoryEntry(SchemaModel):
    """Full Directory record for one Membership, returned by ``get_profile``."""

    address: QualifiedAddress
    agent_did: AgentDid
    profile: AgentProfile


class DirectoryMatch(SchemaModel):
    """One ranked discovery result. Light by default; ``detail='full'`` fills the rest."""

    address: QualifiedAddress
    summary: str
    skill_names: list[str]
    tags: Optional[list[Tag]] = None
    agent_did: Optional[AgentDid] = None
    profile: Optional[AgentProfile] = None


class FindRequest(SchemaModel):
    """Local Directory search input."""

    query: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    limit: Optional[int] = Field(default=None, ge=1, le=100)
    detail: Literal["summary", "full"] = "summary"


class FindResult(SchemaModel):
    """Ordered local Directory search result."""

    matches: list[DirectoryMatch]


class GetProfileRequest(SchemaModel):
    """Directory lookup used by non-HTTP bindings."""

    address: Address
