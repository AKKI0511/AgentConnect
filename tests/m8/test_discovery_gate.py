"""Hashed discovery behavior on the supported single-Runtime sizes.

Warm-find p95 budgets are enforced by ``tests/m8/bench.py``, not the
default pytest suite.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Sequence

import pytest
from tests.m8.budgets import (
    SEND_DURING_FIND_P95_S,
    WARM_RANK_MEMBERS,
    find_p95_budget_s,
    percentile,
)
from tests.m8.stores import CountingStore, YieldingStore, open_m8_store
from tests.m8.support import (
    FailingEmbedder,
    assert_loop_responsive,
    heavy_profile,
    join_roster,
    probe_during,
    short_profile,
    specialist_profile,
    start_team,
)
from tests.team.conftest import deadline, join_member, make_did, profile

from agentconnect.team.directory import HashedEmbedder
from agentconnect.team.directory.directory import Directory
from agentconnect.team.store.memory import MemoryStore

pytestmark = pytest.mark.asyncio


def _member(name: str, member_profile: dict) -> dict[str, Any]:
    return {
        "name": name,
        "address": f"{name}@content-squad",
        "agent_did": make_did(name),
        "profile": member_profile,
    }


async def _warm_directory(
    count: int, *, specialist: bool = True
) -> tuple[Directory, list]:
    store = CountingStore(MemoryStore())
    directory = Directory(store, HashedEmbedder())
    members = []
    if specialist:
        members.append(_member("reviewer", specialist_profile()))
        count -= 1
    for index in range(max(0, count)):
        members.append(_member(f"agent{index:04d}", short_profile(index)))
    for member in members:
        await directory.upsert(member["name"], member["profile"])
    await directory.search(
        "similar paperwork",
        members[: min(8, len(members))],
        exclude_address="researcher@content-squad",
        limit=None,
        detail="summary",
    )
    return directory, members


async def _measure_team_find(team, token: str, samples: int = 10) -> list[float]:
    times: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        found = await team.find(token, "similar paperwork")
        times.append(time.perf_counter() - started)
        assert found["matches"]
    return times


@pytest.mark.perf
@pytest.mark.parametrize("size", [10, 100])
async def test_hashed_warm_team_find_meets_latency_budget(size: int):
    store = MemoryStore()
    team = await start_team(store)
    try:
        await join_roster(team, size, specialist=True)
        caller = await join_member(team, "researcher", agent_did=make_did("researcher"))
        await team.find(caller["session_token"], "similar paperwork")
        times = await _measure_team_find(team, caller["session_token"], samples=10)
        budget = find_p95_budget_s(size)
        assert budget is not None
        p95 = percentile(times, 95)
        assert p95 < budget, (
            f"hashed Team.find p95 {p95 * 1000:.1f}ms exceeds "
            f"{budget * 1000:.0f}ms at {size}"
        )
    finally:
        await team.stop()


async def test_warm_ranking_400_stays_within_loop_budget():
    directory, members = await _warm_directory(WARM_RANK_MEMBERS)
    found, delays = await probe_during(
        directory.search(
            "similar paperwork",
            members,
            exclude_address="researcher@content-squad",
            limit=None,
            detail="summary",
        ),
        members=WARM_RANK_MEMBERS,
    )
    assert len(found.matches) == 100
    assert delays


async def test_team_find_hashed_on_yielding_memory_and_redis():
    for kind in ("yielding-memory", "redis"):
        store = await open_m8_store(kind)
        team = await start_team(store)
        try:
            await join_member(
                team,
                "reviewer",
                agent_did=make_did("reviewer"),
                profile=specialist_profile(),
            )
            for index in range(9):
                name = f"agent{index:02d}"
                await join_member(
                    team, name, agent_did=make_did(name), profile=short_profile(index)
                )
            caller = await join_member(
                team, "researcher", agent_did=make_did("researcher")
            )
            found = await team.find(
                caller["session_token"], "someone who can verify a contract"
            )
            assert found["matches"][0]["address"] == "reviewer@content-squad"
        finally:
            await team.stop()
            await store.clear()
            await store.close()


async def test_http_find_hashed_ten_members():
    store = YieldingStore()
    team = await start_team(store)
    try:
        url = await team.serve()
        await join_member(
            team,
            "reviewer",
            agent_did=make_did("reviewer"),
            profile=specialist_profile(),
        )
        for index in range(9):
            name = f"agent{index:02d}"
            await join_member(
                team, name, agent_did=make_did(name), profile=short_profile(index)
            )
        from tests.agent.conftest import EchoAgent

        caller = EchoAgent(name="researcher")
        await caller.join(url)
        try:
            found = await caller.find("someone who can verify a contract")
            assert found.matches[0].address == "reviewer@content-squad"
        finally:
            await caller.leave()
    finally:
        await team.stop()


async def test_concurrent_searches_share_one_space():
    directory, members = await _warm_directory(100)
    results = await asyncio.gather(
        *[
            directory.search(
                "similar paperwork",
                members,
                exclude_address="researcher@content-squad",
                limit=5,
                detail="summary",
            )
            for _ in range(8)
        ]
    )
    assert all(result.matches for result in results)
    first = results[0].matches[0].address
    assert all(result.matches[0].address == first for result in results)


async def test_profile_update_rebuilds_that_vector():
    store = MemoryStore()
    directory = Directory(store, HashedEmbedder())
    writer = _member("writer", profile(summary="Writes short drafts from notes."))
    await directory.upsert(writer["name"], writer["profile"])
    updated = _member("writer", specialist_profile())
    await directory.upsert(updated["name"], updated["profile"])
    found = await directory.search(
        "contract review",
        [updated],
        exclude_address="researcher@content-squad",
        limit=None,
        detail="summary",
    )
    assert found.matches[0].address == "writer@content-squad"


async def test_backend_failure_rebuild_stays_responsive():
    class _FailAfter:
        name = "openai:fake"
        input_char_limit = None
        max_batch = 8

        def __init__(self) -> None:
            self.calls = 0

        async def embed(self, texts: Sequence[str]) -> list[list[float]]:
            self.calls += 1
            if self.calls > 4:
                raise RuntimeError("api down")
            return [[1.0, 0.0] for _ in texts]

    store = MemoryStore()
    directory = Directory(store, _FailAfter())
    members = [
        _member(f"agent{index:02d}", heavy_profile(f"task{index:02d}"))
        for index in range(20)
    ]
    for member in members[:3]:
        await directory.upsert(member["name"], member["profile"])
    found, delays = await probe_during(
        directory.search(
            "clause review notes",
            members,
            exclude_address="researcher@content-squad",
            limit=None,
            detail="summary",
        ),
        members=20,
        rebuild=True,
    )
    assert len(found.matches) == 20
    assert directory.using_fallback
    assert_loop_responsive(delays, members=20, rebuild=True)


async def test_send_renew_and_expiry_overlap_find():
    store = MemoryStore()
    runtime = await start_team(store, sweep_interval_seconds=0.05, lease_ttl_seconds=8)
    try:
        writer = await join_member(runtime, "writer", max_in_flight=8)
        for index in range(40):
            name = f"agent{index:03d}"
            await join_member(
                runtime, name, agent_did=make_did(name), profile=short_profile(index)
            )
        caller = await join_member(
            runtime, "researcher", agent_did=make_did("researcher")
        )
        await runtime.find(caller["session_token"], "similar paperwork")
        await runtime.send(
            caller["session_token"],
            {
                "id": str(uuid.uuid4()),
                "recipient": "writer",
                "kind": "request",
                "content": "hold-for-renew",
                "collect": "ticket",
                "deadline": deadline(20),
            },
        )
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        send_samples: list[float] = []
        renew_samples: list[float] = []
        for _ in range(10):
            search = asyncio.create_task(
                runtime.find(caller["session_token"], "similar paperwork")
            )
            await asyncio.sleep(0)
            started = time.perf_counter()
            sent = await runtime.send(
                caller["session_token"],
                {
                    "id": str(uuid.uuid4()),
                    "recipient": "writer",
                    "kind": "event",
                    "content": "notes",
                },
            )
            send_samples.append(time.perf_counter() - started)
            started = time.perf_counter()
            renewed = await runtime.renew(writer["session_token"], delivery["lease_id"])
            renew_samples.append(time.perf_counter() - started)
            found = await search
            assert sent["message"]["recipient"] == "writer@content-squad"
            assert renewed["lease_expires_at"]
            assert found["matches"]
        assert percentile(send_samples, 95) < SEND_DURING_FIND_P95_S
        assert percentile(renew_samples, 95) < SEND_DURING_FIND_P95_S
        expiring = await runtime.send(
            caller["session_token"],
            {
                "id": str(uuid.uuid4()),
                "recipient": "writer",
                "kind": "request",
                "content": "expire-during-find",
                "collect": "ticket",
                "deadline": deadline(0.2),
            },
        )
        found, _delays = await probe_during(
            runtime.find(caller["session_token"], "similar paperwork"),
            members=40,
        )
        assert found["matches"]
        ticket = None
        for _ in range(40):
            ticket = await runtime.get_result(
                caller["session_token"], expiring["message"]["id"]
            )
            if ticket["state"] != "open":
                break
            await asyncio.sleep(0.05)
        assert ticket is not None and ticket["state"] == "expired"
        await runtime.reply(
            writer["session_token"],
            {
                "id": str(uuid.uuid4()),
                "lease_id": delivery["lease_id"],
                "outcome": "completed",
                "content": "done",
            },
        )
    finally:
        await runtime.stop()


async def test_runtime_cold_long_profiles_stay_responsive():
    store = MemoryStore()
    team = await start_team(store, embeddings=HashedEmbedder())

    async def cold():
        for index in range(20):
            name = f"agent{index:02d}"
            await join_member(
                team,
                name,
                agent_did=make_did(name),
                profile=heavy_profile(f"task{index:02d}"),
            )
        caller = await join_member(team, "researcher")
        return await team.find(caller["session_token"], "clause review notes")

    try:
        found, _intervals = await probe_during(cold(), members=20)
        assert found["matches"]
        assert team._directory is not None
        assert not team._directory.using_fallback
    finally:
        await team.stop()
        await store.close()


async def test_runtime_profile_update_ranks_new_skill():
    store = MemoryStore()
    team = await start_team(store, embeddings=HashedEmbedder())
    writer_did = make_did("writer")
    try:
        await join_member(
            team, "writer", agent_did=writer_did, profile=short_profile(0)
        )
        for index in range(7):
            name = f"agent{index:02d}"
            await join_member(
                team,
                name,
                agent_did=make_did(name),
                profile=heavy_profile(f"task{index:02d}"),
            )
        caller = await join_member(team, "researcher")
        token = caller["session_token"]
        await join_member(
            team, "writer", agent_did=writer_did, profile=specialist_profile()
        )
        found, _intervals = await probe_during(
            team.find(token, "missing terms and contract risk"),
            members=8,
        )
        assert found["matches"][0]["address"] == "writer@content-squad"
    finally:
        await team.stop()
        await store.close()


async def test_runtime_fallback_rebuild_stays_responsive():
    store = MemoryStore()
    embedder = FailingEmbedder(succeed_calls=22)
    team = await start_team(store, embeddings=embedder)

    try:
        for index in range(20):
            name = f"agent{index:02d}"
            await join_member(
                team,
                name,
                agent_did=make_did(name),
                profile=heavy_profile(f"task{index:02d}"),
            )
        caller = await join_member(team, "researcher")
        found, _intervals = await probe_during(
            team.find(caller["session_token"], "clause review notes"),
            members=20,
            rebuild=True,
        )
        assert found["matches"]
        assert team._directory is not None
        assert team._directory.using_fallback
        assert team._directory.backend_name == "hashed"
    finally:
        await team.stop()
        await store.close()
