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
    for name in [
        "qdrant_client",
        "fastembed",
        "sentence_transformers",
        "langchain_huggingface",
    ]:
        sys.modules.pop(name, None)

    mod = importlib.import_module("agentconnect.index.registry.capability_discovery")
    assert hasattr(mod, "CapabilityDiscoveryService")


def test_import_team_directory_without_torch_or_qdrant(monkeypatch):
    for name in [
        "torch",
        "sentence_transformers",
        "fastembed",
        "qdrant_client",
        "litellm",
    ]:
        sys.modules.pop(name, None)

    mod = importlib.import_module("agentconnect.team.directory")
    assert hasattr(mod, "Directory")
    assert hasattr(mod, "HashedEmbedder")


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
    from agentconnect.core.identity import AgentIdentity
    from agentconnect.core.profile import AgentProfile, Skill

    class DummyAgent(BaseAgent):
        def _initialize_llm(self):
            return None

        def _initialize_workflow(self):
            return None

        async def process_message(self, message, ctx=None):
            return None

    profile = AgentProfile(
        summary="Test agent for import safety.",
        skills=[Skill(name="x", description="Handles a tiny test skill.")],
    )
    identity = AgentIdentity.create_key_based()
    agent = DummyAgent(
        agent_id="test_agent",
        identity=identity,
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
    from agentconnect.core.identity import AgentIdentity
    from agentconnect.core.profile import AgentProfile, Skill

    class DummyAgent(BaseAgent):
        def _initialize_llm(self):
            return None

        def _initialize_workflow(self):
            return None

        async def process_message(self, message, ctx=None):
            return None

    profile = AgentProfile(
        summary="Test agent for import safety.",
        skills=[Skill(name="x", description="Handles a tiny test skill.")],
    )
    identity = AgentIdentity.create_key_based()

    # Should not raise even if optional deps are missing; agent disables payments internally
    agent = DummyAgent(
        agent_id="test_agent",
        identity=identity,
        profile=profile,
        enable_payments=True,
    )

    # Since deps are missing, lazy import path should fail internally and disable payments
    assert agent.wallet_provider is None and agent.agent_kit is None


def test_prebuilt_ai_agent_does_not_import_langchain():
    for name in list(sys.modules):
        if name == "langchain" or name.startswith("langchain"):
            sys.modules.pop(name, None)
    importlib.import_module("agentconnect.prebuilt.ai_agent")
    loaded = [
        name
        for name in sys.modules
        if name == "langchain" or name.startswith("langchain")
    ]
    assert loaded == []


def test_core_types_has_no_model_enums():
    types_mod = importlib.import_module("agentconnect.core.types")
    assert not hasattr(types_mod, "ModelProvider")
    assert not hasattr(types_mod, "ModelName")


def test_human_agent_imports_without_aioconsole():
    sys.modules.pop("agentconnect.prebuilt.human_agent", None)
    sys.modules.pop("aioconsole", None)
    mod = importlib.import_module("agentconnect.prebuilt.human_agent")
    assert hasattr(mod, "HumanAgent")
    assert "aioconsole" not in sys.modules


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
        "agentconnect.mcp.communication_mcp_server",
        "agentconnect.mcp.registry_mcp_server",
        "agentconnect.mcp.token_verifier",
        "agentconnect.cli.mcp",
        "agentconnect.cli.config",
        "agentconnect.cli.serve",
        "agentconnect.cli.registry",
        "agentconnect.providers",
        "agentconnect.prompts",
    ]:
        sys.modules.pop(name, None)
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            continue
        raise AssertionError(f"{name} should not exist")
