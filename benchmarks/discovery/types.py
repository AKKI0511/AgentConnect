"""Shared builders and types for the discovery corpus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

Split = Literal["development", "held_out"]

# Every label below must appear on at least one need in each split.
REQUIRED_SLICE_LABELS: frozenset[str] = frozenset(
    {
        "refunds_vs_chargeback",
        "contract_substance_vs_formatting",
        "staging_vs_production",
        "translation_direction",
        "jurisdiction_or_dataset",
        "generalist_vs_specialist",
        "repeated_boilerplate",
        "negated_capability",
        "late_capability",
        "paraphrase",
        "multilingual",
        "broad_or_misleading",
        "no_suitable_member",
        "multiple_acceptable",
    }
)


def skill(
    name: str,
    description: str,
    *,
    examples: Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build a Skill dict using only real Skill fields."""
    out: dict[str, Any] = {"name": name, "description": description}
    if examples is not None:
        out["examples"] = list(examples)
    if tags is not None:
        out["tags"] = list(tags)
    return out


def profile(
    summary: str,
    skills: Sequence[Mapping[str, Any]],
    *,
    description: str | None = None,
    tags: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build an AgentProfile dict using only real Profile fields."""
    out: dict[str, Any] = {"summary": summary, "skills": list(skills)}
    if description is not None:
        out["description"] = description
    if tags is not None:
        out["tags"] = list(tags)
    return out


@dataclass(frozen=True)
class Roster:
    """One Team-sized specialist set with stable local Addresses."""

    id: str
    members: Mapping[str, Mapping[str, Any]]

    @property
    def size(self) -> int:
        return len(self.members)


@dataclass(frozen=True)
class Need:
    """One authored discovery need with an acceptable Address set."""

    id: str
    split: Split
    roster_id: str
    query: str
    acceptable: frozenset[str]
    task: str
    slices: frozenset[str]


@dataclass(frozen=True)
class Corpus:
    """Versioned discovery corpus loaded for structure checks and later scoring."""

    revision: str
    rosters: Mapping[str, Roster]
    needs: Sequence[Need]
