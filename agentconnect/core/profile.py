"""Profiles and Skills that help agents choose a teammate."""

from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator, model_validator

from agentconnect.core.base import SchemaModel
from agentconnect.core.primitives import SkillExample, Tag

__all__ = ["Skill", "AgentProfile"]


class Skill(SchemaModel):
    """One kind of work an agent claims it can do.

    Describe suitable inputs and the help a caller can expect. A Skill describes
    free-form work; it does not define a callable input or output schema.

    Attributes:
        name: Stable identifier, unique within the Profile; not an Address.
        examples: Natural-language illustrations of suitable requests.
        tags: Labels visible on the full Profile, rather than the discovery card.
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
    """Discovery information other agents use to choose work for this agent.

    The summary, Skill names and Profile tags appear on discovery matches.
    The full Profile adds the description, Skill descriptions and examples.
    Identity and Address belong to the Directory entry.

    Attributes:
        skills: Names must be unique within this Profile.
        description: Suitable work and boundaries to consider before asking for help.
        tags: Labels for the agent as a whole; repeated labels are invalid.

    Examples:
        Describe a writer who can turn research into a release note:

        ```python
        from agentconnect.core.profile import AgentProfile, Skill

        profile = AgentProfile(
            summary="Writes release notes from engineering findings.",
            skills=[
                Skill(
                    name="release-notes",
                    description="Turn changes and user impact into a release note.",
                    examples=["Explain the faster search and who benefits from it."],
                )
            ],
            description="Provide the findings and intended audience. Does not verify claims.",
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
