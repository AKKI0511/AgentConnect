import json
import os

import pytest
from fastapi.testclient import TestClient

from agentconnect.index.service import create_registry_api_app
from agentconnect.config.servers import RegistryAPISettings
from agentconnect.team.directory.registry_base import AgentRegistry


def _clear_registry_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in list(os.environ.keys()):
        if k.startswith("AGENTCONNECT_REGISTRY_"):
            monkeypatch.delenv(k, raising=False)


def _monkeypatch_fast_registry_init(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fast_init(self):  # type: ignore[unused-argument]
        # Set initialized flag without heavy work
        try:
            self._initialized_event.set()
        except Exception:
            pass

    async def _noop(self):  # type: ignore[unused-argument]
        return

    # Avoid model downloads / network
    monkeypatch.setattr(
        AgentRegistry, "_initialize_vector_search", _fast_init, raising=True
    )
    monkeypatch.setattr(AgentRegistry, "ensure_initialized", _noop, raising=False)


def test_app_starts_with_defaults(monkeypatch: pytest.MonkeyPatch):
    _clear_registry_env(monkeypatch)
    _monkeypatch_fast_registry_init(monkeypatch)

    settings = RegistryAPISettings()
    app = create_registry_api_app(settings)

    # Enter lifespan without errors
    with TestClient(app) as client:
        # App exposes resolved settings for host environments
        assert hasattr(app.state, "registry_settings")

        # OpenAPI should be available for FastAPI apps
        openapi_res = client.get("/openapi.json")
        assert openapi_res.status_code == 200
        openapi = openapi_res.json()
        assert isinstance(openapi, dict) and "paths" in openapi

        # Health may exist; if so, should return 200
        resp = client.get("/health")
        if resp.status_code == 200:
            assert resp.json() and isinstance(resp.json(), dict)
        else:
            # If route not present, ensure routing is operational via a controlled 404
            resp_404 = client.get("/__nonexistent__")
            assert resp_404.status_code == 404


def test_app_starts_with_env_overrides_and_cors_json(monkeypatch: pytest.MonkeyPatch):
    _clear_registry_env(monkeypatch)
    _monkeypatch_fast_registry_init(monkeypatch)

    origins = ["https://a.example", "https://b.example"]
    monkeypatch.setenv("AGENTCONNECT_REGISTRY_ALLOWED_ORIGINS", json.dumps(origins))

    app = create_registry_api_app(None)  # load from env
    with TestClient(app) as client:
        # Lifespan should enter fine
        res = client.get("/health")
        assert res.status_code in (200, 404)

        # Preflight OPTIONS should reflect allowed origin when present
        origin = origins[0]
        preflight = client.options(
            "/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS middleware should allow the origin
        assert preflight.headers.get("access-control-allow-origin") == origin


def test_app_starts_with_env_overrides_and_cors_csv(monkeypatch: pytest.MonkeyPatch):
    _clear_registry_env(monkeypatch)
    _monkeypatch_fast_registry_init(monkeypatch)

    csv_value = "https://x.example,https://y.example"
    monkeypatch.setenv("AGENTCONNECT_REGISTRY_ALLOWED_ORIGINS", csv_value)

    app = create_registry_api_app(None)  # load from env
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code in (200, 404)

        origin = "https://y.example"
        preflight = client.options(
            "/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert preflight.headers.get("access-control-allow-origin") == origin
