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
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from agentconnect.core.base import dump_public
from agentconnect.core.directory import DirectoryEntry
from agentconnect.core.primitives import QualifiedAddress
from agentconnect.index._registry import Registry
from agentconnect.index.models import IndexSearchHit, IndexSettings

_QUALIFIED_ADDRESS = TypeAdapter(QualifiedAddress)
_MISSING_ENTRY = "entry not found"


class _SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", title="SearchRequest")

    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    tags: list[str] | None = None


def _loopback(host: str) -> bool:
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _address(value: str) -> str:
    try:
        return _QUALIFIED_ADDRESS.validate_python(value)
    except ValidationError:
        raise HTTPException(
            status_code=400,
            detail="address must be a canonical qualified Address",
        ) from None


def _entry_json(entry: DirectoryEntry, *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(dump_public(entry), status_code=status_code)


def _hits_json(hits: list[IndexSearchHit]) -> JSONResponse:
    return JSONResponse(
        [{"entry": dump_public(hit.entry), "score": hit.score} for hit in hits]
    )


def create_index_app(settings: Optional[IndexSettings] = None) -> FastAPI:
    """Return an ASGI app that owns one Index roster.

    Each app has its own snapshots. Closing the app drops that roster.
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

    @router.put("/entries/{address}", response_model=DirectoryEntry)
    async def put_entry(
        address: str, entry: DirectoryEntry, request: Request
    ) -> JSONResponse:
        """Insert or replace one snapshot. A repeated Address overwrites."""
        path_address = _address(address)
        if entry.address != path_address:
            raise HTTPException(
                status_code=400,
                detail="path address must match entry.address",
            )
        try:
            stored = await _registry(request).put(entry)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return _entry_json(stored)

    @router.get("/entries/{address}", response_model=DirectoryEntry)
    async def get_entry(address: str, request: Request) -> JSONResponse:
        """Return one stored snapshot. An unknown Address is HTTP 404."""
        found = await _registry(request).get(_address(address))
        if found is None:
            raise HTTPException(status_code=404, detail=_MISSING_ENTRY)
        return _entry_json(found)

    @router.get("/entries", response_model=list[DirectoryEntry])
    async def list_entries(request: Request) -> JSONResponse:
        """Return every snapshot this app is holding."""
        return JSONResponse(dump_public(await _registry(request).list()))

    @router.delete("/entries/{address}", status_code=204)
    async def delete_entry(address: str, request: Request) -> Response:
        """Remove one snapshot. A missing Address still succeeds."""
        await _registry(request).delete(_address(address))
        return Response(status_code=204)

    @router.post("/search", response_model=list[IndexSearchHit])
    async def search(body: _SearchRequest, request: Request) -> JSONResponse:
        """Rank current snapshots. Unknown body fields are HTTP 422."""
        try:
            hits = await _registry(request).search(
                body.query, limit=body.limit, tags=body.tags
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return _hits_json(hits)

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
