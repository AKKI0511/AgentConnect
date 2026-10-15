import pytest

from agentconnect.transport.base import RouteContext
from agentconnect.transport.http import HTTPOutboundTransport
from agentconnect.transport.schemas import TransportTarget
from agentconnect.core.identity import AgentIdentity
from agentconnect.core.kinds import MessageKind
from agentconnect.transport.envelope import CollaborationMessage as Message


@pytest.mark.asyncio
async def test_http_idempotency_header_fallback_for_response(monkeypatch):
    transport = HTTPOutboundTransport()

    sent_headers = {}

    async def fake_post(url, headers=None, json=None):  # type: ignore[override]
        nonlocal sent_headers
        sent_headers = headers or {}

        class _Resp:
            status_code = 202

            def json(self):
                return {
                    "status": "accepted",
                    "request_id": json.get("envelope", {})
                    .get("metadata", {})
                    .get("request_id"),
                }

            @property
            def request(self):
                return type("_Req", (), {"url": url})

            @property
            def headers(self):
                return {}

        return _Resp()

    class _Client:
        async def post(self, url, headers=None, json=None):
            return await fake_post(url, headers=headers, json=json)

    async def fake_get_client(base_url):
        return _Client()

    monkeypatch.setattr(transport, "_get_client", fake_get_client)

    msg = Message.create(
        sender_id="a",
        receiver_id="b",
        content="resp",
        sender_identity=AgentIdentity.create_key_based(),
        kind=MessageKind.RESPONSE,
        metadata={"response_to": "abc-123"},
    )

    target = TransportTarget(
        agent_id="b", url="http://x", inbox_path="/agentconnect/collaboration"
    )
    ctx = RouteContext()
    await transport.send(msg, target, ctx)
    # Expect fallback idempotency header derived from response_to when request_id missing
    assert "X-Idempotency-Key" in sent_headers
    assert sent_headers["X-Idempotency-Key"] == "abc-123"
