"""Memory and Redis store persistence for Tickets and mailboxes."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from tests.m8.stores import connect_redis
from tests.team.conftest import deadline, join_member, make_did, profile

from agentconnect.team import Team
from agentconnect.team.store import Cas, Insert, Put, RedisStore


def _id() -> str:
    return str(uuid.uuid4())


@pytest_asyncio.fixture(loop_scope="function")
async def redis_store(request: pytest.FixtureRequest):
    request.node.add_marker(pytest.mark.redis)
    store = await connect_redis(prefix=f"ac:pytest:{uuid.uuid4()}")
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


@pytest.mark.asyncio
async def test_redis_apply_is_all_or_nothing(redis_store: RedisStore):
    assert await redis_store.insert("ticket", {"state": "open"})
    record = await redis_store.get_record("ticket")
    assert record is not None
    result = await redis_store.apply(
        [
            Insert("msg", {"id": "m1"}),
            Cas("ticket", record.version + 3, {"state": "completed"}),
        ]
    )
    assert result.ok is False
    assert await redis_store.get("msg") is None
    assert await redis_store.get("ticket") == {"state": "open"}


@pytest.mark.asyncio
async def test_redis_concurrent_put_assigns_distinct_versions(redis_store: RedisStore):
    import asyncio

    assert await redis_store.insert("k", {"n": 0})
    await asyncio.gather(*[redis_store.put("k", {"n": i}) for i in range(10)])
    record = await redis_store.get_record("k")
    assert record is not None
    assert record.version == 11


@pytest.mark.asyncio
async def test_redis_apply_waits_when_the_pool_is_busy(redis_store: RedisStore):
    import asyncio

    count = 32
    results = await asyncio.gather(
        *[redis_store.apply([Put(f"k{i}", {"n": i})]) for i in range(count)]
    )
    assert all(result.ok for result in results)
    many = await redis_store.get_many([f"k{i}" for i in range(count)])
    assert [item["n"] for item in many] == list(range(count))


@pytest.mark.asyncio
async def test_redis_get_many_spans_mget_batches(redis_store: RedisStore):
    keys = [f"vec:{index}" for index in range(200)]
    for index, key in enumerate(keys):
        await redis_store.put(
            key,
            {"n": index, "mixed": [1, {"status": "accepted"}], "vector": [0.1, 0.2]},
        )
    many = await redis_store.get_many(keys)
    assert len(many) == 200
    assert many[0] == {
        "n": 0,
        "mixed": [1, {"status": "accepted"}],
        "vector": [0.1, 0.2],
    }
    assert many[199]["n"] == 199
    many[0]["mixed"][1]["status"] = "spoofed"
    assert (await redis_store.get(keys[0]))["mixed"][1]["status"] == "accepted"
    missing = await redis_store.get_many(["missing-a", keys[5], "missing-b"])
    assert missing[0] is None
    assert missing[1]["n"] == 5
    assert missing[2] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["increment", "insert", "apply"])
async def test_redis_lost_write_reply_is_not_replayed(
    redis_store, monkeypatch, operation
):
    from redis.exceptions import ConnectionError

    from agentconnect.team.store.ops import IncrementIfBelow

    client = await redis_store._client()
    if operation == "increment":
        original = redis_store._incr_if_below

        async def lost_reply(*args, **kwargs):
            await original(*args, **kwargs)
            raise ConnectionError("reply lost after commit")

        monkeypatch.setattr(redis_store, "_incr_if_below", lost_reply)
        call = redis_store.increment_if_below("count", 10)
    elif operation == "insert":
        original = client.set

        async def lost_reply(*args, **kwargs):
            await original(*args, **kwargs)
            raise ConnectionError("reply lost after commit")

        monkeypatch.setattr(client, "set", lost_reply)
        call = redis_store.insert("count", 1)
    else:
        original_pipeline = client.pipeline

        def pipeline(*args, **kwargs):
            pipe = original_pipeline(*args, **kwargs)
            original_parse = pipe.parse_response
            replies = 0

            async def lose_exec_reply(connection, command, **options):
                nonlocal replies
                value = await original_parse(connection, command, **options)
                if command == "_":
                    replies += 1
                    # MULTI, SET, EXEC: Redis has committed, but redis-py has
                    # not observed the EXEC reply and still considers us watching.
                    if replies == 3:
                        raise ConnectionError("reply lost after commit")
                return value

            pipe.parse_response = lose_exec_reply
            return pipe

        monkeypatch.setattr(client, "pipeline", pipeline)
        call = redis_store.apply([IncrementIfBelow("count", 10)])

    with pytest.raises(ConnectionError, match="reply lost after commit"):
        await call
    assert await redis_store.get("count") == 1


@pytest.mark.asyncio
async def test_redis_read_retry_keeps_shared_pool(redis_store, monkeypatch):
    from redis.exceptions import ConnectionError

    await redis_store.put("value", 1)
    client = await redis_store._client()
    original = client.get
    calls = 0

    async def transient_read(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("transient read failure")
        return await original(*args, **kwargs)

    async def forbidden_close():
        pytest.fail("one read failure must not close the shared pool")

    with monkeypatch.context() as patch:
        patch.setattr(client, "get", transient_read)
        patch.setattr(redis_store, "close", forbidden_close)
        assert await redis_store.get("value") == 1
        assert await redis_store._client() is client
    assert calls == 2
