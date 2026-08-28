import pytest

from agentconnect.agent.base import BaseAgent
from agentconnect.core.message import Message
from agentconnect.core.types import (
    AgentIdentity,
    AgentProfile,
    AgentType,
    InteractionMode,
)
from agentconnect.team.directory.registry_base import AgentRegistry
from agentconnect.team.directory.registration import AgentRegistration
from agentconnect.mcp.token_verifier import MCPRegistryTokenVerifier
from agentconnect.mcp.communication_mcp_server import create_communication_mcp
from types import SimpleNamespace
from agentconnect.config.models import MCPCommunicationSettings
from agentconnect.core.identity import encode_eddsa_jwt
import time
import uuid


class _DummyAgent(BaseAgent):
    def _initialize_llm(self):
        return None

    def _initialize_workflow(self):
        return None

    async def process_message(self, message: Message):
        return None


class EmptyCapabilityDiscovery:
    """Empty stub for capability discovery (no-op for tests)."""

    async def initialize_embeddings_model(self):
        return None

    async def update_capability_embeddings_cache(self, registration):
        return None

    async def clear_agent_embeddings_cache(self, agent_id: str):
        return None


# Use this for fast startup tests
class _Registry(AgentRegistry):
    def __init__(self):
        super().__init__()
        self._capability_discovery = EmptyCapabilityDiscovery()

    async def _initialize_vector_search(self):
        return None

    async def ensure_initialized(self):
        return True


@pytest.mark.asyncio
async def test_token_verifier_valid_jwt_returns_access_token():
    registry = _Registry()
    ident = AgentIdentity.create_key_based()
    agent = _DummyAgent(
        agent_id="agent_valid",
        identity=ident,
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
        profile=AgentProfile(agent_id="agent_valid", agent_type=AgentType.AI),
    )
    await registry.register(
        AgentRegistration(
            agent_id=agent.agent_id,
            agent_type=AgentType.AI,
            interaction_modes=[InteractionMode.AGENT_TO_AGENT],
            identity=ident,
        )
    )

    token = agent.mint_mcp_access_token(audience="http://localhost:8001/mcp", ttl_s=300)
    verifier = MCPRegistryTokenVerifier(
        registry, expected_audience="http://localhost:8001/mcp"
    )

    access = await verifier.verify_token(token)
    assert access is not None
    assert access.client_id == agent.agent_id

    # Also ensure server can be created with auth configured
    hub = SimpleNamespace(registry=registry)
    from agentconnect.config import settings

    settings.mcp.communication.auth = MCPCommunicationSettings.Auth(
        resource_server_url="http://localhost:8001/mcp",
        issuer_url="http://localhost:8001",
        required_scopes=None,
        service_documentation_url=None,
    )
    mcp = create_communication_mcp(hub)
    assert mcp is not None


@pytest.mark.asyncio
async def test_token_verifier_parses_scope_and_scp_claims():
    registry = _Registry()
    ident = AgentIdentity.create_key_based()
    agent = _DummyAgent(
        agent_id="agent_scopes",
        identity=ident,
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
        profile=AgentProfile(agent_id="agent_scopes", agent_type=AgentType.AI),
    )
    await registry.register(
        AgentRegistration(
            agent_id=agent.agent_id,
            agent_type=AgentType.AI,
            interaction_modes=[InteractionMode.AGENT_TO_AGENT],
            identity=ident,
        )
    )

    now = int(time.time())
    claims = {
        "sub": agent.agent_id,
        "aud": "http://localhost:8001/mcp",
        "iat": now,
        "exp": now + 300,
        "jti": str(uuid.uuid4()),
        "scope": "read:inbox write:inbox",
        "scp": ["extra:perm"],
    }
    token = encode_eddsa_jwt(claims, ident.private_key)

    verifier = MCPRegistryTokenVerifier(
        registry, expected_audience="http://localhost:8001/mcp"
    )
    access = await verifier.verify_token(token)
    assert access is not None
    # Both sources included; duplicates allowed; order not guaranteed beyond our concatenation choices
    assert "read:inbox" in access.scopes
    assert "write:inbox" in access.scopes
    assert "extra:perm" in access.scopes


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    [
        "invalid_signature",
        "wrong_audience",
        "expired",
    ],
)
async def test_token_verifier_negative_scenarios(scenario: str):
    registry = _Registry()
    if scenario == "invalid_signature":
        ident_a = AgentIdentity.create_key_based()
        await registry.register(
            AgentRegistration(
                agent_id="agent_a",
                agent_type=AgentType.AI,
                interaction_modes=[InteractionMode.AGENT_TO_AGENT],
                identity=ident_a,
            )
        )
        ident_b = AgentIdentity.create_key_based()
        fake_agent = _DummyAgent(
            agent_id="agent_a",
            identity=ident_b,
            interaction_modes=[InteractionMode.AGENT_TO_AGENT],
            profile=AgentProfile(agent_id="agent_a", agent_type=AgentType.AI),
        )
        token = fake_agent.mint_mcp_access_token(
            audience="http://localhost:8001/mcp", ttl_s=300
        )
        verifier = MCPRegistryTokenVerifier(
            registry, expected_audience="http://localhost:8001/mcp"
        )
        access = await verifier.verify_token(token)
        assert access is None
    elif scenario == "wrong_audience":
        ident = AgentIdentity.create_key_based()
        await registry.register(
            AgentRegistration(
                agent_id="agent_wrong_aud",
                agent_type=AgentType.AI,
                interaction_modes=[InteractionMode.AGENT_TO_AGENT],
                identity=ident,
            )
        )
        agent = _DummyAgent(
            agent_id="agent_wrong_aud",
            identity=ident,
            interaction_modes=[InteractionMode.AGENT_TO_AGENT],
            profile=AgentProfile(agent_id="agent_wrong_aud", agent_type=AgentType.AI),
        )
        token = agent.mint_mcp_access_token(audience="http://not-this", ttl_s=300)
        verifier = MCPRegistryTokenVerifier(
            registry, expected_audience="http://localhost:8001/mcp"
        )
        access = await verifier.verify_token(token)
        assert access is None
    else:
        ident = AgentIdentity.create_key_based()
        await registry.register(
            AgentRegistration(
                agent_id="agent_expired",
                agent_type=AgentType.AI,
                interaction_modes=[InteractionMode.AGENT_TO_AGENT],
                identity=ident,
            )
        )
        agent = _DummyAgent(
            agent_id="agent_expired",
            identity=ident,
            interaction_modes=[InteractionMode.AGENT_TO_AGENT],
            profile=AgentProfile(agent_id="agent_expired", agent_type=AgentType.AI),
        )
        token = agent.mint_mcp_access_token(
            audience="http://localhost:8001/mcp", ttl_s=-5
        )
        verifier = MCPRegistryTokenVerifier(
            registry, expected_audience="http://localhost:8001/mcp"
        )
        access = await verifier.verify_token(token)
        assert access is None
