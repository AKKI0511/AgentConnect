"""
AgentConnect Servers (import-safe package)

Run via CLI:
    .. code-block:: bash

        uvicorn agentconnect.servers.registry_api_server:app

Programmatic:
    .. code-block:: python

        from agentconnect.servers.registry_api_server import create_registry_api_app
        from agentconnect.servers.config import RegistryAPISettings

        settings = RegistryAPISettings()
        app = create_registry_api_app(settings)

This package does not perform imports or side effects at package import time.
"""
