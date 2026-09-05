"""Memory and Redis store persistence for Tickets and mailboxes."""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio

from agentconnect.team import RedisStore, Team
from tests.team.conftest import deadline, join_member, profile, make_did


def _id() -> str:
    return str(uuid.uuid4())


@pytest_asyncio.fixture(loop_scope="function")
async def redis_store():
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/15")
    store = RedisStore(url, prefix=f"ac:pytest:{uuid.uuid4()}")
    try:
        await store.open()
        await store.ping()
    except Exception:
        pytest.skip("Redis is not reachable")
    try:
        yield store
    finally:
        await store.clear()
        await store.close()


@pytest.mark.asyncio
async def test_memory_put_lease_complete_reply_roundtrip():
    team = Team("content-squad")
    await team.start()
    try:
        writer = await join_member(team, "writer")
        researcher = await join_member(team, "researcher")
        sent = await team.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "request",
                "content": {"task": "draft"},
                "collect": "ticket",
                "deadline": deadline(30),
            },
        )
        delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
        replied = await team.reply(
            writer["session_token"],
            {
                "id": _id(),
                "lease_id": delivery["lease_id"],
                "outcome": "completed",
                "content": "done",
            },
        )
        assert replied["ticket"]["state"] == "completed"
        ticket = await team.get_result(
            researcher["session_token"], sent["message"]["id"]
        )
        assert ticket["response"]["content"] == "done"
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_redis_ticket_survives_runtime_restart(redis_store: RedisStore):
    first = Team("content-squad", store=redis_store)
    await first.start()
    try:
        await join_member(first, "writer", agent_did=make_did("writer"))
        researcher = await join_member(
            first, "researcher", agent_did=make_did("researcher")
        )
        sent = await first.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "request",
                "content": {"task": "draft"},
                "collect": "ticket",
                "deadline": deadline(60),
            },
        )
        ticket_id = sent["message"]["id"]
        writer_did = make_did("writer")
        researcher_did = make_did("researcher")
        writer_profile = profile()
        researcher_profile = profile(
            summary="Researches topics.",
            skill="research",
            description="Find sources.",
        )
    finally:
        await first.stop()

    second = Team("content-squad", store=redis_store)
    await second.start()
    try:
        researcher = await second.join(
            name="researcher",
            agent_did=researcher_did,
            profile=researcher_profile,
        )
        ticket = await second.get_result(researcher["session_token"], ticket_id)
        assert ticket["state"] == "open"
        writer = await second.join(
            name="writer",
            agent_did=writer_did,
            profile=writer_profile,
        )
        delivery = (await second.lease(writer["session_token"]))["deliveries"][0]
        assert delivery["message"]["id"] == ticket_id
        await second.reply(
            writer["session_token"],
            {
                "id": _id(),
                "lease_id": delivery["lease_id"],
                "outcome": "completed",
                "content": "still here after restart",
            },
        )
        done = await second.get_result(researcher["session_token"], ticket_id)
        assert done["state"] == "completed"
        assert done["response"]["content"] == "still here after restart"
    finally:
        await second.stop()


@pytest.mark.asyncio
async def test_redis_mailbox_event_survives_restart(redis_store: RedisStore):
    first = Team("ops-team", store=redis_store)
    await first.start()
    try:
        await join_member(first, "writer", agent_did=make_did("writer"))
        researcher = await join_member(
            first, "researcher", agent_did=make_did("researcher")
        )
        sent = await first.send(
            researcher["session_token"],
            {"id": _id(), "recipient": "writer", "kind": "event", "content": "ping"},
        )
        message_id = sent["message"]["id"]
    finally:
        await first.stop()

    second = Team("ops-team", store=redis_store)
    await second.start()
    try:
        writer = await second.join(
            name="writer",
            agent_did=make_did("writer"),
            profile=profile(),
        )
        delivery = (await second.lease(writer["session_token"]))["deliveries"][0]
        assert delivery["message"]["id"] == message_id
        await second.complete(writer["session_token"], delivery["lease_id"])
    finally:
        await second.stop()


@pytest.mark.asyncio
async def test_redis_status_online_survives_runtime_restart(redis_store: RedisStore):
    first = Team("content-squad", store=redis_store, session_ttl_seconds=120)
    await first.start()
    try:
        writer = await join_member(first, "writer", agent_did=make_did("writer"))
        writer_token = writer["session_token"]
    finally:
        await first.stop()

    second = Team("content-squad", store=redis_store, session_ttl_seconds=120)
    await second.start()
    try:
        second._session_tokens_by_member.clear()
        operator = await second.ensure_operator_session()
        snapshot = await second.status(operator)
        by_name = {row["name"]: row for row in snapshot["members"]}
        assert by_name["writer"]["online"] is True
        await second.heartbeat(writer_token)
    finally:
        await second.stop()


@pytest.mark.asyncio
async def test_redis_directory_vectors_survive_runtime_restart(redis_store: RedisStore):
    first = Team("content-squad", store=redis_store, embeddings="none")
    await first.start()
    try:
        await join_member(
            first,
            "reviewer",
            agent_did=make_did("reviewer"),
            profile=profile(
                summary="Reviews contracts for missing terms.",
                skill="contract_review",
                description="Review a contract.",
                tags=["contracts"],
            ),
        )
        await join_member(first, "writer", agent_did=make_did("writer"))
    finally:
        await first.stop()

    second = Team("content-squad", store=redis_store, embeddings="none")
    await second.start()
    try:
        caller = await join_member(
            second, "researcher", agent_did=make_did("researcher")
        )
        found = await second.find(caller["session_token"], "contract review")
        assert found["matches"][0]["address"] == "reviewer@content-squad"
    finally:
        await second.stop()
