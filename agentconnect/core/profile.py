"""Discovery Profile and Skill.

A Profile describes what an Agent can do. Identity, name, and Address
(the Agent's `name` or `name@team` locator) live on `DirectoryEntry`,
not here.
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator, model_validator

from agentconnect.core.base import SchemaModel
from agentconnect.core.primitives import SkillExample, Tag

__all__ = ["Skill", "AgentProfile"]


class Skill(SchemaModel):
    """One thing an Agent claims it can do, described in natural language.

    A Skill has no input or output schema. Callers send free-form content
    to the Agent; they do not invoke a typed signature.

    Attributes:
        name: Stable lowercase identifier, unique within the Profile. Not
            an Address or a Runtime operation name.
        description: What the Skill does.
        examples: Short natural-language illustrations, at most 10.
        tags: Lowercase labels for this Skill. They appear only on the
            full Profile, not on the light Directory card.

    Examples:
        ```python
        from agentconnect.core.profile import Skill

        Skill(
            name="drafting",
            description="Turn notes into a short draft.",
            examples=["Draft two paragraphs from these bullets."],
        )
        ```
    """

    name: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9_-]{0,61}[a-z0-9])?$")
    description: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    examples: Optional[list[SkillExample]] = Field(default=None, max_length=10)
    tags: Optional[list[Tag]] = Field(default=None, max_length=20)

    @field_validator("tags")
    @classmethod
    def unique_skill_tags(cls, value: list[str] | None) -> list[str] | None:
        """Reject a repeated tag on one Skill. Skill tags are full-Profile only."""
        if value is not None and len(value) != len(set(value)):
            raise ValueError("tags must not repeat a value")
        return value


class AgentProfile(SchemaModel):
    """Discovery information for an Agent.

    `summary` is the cheap Directory card line. `description` is the
    longer explanation on the full Profile. Profile `tags` appear on
    the light card; Skill `tags` appear only on the full Profile.

    Identity, name, Address, presence, and Session data do not belong here.

    Attributes:
        summary: Short line shown on a ranked Directory match.
        skills: One to 50 Skills. Names must be unique in this list.
        description: Longer explanation of suitable work and boundaries.
            Present on the full Profile, not on the light `find` card.
        tags: Lowercase labels for the Agent as a whole. Duplicate tags
            are invalid.

    Examples:
        ```python
        from agentconnect.core.profile import AgentProfile, Skill

        AgentProfile(
            summary="Writes short drafts from notes.",
            skills=[
                Skill(
                    name="drafting",
                    description="Turn notes into a short draft.",
                )
            ],
            description="Hire for first drafts, not final copy-edits.",
            tags=["writing"],
        )
        ```
    """

    summary: str = Field(min_length=1, max_length=200, pattern=r"\S")
    skills: list[Skill] = Field(min_length=1, max_length=50)
    description: Optional[str] = Field(
        default=None, min_length=1, max_length=2000, pattern=r"\S"
    )
    tags: Optional[list[Tag]] = Field(default=None, max_length=20)

    @field_validator("tags")
    @classmethod
    def unique_profile_tags(cls, value: list[str] | None) -> list[str] | None:
        """Reject a repeated Profile tag."""
        if value is not None and len(value) != len(set(value)):
            raise ValueError("tags must not repeat a value")
        return value

    @model_validator(mode="after")
    def unique_skill_names(self) -> "AgentProfile":
        """Reject a Profile that repeats a Skill name."""
        names = [skill.name for skill in self.skills]
        if len(names) != len(set(names)):
            raise ValueError("skill names must be unique within the Profile")
        return self
