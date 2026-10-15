import pytest

from agentconnect.transport.http import HTTPOutboundTransport
from agentconnect.transport.base import RouteContext
from agentconnect.transport.schemas import TransportTarget
from agentconnect.core.identity import AgentIdentity
from agentconnect.core.kinds import MessageKind
from agentconnect.transport.envelope import CollaborationMessage as Message


@pytest.mark.asyncio
async def test_circuit_breaker_and_health_cache(monkeypatch):
    t = HTTPOutboundTransport(verify_ssl=True, retries=0)

    # Force _request_with_retries to return a 503-like response
    class _Resp:
        def __init__(self, code):
            self.status_code = code
            self.headers = {}
            self.request = None

        def json(self):
            return {"status": "pending"}

    async def _request_with_retries(self, client, method, url, headers, json=None):
        return _Resp(503)

    monkeypatch.setattr(
        HTTPOutboundTransport, "_request_with_retries", _request_with_retries
    )

    msg = Message.create(
        sender_id="x",
        receiver_id="y",
        content="c",
        sender_identity=AgentIdentity.create_key_based(),
        kind=MessageKind.REQUEST,
        metadata={"request_id": "r1"},
    )
    target = TransportTarget(
        agent_id="y", url="http://down", inbox_path="/agentconnect/collaboration"
    )
    ctx = RouteContext()

    # 1st send fails and marks down
    ok, _, _ = await t.send(msg, target, ctx)
    assert not ok
    # Immediately attempt again; health cache should skip and not call _post_with_retries
    calls = {"req": 0}

    async def _request_with_retries_count(
        self, client, method, url, headers, json=None
    ):
        calls["req"] += 1
        return _Resp(503)

    monkeypatch.setattr(
        HTTPOutboundTransport, "_request_with_retries", _request_with_retries_count
    )
    ok2, _, _ = await t.send(msg, target, ctx)
    assert not ok2
    assert calls["req"] == 0

    # Now check() should promptly skip using the same key
    calls_check = {"req": 0}

    async def _request_with_retries_check(
        self, client, method, url, headers, json=None, timeout_override=None
    ):
        calls_check["req"] += 1
        return _Resp(503)

    monkeypatch.setattr(
        HTTPOutboundTransport, "_request_with_retries", _request_with_retries_check
    )
    status, _ = await t.check("r1", target, ctx)
    assert status == "pending"
    assert calls_check["req"] == 0


@pytest.mark.asyncio
async def test_idempotency_header_and_route_precedence(monkeypatch):
    t = HTTPOutboundTransport(verify_ssl=True, retries=0, idempotency_header="X-Idem")

    captured = {"url": None, "headers": None}

    class _Resp:
        def __init__(self, code):
            self.status_code = code
            self.headers = {}
            self.request = None

        def json(self):
            return {"status": "accepted", "request_id": "r-123"}

    async def _request_with_retries(self, client, method, url, headers, json=None):
        captured["url"] = url
        captured["headers"] = headers
        return _Resp(202)

    monkeypatch.setattr(
        HTTPOutboundTransport, "_request_with_retries", _request_with_retries
    )

    msg = Message.create(
        sender_id="a",
        receiver_id="b",
        content="c",
        sender_identity=AgentIdentity.create_key_based(),
        kind=MessageKind.REQUEST,
        metadata={"request_id": "xyz", "inbox_path": "/should/not/use"},
    )
    target = TransportTarget(agent_id="b", url="http://host/", inbox_path="/unused")
    ctx = RouteContext()

    ok, resp, req_id = await t.send(msg, target, ctx)
    assert ok and resp is None and req_id == "r-123"
    assert captured["url"] == "http://host/unused"
    # Ensure idempotency header present and not overridden by metadata path
    assert captured["headers"].get("X-Idem") == "xyz"
