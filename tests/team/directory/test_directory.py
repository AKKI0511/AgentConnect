"""Directory ranking, default result size, and embedding backends."""

from __future__ import annotations

import time
from typing import Sequence

import pytest

from agentconnect.team import Team, TeamError
from agentconnect.team.directory import HashedEmbedder, profile_text, resolve_embedder
from tests.team.conftest import join_member, make_did, profile


def _legal():
    return profile(
        summary="Reviews contracts for risk and missing terms.",
        skill="contract_review",
        description="Read a contract and list risks and missing clauses.",
        tags=["legal", "contracts"],
    )


def _writer():
    return profile(
        summary="Writes short drafts from notes.",
        skill="drafting",
        description="Turn research notes into a two-paragraph draft.",
        tags=["writing"],
    )


@pytest.mark.asyncio
async def test_find_ranks_contract_reviewer_first(team: Team):
    await join_member(team, "writer", profile=_writer())
    await join_member(team, "reviewer", profile=_legal())
    caller = await join_member(team, "researcher")
    found = await team.find(
        caller["session_token"], "someone who can verify a contract"
    )
    addresses = [match["address"] for match in found["matches"]]
    assert addresses[0] == "reviewer@content-squad"
    assert "researcher@content-squad" not in addresses
    assert "writer@content-squad" in addresses


@pytest.mark.asyncio
async def test_find_omitted_limit_returns_every_other_member():
    runtime = Team("content-squad", embeddings="none")
    await runtime.start()
    try:
        for index in range(15):
            name = f"member{index:02d}"
            await join_member(
                runtime,
                name,
                agent_did=make_did(name),
                profile=profile(summary=f"Handles task {index}."),
            )
        caller = await join_member(
            runtime, "researcher", agent_did=make_did("researcher")
        )
        found = await runtime.find(caller["session_token"], "handle a task")
        assert len(found["matches"]) == 15
        assert all(
            match["address"] != "researcher@content-squad" for match in found["matches"]
        )
        limited = await runtime.find(caller["session_token"], "handle a task", limit=3)
        assert len(limited["matches"]) == 3
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_find_detail_full_includes_profile_and_did(team: Team):
    await join_member(team, "writer", profile=_writer())
    caller = await join_member(team, "researcher")
    found = await team.find(caller["session_token"], "draft notes", detail="full")
    match = found["matches"][0]
    assert match["agent_did"]
    assert match["profile"]["skills"][0]["name"] == "drafting"
    summary = await team.find(caller["session_token"], "draft notes")
    assert "agent_did" not in summary["matches"][0]
    assert "profile" not in summary["matches"][0]


@pytest.mark.asyncio
async def test_find_custom_embedder_orders_by_supplied_vectors():
    async def embed(texts: Sequence[str]) -> list[list[float]]:
        rows: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            legal = (
                1.0
                if any(word in lowered for word in ("contract", "legal", "clause"))
                else 0.0
            )
            writing = (
                1.0
                if any(word in lowered for word in ("draft", "writ", "notes"))
                else 0.0
            )
            rows.append([legal, writing, 0.1])
        return rows

    runtime = Team("content-squad", embeddings=embed)
    await runtime.start()
    try:
        await join_member(runtime, "writer", profile=_writer())
        await join_member(runtime, "reviewer", profile=_legal())
        caller = await join_member(runtime, "researcher")
        found = await runtime.find(
            caller["session_token"], "legal contract clause review"
        )
        assert found["matches"][0]["address"] == "reviewer@content-squad"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_find_reembeds_when_profile_changes():
    calls: list[str] = []

    async def embed(texts: Sequence[str]) -> list[list[float]]:
        rows: list[list[float]] = []
        for text in texts:
            calls.append(text)
            lowered = text.lower()
            rows.append(
                [1.0, 0.0]
                if "legal" in lowered or "contract" in lowered
                else [0.0, 1.0]
            )
        return rows

    runtime = Team("content-squad", embeddings=embed)
    await runtime.start()
    try:
        await join_member(runtime, "writer", profile=_writer())
        caller = await join_member(runtime, "researcher")
        first = await runtime.find(caller["session_token"], "legal contract")
        assert first["matches"][0]["address"] == "writer@content-squad"
        before = len(calls)
        await join_member(
            runtime,
            "writer",
            agent_did=make_did("writer"),
            profile=_legal(),
        )
        second = await runtime.find(caller["session_token"], "legal contract")
        assert second["matches"][0]["address"] == "writer@content-squad"
        assert len(calls) > before
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_find_includes_offline_members(team: Team):
    writer = await join_member(team, "writer", profile=_writer())
    caller = await join_member(team, "researcher")
    await team.disconnect(writer["session_token"])
    found = await team.find(caller["session_token"], "draft notes")
    assert found["matches"][0]["address"] == "writer@content-squad"


@pytest.mark.asyncio
async def test_find_rejects_blank_query(team: Team):
    caller = await join_member(team, "researcher")
    with pytest.raises(TeamError) as exc:
        await team.find(caller["session_token"], "   ")
    assert exc.value.code == "invalid_request"


@pytest.mark.asyncio
async def test_find_equal_scores_break_ties_by_address():
    async def embed(texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    runtime = Team("content-squad", embeddings=embed)
    await runtime.start()
    try:
        await join_member(runtime, "zeta", profile=_writer())
        await join_member(runtime, "alpha", profile=_writer())
        caller = await join_member(runtime, "researcher")
        found = await runtime.find(caller["session_token"], "anything")
        addresses = [match["address"] for match in found["matches"]]
        assert addresses == ["alpha@content-squad", "zeta@content-squad"]
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_find_ranks_one_hundred_members_quickly():
    runtime = Team("content-squad", embeddings="none")
    await runtime.start()
    try:
        for index in range(100):
            name = f"agent{index:03d}"
            kind = "contract" if index == 42 else "draft"
            await join_member(
                runtime,
                name,
                agent_did=make_did(name),
                profile=profile(
                    summary=f"{kind} specialist number {index}.",
                    skill="contract_review" if index == 42 else "drafting",
                    description=f"Work on {kind} tasks.",
                ),
            )
        caller = await join_member(
            runtime, "researcher", agent_did=make_did("researcher")
        )
        started = time.perf_counter()
        found = await runtime.find(
            caller["session_token"], "someone who can review a contract"
        )
        elapsed = time.perf_counter() - started
        assert elapsed < 0.25
        assert found["matches"][0]["address"] == "agent042@content-squad"
        assert len(found["matches"]) == 100
    finally:
        await runtime.stop()


def test_resolve_embedder_none_is_hashed():
    embedder = resolve_embedder("none")
    assert isinstance(embedder, HashedEmbedder)


def test_profile_text_includes_skills_and_examples():
    text = profile_text(
        {
            "summary": "Reviews contracts.",
            "skills": [
                {
                    "name": "contract_review",
                    "description": "List missing clauses.",
                    "examples": ["Check this MSA."],
                }
            ],
            "tags": ["legal"],
        }
    )
    assert "Reviews contracts." in text
    assert "contract_review" in text
    assert "Check this MSA." in text
    assert "legal" in text


@pytest.mark.asyncio
async def test_hashed_embedder_is_deterministic():
    embedder = HashedEmbedder()
    first = await embedder.embed(["Reviews contracts for missing terms."])
    second = await embedder.embed(["Reviews contracts for missing terms."])
    assert first == second
    assert len(first[0]) == 384
