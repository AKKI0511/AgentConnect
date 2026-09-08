"""Delivery lease renewal is a Session operation, distinct from heartbeat."""

from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest

from agentconnect.team import Team, TeamError
from tests.team.conftest import deadline, join_member, make_did, profile


def _id() -> str:
    return str(uuid.uuid4())


async def _started_team(**kwargs) -> Team:
    runtime = Team("content-squad", session_ttl_seconds=30, **kwargs)
    await runtime.start()
    return runtime


@pytest.mark.asyncio
async def test_renew_extends_active_lease():
    runtime = await _started_team(lease_ttl_seconds=8, sweep_interval_seconds=0.05)
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "request",
                "content": "hold",
                "collect": "ticket",
                "deadline": deadline(20),
            },
        )
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        first_expiry = delivery["lease_expires_at"]
        await asyncio.sleep(0.05)
        renewed = await runtime.renew(writer["session_token"], delivery["lease_id"])
        assert renewed["lease_id"] == delivery["lease_id"]
        assert renewed["lease_expires_at"] >= first_expiry
        await runtime.reply(
            writer["session_token"],
            {
                "id": _id(),
                "lease_id": delivery["lease_id"],
                "outcome": "completed",
                "content": "done",
            },
        )
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_heartbeat_does_not_extend_lease():
    runtime = await _started_team(lease_ttl_seconds=8, sweep_interval_seconds=0.05)
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "hold",
            },
        )
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        await runtime.heartbeat(writer["session_token"])
        store = runtime._store
        assert store is not None
        lease = await store.get(f"lease:{delivery['lease_id']}")
        assert lease is not None
        assert lease["expires_at"] == delivery["lease_expires_at"]
        await runtime.complete(writer["session_token"], delivery["lease_id"])
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_renew_foreign_lease_is_not_found():
    runtime = await _started_team(lease_ttl_seconds=8, sweep_interval_seconds=0.05)
    try:
        writer = await join_member(runtime, "writer")
        editor = await join_member(runtime, "editor")
        researcher = await join_member(runtime, "researcher")
        await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "hold",
            },
        )
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        with pytest.raises(TeamError) as exc:
            await runtime.renew(editor["session_token"], delivery["lease_id"])
        assert exc.value.code == "not_found"
        await runtime.complete(writer["session_token"], delivery["lease_id"])
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_renew_other_session_same_membership_is_not_found():
    runtime = await _started_team(lease_ttl_seconds=8, sweep_interval_seconds=0.05)
    try:
        did = make_did("writer")
        writer = await runtime.join(
            name="writer",
            agent_did=did,
            profile=profile(),
            instance_id="8f0d3e6a-6b1f-4d1e-9a2c-2f0b7c9d1e5a",
        )
        other = await runtime.join(
            name="writer",
            agent_did=did,
            profile=profile(),
            instance_id="9f0d3e6a-6b1f-4d1e-9a2c-2f0b7c9d1e5b",
        )
        researcher = await join_member(runtime, "researcher")
        await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "hold",
            },
        )
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        with pytest.raises(TeamError) as exc:
            await runtime.renew(other["session_token"], delivery["lease_id"])
        assert exc.value.code == "not_found"
        await runtime.complete(writer["session_token"], delivery["lease_id"])
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_renew_after_expiry_fails():
    runtime = await _started_team(
        lease_ttl_seconds=0.15,
        sweep_interval_seconds=0.05,
    )
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "hold",
            },
        )
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        await asyncio.sleep(0.4)
        with pytest.raises(TeamError) as exc:
            await runtime.renew(writer["session_token"], delivery["lease_id"])
        assert exc.value.code == "lease_expired"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_renew_cannot_pass_request_deadline():
    runtime = await _started_team(lease_ttl_seconds=30, sweep_interval_seconds=0.05)
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        due = deadline(0.8)
        await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "request",
                "content": "soon",
                "collect": "ticket",
                "deadline": due,
            },
        )
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        renewed = await runtime.renew(writer["session_token"], delivery["lease_id"])
        assert renewed["lease_expires_at"] <= due
        await runtime.complete(writer["session_token"], delivery["lease_id"])
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_http_renew_extends_lease():
    runtime = await _started_team(lease_ttl_seconds=8, sweep_interval_seconds=0.05)
    try:
        writer = await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        origin = await runtime.serve()
        await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "hold",
            },
        )
        delivery = (await runtime.lease(writer["session_token"]))["deliveries"][0]
        async with httpx.AsyncClient() as client:
            response = await client.post(
                origin + "/agentconnect/v1/deliveries/renew",
                json={"lease_id": delivery["lease_id"]},
                headers={"Authorization": f"Bearer {writer['session_token']}"},
            )
            extra = await client.post(
                origin + "/agentconnect/v1/deliveries/renew",
                json={
                    "lease_id": delivery["lease_id"],
                    "ttl_seconds": 30,
                },
                headers={"Authorization": f"Bearer {writer['session_token']}"},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["lease_id"] == delivery["lease_id"]
        assert "lease_expires_at" in body
        assert extra.status_code == 400
        assert extra.json()["code"] == "invalid_request"
        await runtime.complete(writer["session_token"], delivery["lease_id"])
    finally:
        await runtime.stop()
