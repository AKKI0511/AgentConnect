import importlib
import sys
from types import ModuleType


def test_top_level_import_has_version_and_no_crash():
    mod = importlib.import_module("agentconnect")
    assert hasattr(mod, "__version__")


def test_lazy_submodule_access_core():
    pkg = importlib.import_module("agentconnect")
    core = getattr(pkg, "core")
    assert isinstance(core, ModuleType)


def test_import_core_agent_without_coinbase(monkeypatch):
    # Simulate absence of optional coinbase deps
    for name in [
        "coinbase_agentkit",
        "coinbase_agentkit_langchain",
        "cdp",
    ]:
        sys.modules.pop(name, None)

    mod = importlib.import_module("agentconnect.agent.base")
    assert mod is not None


def test_import_capability_discovery_without_qdrant_and_hf(monkeypatch):
    # Ensure optional deps are not present
    for name in [
        "qdrant_client",
        "langchain_huggingface",
    ]:
        sys.modules.pop(name, None)

    mod = importlib.import_module("agentconnect.team.directory.capability_discovery")
    assert hasattr(mod, "CapabilityDiscoveryService")


def test_server_module_import_without_optional_extras(monkeypatch):
    # Ensure optional extras are not available
    for name in [
        "coinbase_agentkit",
        "coinbase_agentkit_langchain",
        "cdp",
        "jsonschema",
    ]:
        sys.modules.pop(name, None)

    module = importlib.import_module("agentconnect.index.service")
    assert hasattr(module, "app") and module.app is not None


def test_base_agent_does_not_import_coinbase_when_disabled(monkeypatch):
    # Ensure coinbase packages are absent
    for name in [
        "coinbase_agentkit",
        "coinbase_agentkit_langchain",
    ]:
        sys.modules.pop(name, None)

    from agentconnect.agent.base import BaseAgent
    from agentconnect.core.types import (
        AgentIdentity,
        AgentProfile,
        AgentType,
        InteractionMode,
        Capability,
    )

    class DummyAgent(BaseAgent):
        def _initialize_llm(self):
            return None

        def _initialize_workflow(self):
            return None

        async def process_message(self, message):
            return None

    profile = AgentProfile(
        agent_id="test_agent",
        agent_type=AgentType.AI,
        name="Test",
        capabilities=[Capability(name="x", description="y")],
    )
    identity = AgentIdentity.create_key_based()
    agent = DummyAgent(
        agent_id="test_agent",
        identity=identity,
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
        profile=profile,
        enable_payments=False,
    )

    assert agent.wallet_provider is None and agent.agent_kit is None


def test_base_agent_payments_enabled_handles_missing_coinbase(monkeypatch):
    # Purge optional deps to simulate missing installation
    for name in [
        "coinbase_agentkit",
        "coinbase_agentkit_langchain",
        "cdp",
    ]:
        sys.modules.pop(name, None)

    from agentconnect.agent.base import BaseAgent
    from agentconnect.core.types import (
        AgentIdentity,
        AgentProfile,
        AgentType,
        InteractionMode,
        Capability,
    )

    class DummyAgent(BaseAgent):
        def _initialize_llm(self):
            return None

        def _initialize_workflow(self):
            return None

        async def process_message(self, message):
            return None

    profile = AgentProfile(
        agent_id="test_agent",
        agent_type=AgentType.AI,
        name="Test",
        capabilities=[Capability(name="x", description="y")],
    )
    identity = AgentIdentity.create_key_based()

    # Should not raise even if optional deps are missing; agent disables payments internally
    agent = DummyAgent(
        agent_id="test_agent",
        identity=identity,
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
        profile=profile,
        enable_payments=True,
    )

    # Since deps are missing, lazy import path should fail internally and disable payments
    assert agent.wallet_provider is None and agent.agent_kit is None


def test_prebuilt_aiagent_imports_without_optional_helpers():
    for name in ["aiogram", "aioconsole", "cdp"]:
        sys.modules.pop(name, None)

    mod = importlib.import_module("agentconnect.prebuilt")
    assert hasattr(mod, "AIAgent")


def test_removed_legacy_packages():
    importlib.invalidate_caches()
    for name in [
        "agentconnect.communication",
        "agentconnect.communication.protocols",
        "agentconnect.servers",
        "agentconnect.clients",
        "agentconnect.core.agent",
        "agentconnect.core.registry",
    ]:
        sys.modules.pop(name, None)
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            continue
        raise AssertionError(f"{name} should not exist")
