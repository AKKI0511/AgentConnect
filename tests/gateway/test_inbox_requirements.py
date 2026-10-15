import uuid

import pytest
from fastapi.testclient import TestClient

from agentconnect.core.identity import AgentIdentity
from agentconnect.core.kinds import MessageKind
from agentconnect.config.servers import InboxServerSettings
from agentconnect.gateway.inbound import create_agent_inbox_app
from agentconnect.index.registry import AgentRegistry, AgentRegistration
from agentconnect.index.types import AgentType, InteractionMode
from agentconnect.transport.envelope import CollaborationMessage as Message
from tests.gateway.conftest import InboxFacade


class _Registry(AgentRegistry):
    async def _initialize_vector_search(self):
        return None

    async def ensure_initialized(self):
        return True


def _wire(sender: str, receiver: str, ident: AgentIdentity, req_id: str | None = None):
    msg = Message.create(
        sender_id=sender,
        receiver_id=receiver,
        content="ping",
        sender_identity=ident,
        kind=MessageKind.REQUEST,
        metadata={"request_id": req_id or str(uuid.uuid4())},
    )
    return msg.to_wire_dict()


@pytest.mark.asyncio
async def test_post_400_when_idempotency_header_required_and_missing():
    reg = _Registry()
    hub = InboxFacade(reg)
    settings = InboxServerSettings(require_auth=False, require_idempotency_header=True)
    app = create_agent_inbox_app(hub, settings)

    ident = AgentIdentity.create_key_based()
    await reg.register(
        AgentRegistration(
            agent_id="s1",
            agent_type=AgentType.AI,
            interaction_modes=[InteractionMode.AGENT_TO_AGENT],
            identity=ident,
            url="http://remote",
        )
    )

    wire = _wire("s1", "r1", ident)
    with TestClient(app) as client:
        r = client.post(settings.path, json=wire)
        assert r.status_code == 400
        assert r.json().get("detail") == "Missing idempotency header"


@pytest.mark.asyncio
async def test_idempotency_conflict_when_header_reused_with_different_request_id():
    reg = _Registry()
    hub = InboxFacade(reg)
    settings = InboxServerSettings(require_auth=False, require_idempotency_header=True)
    app = create_agent_inbox_app(hub, settings)

    ident = AgentIdentity.create_key_based()
    await reg.register(
        AgentRegistration(
            agent_id="s2",
            agent_type=AgentType.AI,
            interaction_modes=[InteractionMode.AGENT_TO_AGENT],
            identity=ident,
            url="http://remote",
        )
    )

    idem = "idem-1"
    req_a = str(uuid.uuid4())
    wire_a = _wire("s2", "r2", ident, req_a)
    # Create a second wire envelope with the same signature content except request_id changes
    req_b = str(uuid.uuid4())
    wire_b = _wire("s2", "r2", ident, req_b)

    with TestClient(app) as client:
        r1 = client.post(
            settings.path, json=wire_a, headers={settings.idempotency_header_name: idem}
        )
        assert r1.status_code in (200, 202)
        r2 = client.post(
            settings.path, json=wire_b, headers={settings.idempotency_header_name: idem}
        )
        assert r2.status_code == 409
        assert r2.json().get("detail") == "Idempotency conflict"


@pytest.mark.asyncio
async def test_idempotency_replay_returns_same_completed_response():
    reg = _Registry()
    hub = InboxFacade(reg)
    settings = InboxServerSettings(require_auth=False, require_idempotency_header=True)
    app = create_agent_inbox_app(hub, settings)

    ident = AgentIdentity.create_key_based()
    await reg.register(
        AgentRegistration(
            agent_id="s3",
            agent_type=AgentType.AI,
            interaction_modes=[InteractionMode.AGENT_TO_AGENT],
            identity=ident,
            url="http://remote",
        )
    )

    async def _check_completed(req_id):
        resp = Message.create(
            "s3", "rX", "ok", ident, MessageKind.RESPONSE, {"response_to": req_id}
        )
        return "completed", resp

    hub.response_tracker.check = _check_completed  # type: ignore

    idem = "idem-2"
    req_id = str(uuid.uuid4())
    wire = _wire("s3", "rX", ident, req_id)
    with TestClient(app) as client:
        r1 = client.post(
            settings.path, json=wire, headers={settings.idempotency_header_name: idem}
        )
        assert r1.status_code == 200
        body1 = r1.json()
        assert body1.get("status") == "completed"
        r2 = client.post(
            settings.path, json=wire, headers={settings.idempotency_header_name: idem}
        )
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2 == body1


@pytest.mark.asyncio
async def test_allowed_senders_forbidden_when_sender_not_in_list():
    reg = _Registry()
    hub = InboxFacade(reg)
    settings = InboxServerSettings(require_auth=False, allowed_senders=["s"])
    app = create_agent_inbox_app(hub, settings)

    ident = AgentIdentity.create_key_based()
    await reg.register(
        AgentRegistration(
            agent_id="t",
            agent_type=AgentType.AI,
            interaction_modes=[InteractionMode.AGENT_TO_AGENT],
            identity=ident,
            url="http://remote",
        )
    )

    wire = _wire("t", "r3", ident)
    with TestClient(app) as client:
        r = client.post(
            settings.path,
            json=wire,
            headers={settings.idempotency_header_name: wire["metadata"]["request_id"]},
        )
        assert r.status_code == 403
        assert r.json().get("detail") == "Sender not allowed"
