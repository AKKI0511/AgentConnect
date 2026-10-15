import httpx
import pytest

from agentconnect.transport.http import HTTPOutboundTransport
from agentconnect.transport.base import RouteContext
from agentconnect.transport.schemas import TransportTarget
from agentconnect.core.identity import AgentIdentity
from agentconnect.core.kinds import MessageKind
from agentconnect.transport.envelope import CollaborationMessage as Message


@pytest.mark.asyncio
async def test_get_check_sends_no_json_and_no_raise(monkeypatch):
    t = HTTPOutboundTransport(verify_ssl=True, retries=0)

    # Build a client with MockTransport that asserts no body/Content-Type on GET
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        # No request body should be sent for GET
        assert (request.content or b"") == b""
        # Content-Type should not be set for GET
        assert request.headers.get("content-type") is None
        return httpx.Response(200, json={"status": "pending"})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, verify=True)

    async def _get_client(self, base_url: str):
        return client

    monkeypatch.setattr(HTTPOutboundTransport, "_get_client", _get_client)

    # Perform a check() call that uses GET internally
    target = TransportTarget(
        agent_id="b", url="http://h", inbox_path="/agentconnect/collaboration"
    )
    ctx = RouteContext()
    status, resp = await t.check("req-1", target, ctx)
    assert status in ("pending", "completed")
    assert resp is None or isinstance(resp, Message)


@pytest.mark.asyncio
async def test_cb_trips_on_network_exception_and_skips_next(monkeypatch):
    t = HTTPOutboundTransport(verify_ssl=True, retries=0)

    # First call raises a RequestError to simulate network failure
    calls = {"count": 0}

    async def _request_with_retries(
        self, client, method, url, headers, json=None, timeout_override=None
    ):
        calls["count"] += 1
        raise httpx.RequestError("boom", request=httpx.Request(method, url))

    monkeypatch.setattr(
        HTTPOutboundTransport, "_request_with_retries", _request_with_retries
    )

    msg = Message.create(
        sender_id="a",
        receiver_id="b",
        content="c",
        sender_identity=AgentIdentity.create_key_based(),
        kind=MessageKind.REQUEST,
        metadata={"request_id": "r-net"},
    )
    target = TransportTarget(
        agent_id="b", url="http://down", inbox_path="/agentconnect/collaboration"
    )
    ctx = RouteContext()

    ok, _, _ = await t.send(msg, target, ctx)
    assert not ok
    assert calls["count"] == 1

    # Second call should be skipped due to markdown/CB
    calls["count"] = 0

    async def _request_with_retries_count(
        self, client, method, url, headers, json=None, timeout_override=None
    ):
        calls["count"] += 1
        raise httpx.RequestError("boom2", request=httpx.Request(method, url))

    monkeypatch.setattr(
        HTTPOutboundTransport, "_request_with_retries", _request_with_retries_count
    )
    ok2, _, _ = await t.send(msg, target, ctx)
    assert not ok2
    assert calls["count"] == 0
