"""Session retries use the current transport and stay bounded."""

from __future__ import annotations

import asyncio
import time

import pytest

from agentconnect.agent.errors import SessionError
from agentconnect.agent.session import Session, _should_reconnect
from agentconnect.transport.runtime import TransportError


def test_busy_and_wait_limit_do_not_reconnect():
    assert not _should_reconnect(TransportError("busy", "full", retryable=True))
    assert not _should_reconnect(
        TransportError("wait_limit", "held", retryable=True)
    )
    assert _should_reconnect(TransportError("unauthorized", "gone"))
    assert _should_reconnect(TransportError("unavailable", "down", retryable=True))


class _FakeTransport:
    def __init__(self, name: str, *, fail_first: bool = False) -> None:
        self.name = name
        self.closed = False
        self.sends = 0
        self._fail_first = fail_first

    async def send(self, token: str, body: dict) -> dict:
        if self.closed:
            raise AssertionError(f"send on closed transport {self.name}")
        self.sends += 1
        if self._fail_first and self.sends == 1:
            raise TransportError("unauthorized", "gone")
        return {
            "status": "accepted",
            "message": {
                "id": body["id"],
                "sender": "researcher@content-squad",
                "kind": "event",
                "content": body.get("content"),
            },
        }

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_call_retries_send_on_current_transport():
    session = Session.__new__(Session)
    session._stopped = False
    session._connected = True
    session.session_token = "tok-1"
    session._target = "http://127.0.0.1:9"
    session._reconnect_lock = asyncio.Lock()
    first = _FakeTransport("first", fail_first=True)
    second = _FakeTransport("second")
    session._transport = first

    async def _reconnect() -> None:
        await first.close()
        session._transport = second
        session.session_token = "tok-2"
        session._connected = True

    session._reconnect = _reconnect
    result = await session._call(
        "send",
        "tok-1",
        {"id": "15c44926-4c2a-4a01-a13b-95152da9a859", "content": "ping"},
    )
    assert first.sends == 1
    assert first.closed
    assert second.sends == 1
    assert result["status"] == "accepted"


@pytest.mark.asyncio
async def test_call_does_not_reconnect_on_busy():
    session = Session.__new__(Session)
    session._stopped = False
    session._connected = True
    session.session_token = "tok-1"
    session._transport = _FakeTransport("only")

    async def _send(token: str, body: dict) -> dict:
        raise TransportError("busy", "full", retryable=True)

    session._transport.send = _send
    reconnected = False

    async def _reconnect() -> None:
        nonlocal reconnected
        reconnected = True

    session._reconnect = _reconnect
    with pytest.raises(SessionError) as exc:
        await session._call("send", "tok-1", {"id": "x"})
    assert exc.value.code == "busy"
    assert reconnected is False


@pytest.mark.asyncio
async def test_foreground_recovery_returns_when_reconnect_is_stuck():
    session = Session.__new__(Session)
    session._stopped = False
    session._connected = True
    session.session_token = "tok-1"
    session._reconnect_lock = asyncio.Lock()
    transport = _FakeTransport("only")
    transport._timeout = 0.05
    session._transport = transport

    async def _send(token: str, body: dict) -> dict:
        raise TransportError("unavailable", "down", retryable=True)

    session._transport.send = _send
    started = asyncio.Event()

    async def _reconnect() -> None:
        started.set()
        await asyncio.Event().wait()

    session._reconnect = _reconnect
    t0 = time.monotonic()
    with pytest.raises(SessionError) as exc:
        await session._call(
            "send",
            "tok-1",
            {"id": "15c44926-4c2a-4a01-a13b-95152da9a859", "content": "ping"},
        )
    elapsed = time.monotonic() - t0
    assert exc.value.code == "unavailable"
    assert exc.value.retryable is True
    assert "may already have accepted" in exc.value.message
    assert started.is_set()
    assert elapsed < 1.0


@pytest.mark.asyncio
async def test_foreground_recovery_timeout_leaves_background_reconnect():
    session = Session.__new__(Session)
    session._stopped = False
    session._connected = False
    session.session_token = "tok-1"
    session._reconnect_lock = asyncio.Lock()
    transport = _FakeTransport("only")
    transport._timeout = 0.05
    session._transport = transport

    async def _send(token: str, body: dict) -> dict:
        raise TransportError("unavailable", "down", retryable=True)

    session._transport.send = _send
    holding = asyncio.Event()

    async def _reconnect() -> None:
        async with session._reconnect_lock:
            holding.set()
            await asyncio.Event().wait()

    session._reconnect = _reconnect
    holder = asyncio.create_task(_reconnect())
    await holding.wait()
    t0 = time.monotonic()
    with pytest.raises(SessionError) as exc:
        await session._call("send", "tok-1", {"id": "x"})
    elapsed = time.monotonic() - t0
    assert exc.value.code == "unavailable"
    assert elapsed < 1.0
    assert not holder.done()
    holder.cancel()
    await asyncio.gather(holder, return_exceptions=True)


@pytest.mark.asyncio
async def test_call_retries_original_send_identity_after_lost_response():
    session = Session.__new__(Session)
    session._stopped = False
    session._connected = True
    session.session_token = "tok-1"
    session._target = "http://127.0.0.1:9"
    session._reconnect_lock = asyncio.Lock()
    bodies: list[dict] = []

    class _RetryTransport(_FakeTransport):
        async def send(self, token: str, body: dict) -> dict:
            bodies.append(dict(body))
            if self.name == "first":
                raise TransportError(
                    "unavailable",
                    "send timed out; the Runtime may already have accepted the Message",
                    retryable=True,
                )
            return await super().send(token, body)

    first = _RetryTransport("first")
    second = _RetryTransport("second")
    session._transport = first
    original = {
        "id": "15c44926-4c2a-4a01-a13b-95152da9a859",
        "content": "ping",
    }

    async def _reconnect() -> None:
        await first.close()
        session._transport = second
        session.session_token = "tok-2"
        session._connected = True

    session._reconnect = _reconnect
    result = await session._call("send", "tok-1", original)
    assert bodies == [original, original]
    assert result["message"]["id"] == original["id"]
    assert second.sends == 1
