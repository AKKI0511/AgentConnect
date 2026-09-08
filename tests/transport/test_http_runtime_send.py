"""HTTP Runtime send retries the same body and returns a typed result."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from agentconnect.transport.agent_http import HttpRuntimeTransport
from agentconnect.transport.runtime import TransportError

_DID = "did:key:z6MkmEtU9Z7p7G6vbULDgMk8DXCVqW8rNyLMtd2RrAHjLD3m"
_ID = "15c44926-4c2a-4a01-a13b-95152da9a859"
_TS = "2026-08-18T15:00:00Z"


def _send_body() -> dict[str, Any]:
    return {
        "id": _ID,
        "recipient": "writer",
        "kind": "request",
        "content": "draft this",
        "collect": "wait",
        "deadline": "2026-08-18T15:10:00Z",
    }


def _send_result() -> dict[str, Any]:
    return {
        "status": "ticketed",
        "message": {
            "id": _ID,
            "sender": "researcher@content-squad",
            "sender_did": _DID,
            "recipient": "writer@content-squad",
            "kind": "request",
            "content": "draft this",
            "created_at": _TS,
            "trace_id": "e26e64ce-f7f1-47c4-a323-e3a3867e7d28",
            "deadline": "2026-08-18T15:10:00Z",
        },
        "ticket": {
            "id": _ID,
            "requester": "researcher@content-squad",
            "recipient": "writer@content-squad",
            "state": "open",
            "created_at": _TS,
            "updated_at": _TS,
            "deadline": "2026-08-18T15:10:00Z",
            "late_reply_count": 0,
        },
    }


@pytest.mark.asyncio
async def test_send_retries_same_body_after_timeout():
    transport = HttpRuntimeTransport("http://127.0.0.1:9")
    calls: list[dict[str, Any]] = []

    async def _request(method, path, **kwargs):
        calls.append(dict(kwargs.get("json") or {}))
        if len(calls) == 1:
            raise httpx.TimeoutException("held")
        return _send_result()

    transport._request = _request  # type: ignore[method-assign]
    result = await transport.send("token", _send_body())
    assert calls == [_send_body(), _send_body()]
    assert result["message"]["sender_did"] == _DID
    assert result["message"]["trace_id"]
    assert result["message"]["content"] == "draft this"
    await transport.close()


@pytest.mark.asyncio
async def test_send_timeout_twice_is_unavailable():
    transport = HttpRuntimeTransport("http://127.0.0.1:9")

    async def _request(method, path, **kwargs):
        raise httpx.TimeoutException("held")

    transport._request = _request  # type: ignore[method-assign]
    with pytest.raises(TransportError) as exc:
        await transport.send("token", _send_body())
    assert exc.value.code == "unavailable"
    assert exc.value.retryable is True
    assert "may already have accepted" in exc.value.message
    assert "before the Runtime accepted" not in exc.value.message
    await transport.close()


@pytest.mark.asyncio
async def test_stalled_ticket_read_uses_configured_timeout():
    transport = HttpRuntimeTransport("http://127.0.0.1:9", timeout=1.25)
    transport.configure_wait_hold(25.0)
    seen: list[Any] = []

    async def request(method, url, **kwargs):
        seen.append(kwargs.get("timeout", "client-default"))
        raise httpx.TimeoutException("stalled")

    transport._client.request = request  # type: ignore[method-assign]
    with pytest.raises(TransportError) as exc:
        await transport.get_result("token", _ID)
    assert exc.value.code == "unavailable"
    assert exc.value.retryable is True
    assert seen == ["client-default"]
    assert "never accepted" not in exc.value.message
    await transport.close()


@pytest.mark.asyncio
async def test_heartbeat_uses_configured_timeout():
    transport = HttpRuntimeTransport("http://127.0.0.1:9", timeout=1.25)
    transport.configure_wait_hold(25.0)
    seen: list[Any] = []

    async def request(method, url, **kwargs):
        seen.append(kwargs.get("timeout", "client-default"))
        raise httpx.TimeoutException("stalled")

    transport._client.request = request  # type: ignore[method-assign]
    with pytest.raises(TransportError) as exc:
        await transport.heartbeat("token")
    assert exc.value.code == "unavailable"
    assert seen == ["client-default"]
    await transport.close()


@pytest.mark.asyncio
async def test_send_timeout_covers_wait_hold():
    transport = HttpRuntimeTransport("http://127.0.0.1:9", timeout=1.25)
    transport.configure_wait_hold(10.0)
    seen: list[Any] = []

    async def request(method, url, **kwargs):
        seen.append(kwargs.get("timeout"))
        raise httpx.TimeoutException("held")

    transport._client.request = request  # type: ignore[method-assign]
    with pytest.raises(TransportError) as exc:
        await transport.send("token", _send_body())
    assert exc.value.code == "unavailable"
    assert "may already have accepted" in exc.value.message
    assert seen == [15.0, 15.0]
    await transport.close()
