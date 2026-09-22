"""Structure-only checks for the discovery corpus.

Validates authorship constraints. Does not call Team, Directory.search,
embedders, or BM25, and does not compute recall or any score.
"""

from __future__ import annotations

from typing import Any, Mapping

from agentconnect.core.profile import AgentProfile

from benchmarks.discovery.corpus import CORPUS_REVISION, load_corpus
from benchmarks.discovery.types import REQUIRED_SLICE_LABELS, Corpus, Need

# Profile / Skill keys allowed on corpus records (mirrors AgentProfile / Skill).
_PROFILE_KEYS = frozenset({"summary", "description", "skills", "tags"})
_SKILL_KEYS = frozenset({"name", "description", "examples", "tags"})


def assert_corpus_structure(corpus: Corpus | None = None) -> Corpus:
    """Assert corpus shape, splits, slices, and Profile field constraints.

    Returns the loaded corpus on success. Raises AssertionError on failure.
    """
    data = corpus if corpus is not None else load_corpus()
    assert data.revision == CORPUS_REVISION, (
        f"unexpected revision {data.revision!r}; expected {CORPUS_REVISION!r}"
    )
    assert len(data.rosters) >= 4, f"need at least 4 rosters, got {len(data.rosters)}"

    sizes = [roster.size for roster in data.rosters.values()]
    assert any(size <= 10 for size in sizes), (
        f"need a roster with at most 10 members for elbow tests; sizes={sizes}"
    )
    assert any(size > 20 for size in sizes), (
        f"need a roster with more than 20 members for elbow tests; sizes={sizes}"
    )

    for roster in data.rosters.values():
        assert roster.members, f"roster {roster.id!r} has no members"
        for address, profile in roster.members.items():
            assert address == address.lower(), (
                f"address {address!r} on {roster.id} must be lowercase"
            )
            _assert_profile_shape(roster.id, address, profile)

    needs = list(data.needs)
    ids = [need.id for need in needs]
    assert len(ids) == len(set(ids)), "need ids must be unique across the corpus"

    development = [need for need in needs if need.split == "development"]
    held_out = [need for need in needs if need.split == "held_out"]
    assert len(development) >= 40, (
        f"development needs must be >= 40, got {len(development)}"
    )
    assert len(held_out) >= 40, f"held-out needs must be >= 40, got {len(held_out)}"

    dev_ids = {need.id for need in development}
    held_ids = {need.id for need in held_out}
    assert dev_ids.isdisjoint(held_ids), "development and held-out need ids overlap"

    assert any(not need.acceptable for need in development), (
        "development split needs at least one empty acceptable set"
    )
    assert any(not need.acceptable for need in held_out), (
        "held-out split needs at least one empty acceptable set"
    )

    _assert_slices_present(development, "development")
    _assert_slices_present(held_out, "held_out")

    for need in needs:
        assert need.roster_id in data.rosters, (
            f"need {need.id!r} references unknown roster {need.roster_id!r}"
        )
        roster = data.rosters[need.roster_id]
        for address in need.acceptable:
            assert address in roster.members, (
                f"need {need.id!r} acceptable address {address!r} "
                f"missing from roster {roster.id!r}"
            )
        assert need.query.strip(), f"need {need.id!r} has empty query"
        assert need.task.strip(), f"need {need.id!r} has empty task"
        assert need.slices, f"need {need.id!r} has no slice labels"

    return data


def _assert_slices_present(needs: list[Need], split_name: str) -> None:
    present: set[str] = set()
    for need in needs:
        present.update(need.slices)
    missing = REQUIRED_SLICE_LABELS - present
    assert not missing, (
        f"{split_name} split missing required slice labels: {sorted(missing)}"
    )


def _assert_profile_shape(
    roster_id: str, address: str, profile: Mapping[str, Any]
) -> None:
    extra = set(profile) - _PROFILE_KEYS
    assert not extra, f"{roster_id}/{address} has non-Profile fields: {sorted(extra)}"
    for skill in profile.get("skills") or []:
        assert isinstance(skill, Mapping), (
            f"{roster_id}/{address} skill is not a mapping"
        )
        skill_extra = set(skill) - _SKILL_KEYS
        assert not skill_extra, (
            f"{roster_id}/{address} skill {skill.get('name')!r} has "
            f"non-Skill fields: {sorted(skill_extra)}"
        )
    # Validate against the real frozen model (structure only; no ranking).
    AgentProfile.model_validate(dict(profile))


def corpus_counts() -> dict[str, Any]:
    """Return split and slice counts for reporting (no scores)."""
    data = load_corpus()
    development = [need for need in data.needs if need.split == "development"]
    held_out = [need for need in data.needs if need.split == "held_out"]

    def _slice_counts(needs: list[Need]) -> dict[str, int]:
        counts: dict[str, int] = {label: 0 for label in sorted(REQUIRED_SLICE_LABELS)}
        for need in needs:
            for label in need.slices:
                if label in counts:
                    counts[label] += 1
        return counts

    return {
        "revision": data.revision,
        "roster_sizes": {rid: r.size for rid, r in data.rosters.items()},
        "development_needs": len(development),
        "held_out_needs": len(held_out),
        "development_slices": _slice_counts(development),
        "held_out_slices": _slice_counts(held_out),
        "empty_acceptable_development": sum(
            1 for need in development if not need.acceptable
        ),
        "empty_acceptable_held_out": sum(1 for need in held_out if not need.acceptable),
    }


if __name__ == "__main__":
    assert_corpus_structure()
    counts = corpus_counts()
    print(f"corpus revision: {counts['revision']}")
    print(f"roster sizes: {counts['roster_sizes']}")
    print(
        f"needs: development={counts['development_needs']} "
        f"held_out={counts['held_out_needs']}"
    )
    print(f"development slices: {counts['development_slices']}")
    print(f"held_out slices: {counts['held_out_slices']}")
    print(
        "empty acceptable: "
        f"development={counts['empty_acceptable_development']} "
        f"held_out={counts['empty_acceptable_held_out']}"
    )
    print("structure check passed; no ranking or retrieval was run")
