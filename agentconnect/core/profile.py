"""Discovery Profile, Skill, and Directory result types.

A Profile describes what an Agent claims it can do. Identity, name, Address,
and routing data belong to the Membership and Directory entry, not the Profile.

The Runtime accepts a discovery mapping on ``join``::

    profile = {
        "summary": "Writes short drafts from notes.",
        "skills": [
            {
                "name": "drafting",
                "description": "Turn research notes into a two-paragraph draft.",
            }
        ],
    }

``Capability`` remains for older helper registration objects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Required, TypedDict

from pydantic import BaseModel, Field

from agentconnect.core.types import AgentType

_SKILL_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,61}[a-z0-9])?$")
_TAG = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,30}[a-z0-9])?$")


@dataclass
class Capability:
    """Named capability used by the current directory implementation."""

    name: str
    description: str
    input_schema: Optional[Dict[str, str]] = None
    output_schema: Optional[Dict[str, str]] = None
    version: str = "1.0"


class Skill(BaseModel):
    """One thing an Agent claims it can do, described in natural language.

    A Skill has no input or output schema. Callers send free-form content
    to the Agent; they do not invoke a typed signature.
    """

    name: str
    description: Optional[str] = None
    examples: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class AgentProfile(BaseModel):
    """Discovery profile for an Agent.

    The current object still carries registration fields the directory uses
    (``agent_id``, ``agent_type``, ``capabilities``). Discovery-only fields are
    ``summary``, ``skills``, ``description``, and ``tags``.
    """

    agent_id: str
    agent_type: AgentType
    name: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    documentation_url: Optional[str] = None
    organization: Optional[str] = None
    developer: Optional[str] = None
    url: Optional[str] = None
    auth_schemes: List[str] = []
    default_input_modes: List[str] = []
    default_output_modes: List[str] = []
    capabilities: List[Capability] = []
    skills: List[Skill] = []
    examples: List[str] = []
    tags: List[str] = []
    payment_address: Optional[str] = None
    custom_metadata: Dict[str, Any] = {}
    reputation_score: Optional[float] = Field(None, exclude=True)


def _require_text(
    value: Any, *, field: str, max_len: int, required: bool
) -> Optional[str]:
    """Return a stripped string, or None when an optional field is omitted."""
    if value is None:
        if required:
            raise ValueError(f"{field} is required")
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    if value.strip() == "":
        raise ValueError(f"{field} must contain a non-whitespace character")
    if len(value) > max_len:
        raise ValueError(f"{field} must be at most {max_len} characters")
    return value


def _validate_tags(tags: Any, *, field: str) -> Optional[list[str]]:
    if tags is None:
        return None
    if not isinstance(tags, list):
        raise ValueError(f"{field} must be an array")
    if len(tags) > 20:
        raise ValueError(f"{field} must have at most 20 entries")
    seen: set[str] = set()
    out: list[str] = []
    for tag in tags:
        if not isinstance(tag, str) or _TAG.fullmatch(tag) is None:
            raise ValueError(f"{field} contains an invalid tag")
        if tag in seen:
            raise ValueError(f"{field} must not repeat a tag")
        seen.add(tag)
        out.append(tag)
    return out


def validate_discovery_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a discovery Profile and return a canonical dict.

    Shape rules match the public AgentConnect Profile: a required summary,
    one or more Skills, and optional description and tags. The Runtime
    validates shape only; it does not certify that an Agent performs a
    Skill well.
    """
    if not isinstance(profile, Mapping):
        raise ValueError("profile must be an object")

    summary = _require_text(
        profile.get("summary"), field="summary", max_len=200, required=True
    )
    description = _require_text(
        profile.get("description"), field="description", max_len=2000, required=False
    )

    skills = profile.get("skills")
    if not isinstance(skills, list) or len(skills) < 1:
        raise ValueError("skills must contain at least one entry")
    if len(skills) > 50:
        raise ValueError("skills must have at most 50 entries")

    seen_names: set[str] = set()
    canonical_skills: list[dict[str, Any]] = []
    for skill in skills:
        if not isinstance(skill, Mapping):
            raise ValueError("each skill must be an object")
        name = skill.get("name")
        if not isinstance(name, str) or _SKILL_NAME.fullmatch(name) is None:
            raise ValueError("skill name is invalid")
        if name in seen_names:
            raise ValueError("skill names must be unique within the Profile")
        seen_names.add(name)
        desc = _require_text(
            skill.get("description"),
            field="skill description",
            max_len=1000,
            required=True,
        )
        entry: dict[str, Any] = {"name": name, "description": desc}
        examples = skill.get("examples")
        if examples is not None:
            if not isinstance(examples, list) or len(examples) > 10:
                raise ValueError("a skill may have at most 10 examples")
            canonical_examples: list[str] = []
            for example in examples:
                if not isinstance(example, str) or example.strip() == "":
                    raise ValueError("skill examples must be non-empty strings")
                if len(example) > 500:
                    raise ValueError("a skill example must be at most 500 characters")
                canonical_examples.append(example)
            entry["examples"] = canonical_examples
        skill_tags = _validate_tags(skill.get("tags"), field="skill tags")
        if skill_tags is not None:
            entry["tags"] = skill_tags
        canonical_skills.append(entry)

    out: dict[str, Any] = {"summary": summary, "skills": canonical_skills}
    if description is not None:
        out["description"] = description
    tags = _validate_tags(profile.get("tags"), field="tags")
    if tags is not None:
        out["tags"] = tags
    extra = set(profile.keys()) - {"summary", "description", "skills", "tags"}
    if extra:
        raise ValueError("profile contains unsupported fields")
    return out


class SkillClaim(TypedDict, total=False):
    """One Skill in a discovery Profile mapping passed to ``join``."""

    name: Required[str]
    description: Required[str]
    examples: list[str]
    tags: list[str]


class DiscoveryProfile(TypedDict, total=False):
    """Discovery mapping accepted by ``Team.join`` and ``BaseAgent(profile=...)``."""

    summary: Required[str]
    skills: Required[list[SkillClaim]]
    description: str
    tags: list[str]


class DirectoryEntry(TypedDict):
    """Full Directory record for one Membership, returned by ``get_profile``."""

    address: str
    agent_did: str
    profile: dict[str, Any]


class DirectoryMatch(TypedDict, total=False):
    """One ranked ``find`` result. Light by default; ``detail='full'`` fills the rest."""

    address: Required[str]
    summary: Required[str]
    skill_names: Required[list[str]]
    tags: list[str]
    agent_did: str
    profile: dict[str, Any]


class FindResult(TypedDict):
    """Ordered local Directory search result."""

    matches: list[DirectoryMatch]
