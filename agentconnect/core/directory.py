"""Discovery matches and full teammate Profiles."""

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
    "ProfileFound",
    "ProfileMiss",
    "ProfileItem",
    "GetProfilesResult",
    "FindRequest",
    "FindResult",
    "GetProfilesRequest",
    "MAX_GET_PROFILES",
]

MAX_GET_PROFILES = 20


class DirectoryEntry(SchemaModel):
    """Full Profile and identity for one Team Membership.

    `BaseAgent.get_entry` returns this record. The DID identifies the agent;
    the Profile describes suitable work. Model-facing `get_profiles` returns
    per-Address Profile items instead.
    """

    address: QualifiedAddress
    agent_did: AgentDid
    profile: AgentProfile


class DirectoryMatch(SchemaModel):
    """A candidate returned by discovery, in ranked order.

    The card includes a summary, Skill names and Profile tags. Read the full
    Profile when you need its boundaries or Skill descriptions before choosing.
    """

    address: QualifiedAddress
    summary: str
    skill_names: list[str]
    tags: Optional[list[Tag]] = None


class ProfileFound(SchemaModel):
    """Full Profile for a successfully resolved Address."""

    status: Literal["ok"]
    address: QualifiedAddress
    profile: AgentProfile


class ProfileMiss(SchemaModel):
    """Failure to read one requested Address.

    Other items in the same batch can succeed. Handle this item's `error`
    without discarding those Profiles.
    """

    status: Literal["error"]
    address: Address
    error: ErrorObject


ProfileItem = Annotated[
    Union[ProfileFound, ProfileMiss],
    Field(discriminator="status"),
]


class GetProfilesResult(SchemaModel):
    """Batch Profile results in requested order, with duplicate strings read once.

    Branch on each item's `status` before reading `profile` or `error`.
    """

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
    """Candidate matches, best first.

    An empty list means no candidates were returned. Ranking does not prove
    suitability; read a selected teammate's full Profile before assigning work.
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
