"""ASGI app for one in-memory Index.

[`create_index_app`][agentconnect.index.service.create_index_app] returns a
FastAPI app. `python -m agentconnect.index.service` loads
[`IndexSettings`][agentconnect.index.models.IndexSettings] and listens on
loopback. Records disappear when the process stops.

The app does not check who is writing. Keep the built-in server on
loopback, or put your own access control in front of the app before any
other host can reach it.
"""

from __future__ import annotations

import ipaddress
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from agentconnect.core.address import parse_agent_name
from agentconnect.core.base import JsonObject
from agentconnect.index._registry import DuplicateRegistration, Registry
from agentconnect.index.models import (
    AgentRegistration,
    IndexQuery,
    IndexSearchHit,
    IndexSettings,
    RegistrationUpdate,
)


def _loopback(host: str) -> bool:
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _identifier(agent_id: str) -> str:
    canonical = parse_agent_name(agent_id)
    if canonical is None:
        raise HTTPException(
            status_code=400,
            detail="agent_id must be 1-63 ASCII letters, digits, '_' or '-'",
        )
    return canonical


def create_index_app(settings: Optional[IndexSettings] = None) -> FastAPI:
    """Return an ASGI app that owns one Index roster.

    Each app has its own records. Closing the app drops that roster.
    Install `agentconnect[index]` before serving.
    """

    resolved = settings or IndexSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        registry = Registry(resolved.model_name)
        try:
            await registry.open()
        except Exception as exc:
            raise RuntimeError(
                f"Index embedder {resolved.model_name!r} failed to load"
            ) from exc
        app.state.registry = registry
        try:
            yield
        finally:
            app.state.registry = None

    app = FastAPI(title="AgentConnect Index", version="0.5.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.registry_settings = resolved
    app.include_router(_routes())
    return app


def _registry(request: Request) -> Registry:
    registry = getattr(request.app.state, "registry", None)
    if not isinstance(registry, Registry):
        raise HTTPException(status_code=503, detail="Index is not ready")
    return registry


def _routes() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health(request: Request) -> dict[str, str]:
        """Report that this app's roster is open."""
        _registry(request)
        return {"status": "ok"}

    @router.post("/agents/register", status_code=201)
    async def register(
        registration: AgentRegistration, request: Request
    ) -> AgentRegistration:
        """Store one record. A repeated id is HTTP 409."""
        try:
            return await _registry(request).register(registration)
        except DuplicateRegistration as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.get("/agents/{agent_id}")
    async def get_agent(agent_id: str, request: Request) -> AgentRegistration:
        """Return one stored record. An unknown id is HTTP 404."""
        found = await _registry(request).get_registration(_identifier(agent_id))
        if found is None:
            raise HTTPException(status_code=404, detail="registration not found")
        return found

    @router.get("/agents")
    async def list_agents(request: Request) -> list[AgentRegistration]:
        """Return every record this app is holding."""
        return await _registry(request).list_registrations()

    @router.put("/agents/{agent_id}")
    async def update_agent(
        agent_id: str, updates: RegistrationUpdate, request: Request
    ) -> AgentRegistration:
        """Replace the listed fields. An unknown id is HTTP 404."""
        try:
            updated = await _registry(request).update(_identifier(agent_id), updates)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        if updated is None:
            raise HTTPException(status_code=404, detail="registration not found")
        return updated

    @router.delete("/agents/{agent_id}")
    async def delete_agent(agent_id: str, request: Request) -> JsonObject:
        """Remove one record. An unknown id is HTTP 404."""
        if not await _registry(request).unregister(_identifier(agent_id)):
            raise HTTPException(status_code=404, detail="registration not found")
        return {"agent_id": _identifier(agent_id)}

    @router.post("/agents/search")
    async def search(query: IndexQuery, request: Request) -> list[IndexSearchHit]:
        """Rank current records. Unknown body fields are HTTP 422."""
        try:
            return await _registry(request).search(query)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return router


app = create_index_app()


if __name__ == "__main__":
    import uvicorn

    _settings = IndexSettings()
    if not _loopback(_settings.host):
        raise SystemExit("The built-in Index server listens on loopback only.")
    uvicorn.run(
        app,
        host=_settings.host,
        port=_settings.port,
        log_level=_settings.log_level.lower(),
    )
