import logging

import pytest

from agentconnect.servers.config import RegistryAPISettings
from agentconnect.servers.registry_api_server import create_registry_api_app
from agentconnect.core.registry.registry_base import AgentRegistry


@pytest.mark.asyncio
async def test_logging_levels_are_set_without_handler_churn(monkeypatch):
    # Snapshot handler counts before app startup
    root_logger = logging.getLogger()
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_access_logger = logging.getLogger("uvicorn.access")

    initial_counts = {
        "root": len(root_logger.handlers),
        "uvicorn": len(uvicorn_logger.handlers),
        "uvicorn.error": len(uvicorn_error_logger.handlers),
        "uvicorn.access": len(uvicorn_access_logger.handlers),
    }
    original_levels = {
        "root": root_logger.level,
        "uvicorn": uvicorn_logger.level,
        "uvicorn.error": uvicorn_error_logger.level,
        "uvicorn.access": uvicorn_access_logger.level,
    }

    # Prevent heavy background initialization (no model downloads, no network)
    async def _fast_init(self):  # type: ignore[no-redef]
        self._initialized_event.set()

    async def _noop(self):  # type: ignore[no-redef]
        return

    monkeypatch.setattr(AgentRegistry, "_initialize_vector_search", _fast_init, raising=True)
    monkeypatch.setattr(AgentRegistry, "ensure_initialized", _noop, raising=False)

    try:
        for level_name in ["INFO", "DEBUG"]:
            settings = RegistryAPISettings(log_level=level_name)
            app = create_registry_api_app(settings)

            # Trigger lifespan to apply logging level alignment
            async with app.router.lifespan_context(app):
                pass

            expected_level = getattr(logging, level_name)

            assert logging.getLogger().level == expected_level
            assert logging.getLogger("uvicorn").level == expected_level
            assert logging.getLogger("uvicorn.error").level == expected_level
            assert logging.getLogger("uvicorn.access").level == expected_level

        # Ensure no handler was added/removed by lifespan
        assert len(root_logger.handlers) == initial_counts["root"]
        assert len(uvicorn_logger.handlers) == initial_counts["uvicorn"]
        assert len(uvicorn_error_logger.handlers) == initial_counts["uvicorn.error"]
        assert len(uvicorn_access_logger.handlers) == initial_counts["uvicorn.access"]
    finally:
        # Restore original levels to avoid impacting other tests
        logging.getLogger().setLevel(original_levels["root"])
        logging.getLogger("uvicorn").setLevel(original_levels["uvicorn"])
        logging.getLogger("uvicorn.error").setLevel(original_levels["uvicorn.error"])
        logging.getLogger("uvicorn.access").setLevel(original_levels["uvicorn.access"])
