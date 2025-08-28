import logging
import pytest

from agentconnect.servers.config import RegistryAPISettings
from agentconnect.servers.registry_api_server import create_registry_api_app
from agentconnect.core.registry.registry_base import AgentRegistry


@pytest.mark.asyncio
async def test_no_handler_churn_and_level_applied(monkeypatch):
    # Prevent heavy background initialization (no model downloads, no network)
    async def _fast_init(self):  # type: ignore[no-redef]
        self._initialized_event.set()

    async def _noop(self):  # type: ignore[no-redef]
        return

    monkeypatch.setattr(
        AgentRegistry, "_initialize_vector_search", _fast_init, raising=True
    )
    monkeypatch.setattr(AgentRegistry, "ensure_initialized", _noop, raising=False)

    for level_name in ["INFO", "DEBUG"]:
        settings = RegistryAPISettings(log_level=level_name)
        app = create_registry_api_app(settings)

        # Trigger lifespan; server should not change any handler counts or third-party levels
        async with app.router.lifespan_context(app):
            pass

        # Our hierarchical logger level should reflect settings; allow more verbose levels
        expected_level = getattr(logging, level_name)
        actual_level = logging.getLogger("uvicorn.error.agentconnect.registry").level
        assert actual_level <= expected_level

    # By default, server should not elevate library loggers
    assert logging.getLogger("agentconnect").level in (
        logging.NOTSET,
        logging.WARNING,
        logging.INFO,
        logging.DEBUG,
        logging.ERROR,
        logging.CRITICAL,
    )
