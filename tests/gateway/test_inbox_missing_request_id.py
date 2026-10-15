import pytest
from fastapi.testclient import TestClient

from agentconnect.core.identity import AgentIdentity
from agentconnect.core.kinds import MessageKind
from agentconnect.gateway.inbound import create_agent_inbox_app
from tests.gateway.conftest import InboxFacade
from agentconnect.config.servers import InboxServerSettings
from agentconnect.transport.envelope import CollaborationMessage as Message


@pytest.mark.asyncio
async def test_inbox_post_requires_request_id():
    # Minimal hub and registry to allow ingest path; registry isn't used for this validation
    class _Reg:
        async def register(self, *a, **k):
            return True

        async def unregister(self, *a, **k):
            return True

        async def get_registration(self, agent_id: str):
            return type(
                "_R",
                (),
                {"agent_id": agent_id, "identity": AgentIdentity.create_key_based()},
            )()

    hub = InboxFacade(_Reg())
    app = create_agent_inbox_app(
        hub, InboxServerSettings(require_auth=False, require_idempotency_header=False)
    )

    # Build a valid envelope but omit metadata.request_id
    wire = Message.create(
        sender_id="s",
        receiver_id="r",
        content="ping",
        sender_identity=AgentIdentity.create_key_based(),
        kind=MessageKind.REQUEST,
        metadata={},
    ).to_wire_dict()
    # message_type is already serialized to its enum value in to_wire_dict

    with TestClient(app) as client:
        r = client.post("/agentconnect/collaboration", json=wire)
        assert r.status_code == 400
        assert r.json().get("detail") in ("Missing request_id", "Invalid request_id")

    await hub.stop()
