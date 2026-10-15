import uuid

import pytest
from fastapi.testclient import TestClient

from agentconnect.config.servers import InboxServerSettings
from agentconnect.core.identity import AgentIdentity
from agentconnect.core.kinds import MessageKind
from agentconnect.gateway.inbound import create_agent_inbox_app
from agentconnect.index.registry import AgentRegistry, AgentRegistration
from agentconnect.index.types import AgentType, InteractionMode
from agentconnect.transport.envelope import CollaborationMessage as Message
from tests.gateway.conftest import InboxFacade


def _make_wire(
    sender_id: str, receiver_id: str, ident: AgentIdentity, req_id: str | None = None
):
    msg = Message.create(
        sender_id=sender_id,
        receiver_id=receiver_id,
        content="ping",
        sender_identity=ident,
        kind=MessageKind.REQUEST,
        metadata={"request_id": req_id or str(uuid.uuid4())},
    )
    return msg.to_wire_dict()


class EmptyCapabilityDiscovery:
    async def initialize_embeddings_model(self):
        return None

    async def update_capability_embeddings_cache(self, registration):
        return None

    async def clear_agent_embeddings_cache(self, agent_id: str):
        return None


class _Registry(AgentRegistry):
    def __init__(self):
        super().__init__()
        self._capability_discovery = EmptyCapabilityDiscovery()

    async def _initialize_vector_search(self):
        return None

    async def ensure_initialized(self):
        return True


@pytest.mark.asyncio
async def test_inbox_accepts_envelope_shape():
    sender_ident = AgentIdentity.create_key_based()
    reg = _Registry()
    hub = InboxFacade(reg)
    await reg.register(
        AgentRegistration(
            agent_id="sender3",
            agent_type=AgentType.AI,
            interaction_modes=[InteractionMode.AGENT_TO_AGENT],
            identity=sender_ident,
            url="http://remote-inbox",
        )
    )
    settings = InboxServerSettings(require_auth=False)
    app = create_agent_inbox_app(hub, settings)
    req_id = str(uuid.uuid4())
    wire = _make_wire("sender3", "responder3", sender_ident, req_id)
    payload = {"envelope": wire}
    with TestClient(app) as client:
        r1 = client.post(
            settings.path,
            json=payload,
            headers={settings.idempotency_header_name: req_id},
        )
        assert r1.status_code in (200, 202)
        assert r1.json().get("request_id") == req_id


@pytest.mark.asyncio
async def test_inbox_auth_applies_to_get():
    AgentIdentity.create_key_based()
    reg = _Registry()
    hub = InboxFacade(reg)
    settings = InboxServerSettings(require_auth=True)
    app = create_agent_inbox_app(hub, settings)
    req_id = str(uuid.uuid4())
    with TestClient(app) as client:
        r = client.get(f"{settings.path}/{req_id}")
        assert r.status_code == 401
    import os

    os.environ[settings.bearer_token_env_var] = "TOKEN"
    with TestClient(app) as client:
        r = client.get(
            f"{settings.path}/{req_id}",
            headers={settings.auth_header_name: "Bearer TOKEN"},
        )
        assert r.status_code in (200, 404)


@pytest.mark.asyncio
async def test_inbox_poll_returns_completed_when_tracker_has_response():
    sender_ident = AgentIdentity.create_key_based()
    reg = _Registry()
    hub = InboxFacade(reg)
    await reg.register(
        AgentRegistration(
            agent_id="sender2",
            agent_type=AgentType.AI,
            interaction_modes=[InteractionMode.AGENT_TO_AGENT],
            identity=sender_ident,
            url="http://remote-inbox",
        )
    )
    settings = InboxServerSettings(require_auth=False)
    app = create_agent_inbox_app(hub, settings)
    req_id = str(uuid.uuid4())
    wire = _make_wire("sender2", "responder2", sender_ident, req_id)
    with TestClient(app) as client:
        r1 = client.post(
            settings.path,
            json=wire,
            headers={settings.idempotency_header_name: req_id},
        )
        assert r1.status_code == 202
        assert r1.json()["status"] == "accepted"
        r_pending = client.get(f"{settings.path}/{req_id}")
        assert r_pending.status_code == 200
        assert r_pending.json()["status"] == "pending"
        hub.response_tracker.status = "completed"
        hub.response_tracker.message = Message.create(
            sender_id="responder2",
            receiver_id="sender2",
            content="pong",
            sender_identity=AgentIdentity.create_key_based(),
            kind=MessageKind.RESPONSE,
            metadata={"response_to": req_id, "request_id": req_id},
        )
        r2 = client.get(f"{settings.path}/{req_id}")
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["status"] == "completed"
        assert body2["response"]["kind"] == MessageKind.RESPONSE.value
        assert body2["response"]["content"] == "pong"
