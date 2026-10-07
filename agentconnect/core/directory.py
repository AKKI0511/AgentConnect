"""Directory entry, ranked match, and find result types."""

from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import Field

from agentconnect.core.base import JsonInt, SchemaModel
from agentconnect.core.error import ErrorObject
from agentconnect.core.primitives import (
    Address,
    AgentDid,
    QualifiedAddress,
    Tag,
)
from agentconnect.core.profile import AgentProfile

__all__ = [
    "DirectoryEntry",
    "DirectoryMatch",
    "ProfileView",
    "ProfileFound",
    "ProfileMiss",
    "ProfileItem",
    "GetProfilesResult",
    "FindRequest",
    "FindResult",
    "GetProfilesRequest",
    "MAX_GET_PROFILES",
    "profile_view",
]

MAX_GET_PROFILES = 20


class DirectoryEntry(SchemaModel):
    """Full Directory record for one Membership.

    Runtime ``get_profile`` returns Address, DID, and Profile together.
    The Client method is :meth:`~agentconnect.agent.base.BaseAgent.get_entry`.
    Model-facing tools return :class:`GetProfilesResult` instead.

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

    Light on purpose: Address, ``summary``, Skill names, and Profile tags.
    Read selected Profiles with ``get_profiles``.
    """

    address: QualifiedAddress
    summary: str
    skill_names: list[str]
    tags: Optional[list[Tag]] = None


class ProfileView(SchemaModel):
    """Address and Profile without Directory DID bookkeeping."""

    address: QualifiedAddress
    profile: AgentProfile


class ProfileFound(SchemaModel):
    """Successful ``get_profiles`` item."""

    status: Literal["ok"]
    address: QualifiedAddress
    profile: AgentProfile


class ProfileMiss(SchemaModel):
    """Failed ``get_profiles`` item for one requested Address."""

    status: Literal["error"]
    address: Address
    error: ErrorObject


ProfileItem = Annotated[
    Union[ProfileFound, ProfileMiss],
    Field(discriminator="status"),
]


class GetProfilesResult(SchemaModel):
    """Model-facing ``get_profiles`` result."""

    items: list[ProfileItem]


class FindRequest(SchemaModel):
    """Find teammates by describing the work.

    Ranked matches are candidates, not proof of suitability. Overlapping
    Profiles need ``get_profiles``. Reuse cards already read. You may
    conclude nobody fits. Compact cards omit description; that text is
    on the full Profile.
    """

    query: str = Field(
        min_length=1,
        max_length=1000,
        pattern=r"\S",
        description=(
            "Natural-language description of the work. Ranked matches are "
            "candidates, not proof that someone is suitable."
        ),
    )
    limit: Optional[JsonInt] = Field(
        default=None,
        ge=1,
        le=100,
        description="Maximum matches from 1 to 100. Omit to receive every other member, at most 100.",
    )


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


class GetProfilesRequest(SchemaModel):
    """Read one or more teammate Profiles by Address."""

    addresses: list[Address] = Field(
        min_length=1,
        max_length=MAX_GET_PROFILES,
        description=(
            "Member Addresses to read, 1 to 20. Duplicate requested "
            "strings are read once, keeping the first."
        ),
    )

    def unique_requested(self) -> list[str]:
        """Return requested strings in order, dropping later duplicates."""
        seen: set[str] = set()
        ordered: list[str] = []
        for item in self.addresses:
            if item in seen:
                continue
            seen.add(item)
            ordered.append(item)
        return ordered


def profile_view(entry: DirectoryEntry) -> ProfileView:
    """Project a DirectoryEntry into the model-facing ProfileView."""
    return ProfileView(address=entry.address, profile=entry.profile)
