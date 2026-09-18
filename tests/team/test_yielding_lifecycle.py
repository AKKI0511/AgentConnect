"""Runtime lifecycle against a yielding memory store and real Redis."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from tests.support.budgets import RETENTION_CYCLES, RETENTION_SLACK_BYTES
from tests.support.stores import connect_redis, drop_http_send, restart_redis, redis_url
from tests.support.runtime import message_id, start_team
from tests.team.conftest import deadline, join_member, make_did, profile

from agentconnect.core.identity import AgentIdentity, issue_identity_proof
from agentconnect.team import Team, TeamError
from agentconnect.team.retention import RETAINED_BYTES_KEY

pytestmark = pytest.mark.asyncio


async def _join_with_proof(team: Team, identity: AgentIdentity, name: str, token: str):
    challenge = await team.join_challenge()
    proof = issue_identity_proof(identity, challenge)
    return await team.join(
        name=name,
        agent_did=identity.did,
        profile=profile(),
        join_token=token,
        identity_proof=proof,
    )


async def test_concurrent_send_accepts_one_mailbox_item(runtime_store):
    team = await start_team(runtime_store, lease_ttl_seconds=8)
    try:
        writer = await join_member(team, "writer", max_in_flight=4)
        researcher = await join_member(team, "researcher")
        body = {
            "id": message_id(),
            "recipient": "writer",
            "kind": "event",
            "content": "once",
        }
        first, second = await asyncio.gather(
            team.send(researcher["session_token"], body),
            team.send(researcher["session_token"], body),
        )
        assert first["message"]["id"] == second["message"]["id"]
        leased = await team.lease(writer["session_token"], max_items=10)
        assert len(leased["deliveries"]) == 1
    finally:
        await team.stop()


async def test_single_use_token_admits_one_join(runtime_store):
    team = await start_team(runtime_store, require_join_auth=True)
    writer = AgentIdentity.create_key_based()
    editor = AgentIdentity.create_key_based()
    try:
        issued = await team.issue_join_token(single_use=True)

        async def _join(identity: AgentIdentity, name: str):
            return await _join_with_proof(team, identity, name, issued["token"])

        results = await asyncio.gather(
            _join(writer, "writer"),
            _join(editor, "editor"),
            return_exceptions=True,
        )
        successes = [item for item in results if not isinstance(item, BaseException)]
        failures = [item for item in results if isinstance(item, TeamError)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert failures[0].code == "unauthorized"
    finally:
        await team.stop()


async def test_name_reuse_cannot_read_predecessor(runtime_store):
    team = await start_team(runtime_store)
    try:
        await join_member(team, "writer")
        researcher = await join_member(team, "researcher")
        sent = await team.send(
            researcher["session_token"],
            {
                "id": message_id(),
                "recipient": "writer",
                "kind": "request",
                "content": "secret",
                "collect": "ticket",
                "deadline": deadline(20),
            },
        )
        await team.remove_membership("researcher")
        impostor = await join_member(team, "researcher", agent_did=make_did("impostor"))
        with pytest.raises(TeamError) as exc:
            await team.get_result(impostor["session_token"], sent["message"]["id"])
        assert exc.value.code == "not_found"
    finally:
        await team.stop()


async def test_lost_send_response_replays_the_same_id(runtime_store):
    team = await start_team(runtime_store)
    try:
        writer = await join_member(team, "writer")
        researcher = await join_member(team, "researcher")
        body = {
            "id": message_id(),
            "recipient": "writer",
            "kind": "request",
            "content": "draft",
            "collect": "ticket",
            "deadline": deadline(20),
        }
        first = await team.send(researcher["session_token"], body)
        replay = await team.send(researcher["session_token"], body)
        assert replay["message"]["id"] == first["message"]["id"]
        assert replay["ticket"]["id"] == first["ticket"]["id"]
        leased = await team.lease(writer["session_token"], max_items=10)
        assert len(leased["deliveries"]) == 1
    finally:
        await team.stop()


async def test_reconnect_recovers_open_ticket(runtime_store):
    team = await start_team(runtime_store)
    try:
        await join_member(team, "writer")
        did = make_did("researcher")
        instance = str(uuid.uuid4())
        first = await join_member(
            team, "researcher", agent_did=did, instance_id=instance
        )
        sent = await team.send(
            first["session_token"],
            {
                "id": message_id(),
                "recipient": "writer",
                "kind": "request",
                "content": "keep",
                "collect": "ticket",
                "deadline": deadline(20),
            },
        )
        second = await join_member(
            team, "researcher", agent_did=did, instance_id=instance
        )
        ticket = await team.get_result(second["session_token"], sent["message"]["id"])
        assert ticket["state"] == "open"
        assert ticket["id"] == sent["message"]["id"]
    finally:
        await team.stop()


@pytest.mark.redis
async def test_redis_restart_recovers_ticket_and_mailbox():
    store = await connect_redis()
    prefix = store._prefix
    try:
        first = await start_team(store)
        try:
            await join_member(first, "writer", agent_did=make_did("writer"))
            researcher = await join_member(
                first, "researcher", agent_did=make_did("researcher")
            )
            sent = await first.send(
                researcher["session_token"],
                {
                    "id": message_id(),
                    "recipient": "writer",
                    "kind": "request",
                    "content": "persist",
                    "collect": "ticket",
                    "deadline": deadline(60),
                },
            )
            ticket_id = sent["message"]["id"]
        finally:
            await first.stop()
            await store.close()

        await restart_redis()

        store = await connect_redis(prefix=prefix)
        second = await start_team(store)
        try:
            researcher = await second.join(
                name="researcher",
                agent_did=make_did("researcher"),
                profile=profile(),
            )
            ticket = await second.get_result(researcher["session_token"], ticket_id)
            assert ticket["state"] == "open"
            writer = await second.join(
                name="writer",
                agent_did=make_did("writer"),
                profile=profile(),
            )
            delivery = (await second.lease(writer["session_token"]))["deliveries"][0]
            assert delivery["message"]["id"] == ticket_id
            await second.reply(
                writer["session_token"],
                {
                    "id": message_id(),
                    "lease_id": delivery["lease_id"],
                    "outcome": "completed",
                    "content": "after-restart",
                },
            )
            done = await second.get_result(researcher["session_token"], ticket_id)
            assert done["state"] == "completed"
            assert done["response"]["content"] == "after-restart"
        finally:
            await second.stop()
    finally:
        await store.clear()
        await store.close()


@pytest.mark.redis
async def test_live_runtime_reconnects_after_redis_restart():
    store = await connect_redis()
    team = await start_team(store, lease_ttl_seconds=30)
    try:
        writer = await join_member(team, "writer", agent_did=make_did("writer"))
        researcher = await join_member(
            team, "researcher", agent_did=make_did("researcher")
        )
        sent = await team.send(
            researcher["session_token"],
            {
                "id": message_id(),
                "recipient": "writer",
                "kind": "request",
                "content": "live-reconnect",
                "collect": "ticket",
                "deadline": deadline(60),
            },
        )
        await restart_redis()
        ticket = await team.get_result(
            researcher["session_token"], sent["message"]["id"]
        )
        assert ticket["state"] == "open"
        delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
        assert delivery["message"]["id"] == sent["message"]["id"]
    finally:
        await team.stop()
        await store.clear()
        await store.close()


@pytest.mark.redis
async def test_abrupt_process_exit_recovers_ticket_and_mailbox(tmp_path: Path):
    import tests.support.crash_worker as crash_worker

    prefix = f"ac:test:crash:{uuid.uuid4()}"
    out_path = tmp_path / "crash.json"
    worker = Path(crash_worker.__file__)
    completed = subprocess.run(
        [
            sys.executable,
            str(worker),
            "--url",
            redis_url(),
            "--prefix",
            prefix,
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert completed.returncode != 0
    assert out_path.is_file(), completed.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    ticket_id = payload["ticket_id"]
    store = await connect_redis(prefix=prefix)
    team = await start_team(store, lease_ttl_seconds=30)
    try:
        researcher = await team.join(
            name="researcher",
            agent_did=make_did("researcher"),
            profile=profile(),
        )
        ticket = await team.get_result(researcher["session_token"], ticket_id)
        assert ticket["state"] == "open"
        writer = await team.join(
            name="writer",
            agent_did=make_did("writer"),
            profile=profile(),
        )
        delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
        assert delivery["message"]["id"] == ticket_id
        await team.reply(
            writer["session_token"],
            {
                "id": message_id(),
                "lease_id": delivery["lease_id"],
                "outcome": "completed",
                "content": "after-kill",
            },
        )
        done = await team.get_result(researcher["session_token"], ticket_id)
        assert done["state"] == "completed"
        assert done["response"]["content"] == "after-kill"
    finally:
        await team.stop()
        await store.clear()
        await store.close()


@pytest.mark.redis
async def test_lost_http_send_replays_the_same_id():
    store = await connect_redis()
    team = await start_team(store, lease_ttl_seconds=8)
    try:
        origin = await team.serve()
        writer = await join_member(team, "writer")
        researcher = await join_member(team, "researcher")
        body = {
            "id": message_id(),
            "recipient": "writer",
            "kind": "request",
            "content": "dropped-response",
            "collect": "ticket",
            "deadline": deadline(20),
        }
        await drop_http_send(origin, researcher["session_token"], body)
        await asyncio.sleep(0.1)
        replay = await team.send(researcher["session_token"], body)
        assert replay["message"]["id"] == body["id"]
        leased = await team.lease(writer["session_token"], max_items=10)
        assert len(leased["deliveries"]) == 1
        assert leased["deliveries"][0]["message"]["id"] == body["id"]
    finally:
        await team.stop()
        await store.clear()
        await store.close()


async def test_lease_renew_extends_expiry(runtime_store):
    team = await start_team(runtime_store, lease_ttl_seconds=8)
    try:
        writer = await join_member(team, "writer")
        researcher = await join_member(team, "researcher")
        await team.send(
            researcher["session_token"],
            {
                "id": message_id(),
                "recipient": "writer",
                "kind": "request",
                "content": "hold",
                "collect": "ticket",
                "deadline": deadline(20),
            },
        )
        delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
        first_expiry = delivery["lease_expires_at"]
        await asyncio.sleep(0.05)
        renewed = await team.renew(writer["session_token"], delivery["lease_id"])
        assert renewed["lease_expires_at"] >= first_expiry
        await team.reply(
            writer["session_token"],
            {
                "id": message_id(),
                "lease_id": delivery["lease_id"],
                "outcome": "completed",
                "content": "done",
            },
        )
    finally:
        await team.stop()


async def test_cancelled_wait_does_not_duplicate_work(runtime_store):
    team = await start_team(runtime_store, wait_hold_seconds=2.0)
    try:
        writer = await join_member(team, "writer")
        researcher = await join_member(team, "researcher")
        body = {
            "id": message_id(),
            "recipient": "writer",
            "kind": "request",
            "content": "wait-me",
            "collect": "wait",
            "deadline": deadline(20),
        }
        task = asyncio.create_task(team.send(researcher["session_token"], body))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        replay = await team.send(researcher["session_token"], body)
        leased = await team.lease(writer["session_token"], max_items=10)
        assert len(leased["deliveries"]) == 1
        assert replay["message"]["id"] == body["id"]
    finally:
        await team.stop()


async def test_expiry_closes_open_ticket(runtime_store):
    team = await start_team(runtime_store, sweep_interval_seconds=0.05)
    try:
        await join_member(team, "writer")
        researcher = await join_member(team, "researcher")
        sent = await team.send(
            researcher["session_token"],
            {
                "id": message_id(),
                "recipient": "writer",
                "kind": "request",
                "content": "too-late",
                "collect": "ticket",
                "deadline": deadline(0.2),
            },
        )
        ticket = None
        for _ in range(40):
            ticket = await team.get_result(
                researcher["session_token"], sent["message"]["id"]
            )
            if ticket["state"] == "expired":
                break
            await asyncio.sleep(0.05)
        assert ticket is not None
        assert ticket["state"] == "expired"
    finally:
        await team.stop()


async def test_retention_reclaims_completed_body(runtime_store):
    team = await start_team(
        runtime_store,
        replay_horizon_seconds=1,
        sweep_interval_seconds=0.05,
        thread_message_limit=2,
    )
    try:
        writer = await join_member(team, "writer")
        researcher = await join_member(team, "researcher")
        empty = await runtime_store.get(RETAINED_BYTES_KEY)
        baseline = 0 if empty is None else int(empty)
        for _ in range(RETENTION_CYCLES):
            sent = await team.send(
                researcher["session_token"],
                {
                    "id": message_id(),
                    "recipient": "writer",
                    "kind": "request",
                    "content": "x" * 64,
                    "collect": "ticket",
                    "deadline": deadline(1.3),
                },
            )
            delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
            await team.reply(
                writer["session_token"],
                {
                    "id": message_id(),
                    "lease_id": delivery["lease_id"],
                    "outcome": "completed",
                    "content": "ok",
                },
            )
            done = await team.get_result(
                researcher["session_token"], sent["message"]["id"]
            )
            assert done["state"] == "completed"
        await asyncio.sleep(2.8)
        retained = await runtime_store.get(RETAINED_BYTES_KEY)
        current = 0 if retained is None else int(retained)
        assert current <= baseline + RETENTION_SLACK_BYTES
    finally:
        await team.stop()


async def test_schema_rejects_extra_send_field(runtime_store):
    team = await start_team(runtime_store)
    try:
        await join_member(team, "writer")
        researcher = await join_member(team, "researcher")
        with pytest.raises(TeamError) as extra:
            await team.send(
                researcher["session_token"],
                {
                    "id": message_id(),
                    "recipient": "writer",
                    "kind": "event",
                    "content": "hello",
                    "sender": "spoofed@content-squad",
                },
            )
        assert extra.value.code == "invalid_request"
        with pytest.raises(TeamError) as missing:
            await team.send(
                researcher["session_token"],
                {
                    "id": "not-a-uuid",
                    "recipient": "writer",
                    "kind": "event",
                    "content": "hello",
                },
            )
        assert missing.value.code == "invalid_request"
    finally:
        await team.stop()
