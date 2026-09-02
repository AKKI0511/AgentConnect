"""Discovery Profile and Skill. Identity and addressing live on DirectoryEntry."""

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
    """

    name: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9_-]{0,61}[a-z0-9])?$")
    description: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    examples: Optional[list[SkillExample]] = Field(default=None, max_length=10)
    tags: Optional[list[Tag]] = Field(default=None, max_length=20)

    @field_validator("tags")
    @classmethod
    def unique_skill_tags(cls, value: list[str] | None) -> list[str] | None:
        """Reject a repeated tag on one Skill."""
        if value is not None and len(value) != len(set(value)):
            raise ValueError("tags must not repeat a value")
        return value


class AgentProfile(SchemaModel):
    """Discovery information for an Agent.

    A Profile describes what one participant can do. Identity, name,
    Address, presence, and Session data do not belong here.
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
