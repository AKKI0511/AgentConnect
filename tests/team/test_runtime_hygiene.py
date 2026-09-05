"""Runtime hygiene: time-indexed expiry, store-backed presence, keyed locks."""

from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta

import pytest

from agentconnect.team import Team
from agentconnect.team.codec import format_timestamp, timestamp_score, utc_now
from agentconnect.team.locks import KeyedLock
import agentconnect.team.expiry as expiry_mod
from agentconnect.team.store import MemoryStore
from tests.team.conftest import join_member


@pytest.mark.asyncio
async def test_keyed_lock_serializes_one_key_and_allows_other_keys():
    locks = KeyedLock()
    order: list[str] = []

    async def hold(key: str, label: str, pause: float) -> None:
        async with locks.acquire(key):
            order.append(f"{label}:enter")
            await asyncio.sleep(pause)
            order.append(f"{label}:exit")

    await asyncio.gather(
        hold("a", "a1", 0.05),
        hold("a", "a2", 0.01),
        hold("b", "b1", 0.01),
    )
    a_events = [item for item in order if item.startswith("a")]
    assert len(a_events) == 4
    assert a_events[0].endswith("enter")
    assert a_events[1].endswith("exit")
    assert a_events[2].endswith("enter")
    assert a_events[3].endswith("exit")
    assert "b1:enter" in order


@pytest.mark.asyncio
async def test_expiry_due_returns_only_members_at_or_before_now():
    store = MemoryStore()
    await store.open()
    now = utc_now()
    past = format_timestamp(now - timedelta(seconds=5))
    future = format_timestamp(now + timedelta(seconds=60))
    await expiry_mod.schedule(store, expiry_mod.SESSIONS, "due", past)
    await expiry_mod.schedule(store, expiry_mod.SESSIONS, "later", future)
    popped = await expiry_mod.due(store, expiry_mod.SESSIONS, now)
    assert popped == ["due"]
    assert timestamp_score(past) < timestamp_score(future)


@pytest.mark.asyncio
async def test_sweep_expires_scheduled_session_and_ignores_unindexed():
    team = Team("content-squad", session_ttl_seconds=30, sweep_interval_seconds=60)
    await team.start()
    try:
        writer = await join_member(team, "writer")
        store = team._ensure_started()
        now = utc_now()
        past = format_timestamp(now - timedelta(seconds=1))
        planted = {
            "token": "orphan-unindexed",
            "membership_name": "writer",
            "address": "writer@content-squad",
            "agent_did": writer["agent_did"],
            "instance_id": "8f0d3e6a-6b1f-4d1e-9a2c-2f0b7c9d1e5a",
            "max_in_flight": 1,
            "expires_at": past,
            "lease_ids": [],
        }
        await store.put("session:orphan-unindexed", planted)
        session = await team._get_session(writer["session_token"])
        assert session is not None
        session["expires_at"] = past
        await team._save_session(session)
        await team._sweep_once()
        from agentconnect.team.errors import TeamError

        with pytest.raises(TeamError) as exc:
            await team.heartbeat(writer["session_token"])
        assert exc.value.code == "unauthorized"
        assert await store.get("session:orphan-unindexed") is not None
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_status_online_survives_memory_restart_of_session_map():
    team = Team("content-squad", session_ttl_seconds=30, sweep_interval_seconds=60)
    await team.start()
    try:
        await join_member(team, "writer")
        team._session_tokens_by_member.clear()
        operator = await team.ensure_operator_session()
        snapshot = await team.status(operator)
        by_name = {row["name"]: row for row in snapshot["members"]}
        assert by_name["writer"]["online"] is True
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_remove_membership_drops_sessions_from_store_after_map_clear():
    team = Team("content-squad", session_ttl_seconds=30, sweep_interval_seconds=60)
    await team.start()
    try:
        writer = await join_member(team, "writer")
        team._session_tokens_by_member.clear()
        await team.remove_membership("writer")
        from agentconnect.team.errors import TeamError

        with pytest.raises(TeamError) as exc:
            await team.heartbeat(writer["session_token"])
        assert exc.value.code == "unauthorized"
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_concurrent_send_and_lease_without_team_lock():
    team = Team("content-squad")
    await team.start()
    try:
        writer = await join_member(team, "writer", max_in_flight=8)
        researcher = await join_member(team, "researcher")

        async def send_one(i: int) -> None:
            await team.send(
                researcher["session_token"],
                {
                    "id": str(uuid.uuid4()),
                    "recipient": "writer",
                    "kind": "event",
                    "content": i,
                },
            )

        async def drain() -> list[dict]:
            got: list[dict] = []
            deadline = utc_now() + timedelta(seconds=2)
            while len(got) < 8 and utc_now() < deadline:
                batch = await team.lease(writer["session_token"], max_items=8)
                got.extend(batch["deliveries"])
                if len(got) < 8:
                    await asyncio.sleep(0.01)
            return got

        _, deliveries = await asyncio.gather(
            asyncio.gather(*[send_one(i) for i in range(8)]),
            drain(),
        )
        assert len(deliveries) == 8
    finally:
        await team.stop()
