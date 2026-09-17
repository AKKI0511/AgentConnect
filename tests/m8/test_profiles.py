"""Benchmark Profiles must satisfy the public Profile schema."""

from __future__ import annotations

from agentconnect.core.profile import AgentProfile
from tests.m8.support import heavy_profile, short_profile, specialist_profile


def test_short_specialist_and_heavy_profiles_validate():
    AgentProfile.model_validate(short_profile(0))
    AgentProfile.model_validate(specialist_profile())
    for label in ("task00", "clause-review", "x"):
        parsed = AgentProfile.model_validate(heavy_profile(label))
        assert parsed.description is not None
        assert len(parsed.description) <= 2000
        assert all(len(skill.description) <= 1000 for skill in parsed.skills)
        assert len(parsed.summary) <= 200
