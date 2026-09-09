"""Admission limits, Message size, and HTTP ingress bounds."""

from __future__ import annotations

import uuid

import httpx
import pytest

from agentconnect.team import Team, TeamError
from tests.team.conftest import deadline, join_member

PREFIX = "/agentconnect/v1"


def _id() -> str:
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_oversized_send_creates_nothing():
    tiny = Team("content-squad", max_message_bytes=80)
    await tiny.start()
    try:
        writer = await join_member(tiny, "writer")
        researcher = await join_member(tiny, "researcher")
        with pytest.raises(TeamError) as exc:
            await tiny.send(
                researcher["session_token"],
                {
                    "id": _id(),
                    "recipient": "writer",
                    "kind": "event",
                    "content": "n" * 400,
                },
            )
        assert exc.value.code == "payload_too_large"
        leased = await tiny.lease(writer["session_token"])
        assert leased["deliveries"] == []
    finally:
        await tiny.stop()


@pytest.mark.asyncio
async def test_oversized_reply_leaves_ticket_open_and_lease_active():
    tiny = Team("content-squad", max_message_bytes=2048)
    await tiny.start()
    try:
        writer = await join_member(tiny, "writer")
        researcher = await join_member(tiny, "researcher")
        sent = await tiny.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "request",
                "content": "work",
                "collect": "ticket",
                "deadline": deadline(20),
            },
        )
        delivery = (await tiny.lease(writer["session_token"]))["deliveries"][0]
        with pytest.raises(TeamError) as exc:
            await tiny.reply(
                writer["session_token"],
                {
                    "id": _id(),
                    "lease_id": delivery["lease_id"],
                    "outcome": "completed",
                    "content": "n" * 4000,
                },
            )
        assert exc.value.code == "payload_too_large"
        ticket = await tiny.get_result(
            researcher["session_token"], sent["message"]["id"]
        )
        assert ticket["state"] == "open"
        await tiny.reply(
            writer["session_token"],
            {
                "id": _id(),
                "lease_id": delivery["lease_id"],
                "outcome": "completed",
                "content": "ok",
            },
        )
        done = await tiny.get_result(researcher["session_token"], sent["message"]["id"])
        assert done["state"] == "completed"
        assert done["response"]["content"] == "ok"
    finally:
        await tiny.stop()


@pytest.mark.asyncio
async def test_http_content_length_over_budget_is_payload_too_large():
    runtime = Team("content-squad", max_message_bytes=64)
    await runtime.start()
    try:
        researcher = await join_member(runtime, "researcher")
        origin = await runtime.serve()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                origin + PREFIX + "/messages",
                headers={"Authorization": f"Bearer {researcher['session_token']}"},
                json={
                    "id": _id(),
                    "recipient": "writer",
                    "kind": "event",
                    "content": "n" * 200,
                },
            )
        assert response.status_code == 413
        assert response.json()["code"] == "payload_too_large"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_deadline_past_max_deadline_seconds_is_invalid():
    runtime = Team(
        "content-squad",
        max_deadline_seconds=5,
        work_lifetime_seconds=5,
    )
    await runtime.start()
    try:
        await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        with pytest.raises(TeamError) as exc:
            await runtime.send(
                researcher["session_token"],
                {
                    "id": _id(),
                    "recipient": "writer",
                    "kind": "request",
                    "content": "work",
                    "collect": "ticket",
                    "deadline": deadline(60),
                },
            )
        assert exc.value.code == "invalid_request"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_max_open_tickets_rejects_further_requests():
    runtime = Team("content-squad", max_open_tickets=1)
    await runtime.start()
    try:
        await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        first = await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "request",
                "content": "one",
                "collect": "ticket",
                "deadline": deadline(20),
            },
        )
        assert first["status"] == "ticketed"
        with pytest.raises(TeamError) as exc:
            await runtime.send(
                researcher["session_token"],
                {
                    "id": _id(),
                    "recipient": "writer",
                    "kind": "request",
                    "content": "two",
                    "collect": "ticket",
                    "deadline": deadline(20),
                },
            )
        assert exc.value.code == "busy"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_max_retained_bytes_rejects_new_send():
    runtime = Team("content-squad", max_retained_bytes=3000)
    await runtime.start()
    try:
        await join_member(runtime, "writer")
        researcher = await join_member(runtime, "researcher")
        await runtime.send(
            researcher["session_token"],
            {
                "id": _id(),
                "recipient": "writer",
                "kind": "event",
                "content": "keep",
            },
        )
        with pytest.raises(TeamError) as exc:
            await runtime.send(
                researcher["session_token"],
                {
                    "id": _id(),
                    "recipient": "writer",
                    "kind": "event",
                    "content": "n" * 4000,
                },
            )
        assert exc.value.code == "busy"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_join_challenge_cap_returns_busy():
    runtime = Team("content-squad", max_join_challenges=1)
    await runtime.start()
    try:
        first = await runtime.join_challenge()
        assert first["nonce"]
        with pytest.raises(TeamError) as exc:
            await runtime.join_challenge()
        assert exc.value.code == "busy"
    finally:
        await runtime.stop()
