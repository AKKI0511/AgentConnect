"""Lean Index coverage for CI: models, hashed roster, and client retries."""

from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from agentconnect.core.identity import AgentIdentity
from agentconnect.core.profile import Skill
from agentconnect.index._registry import DuplicateRegistration, Registry
from agentconnect.index.client import IndexClient
from agentconnect.index.models import (
    AgentRegistration,
    IndexQuery,
    IndexSettings,
    RegistrationUpdate,
)
from agentconnect.index.service import create_index_app

_IDENTITY = AgentIdentity.create_key_based()


def _record(
    agent_id: str, *, summary: str, tags: list[str] | None = None
) -> AgentRegistration:
    return AgentRegistration(
        agent_id=agent_id,
        identity=_IDENTITY,
        name=agent_id,
        summary=summary,
        skills=[Skill(name="drafting", description="Drafts release notes.")],
        tags=tags or [],
    )


@pytest.mark.asyncio
async def test_registry_register_search_and_secret() -> None:
    registry = Registry("hashed")
    await registry.open()
    stored = await registry.register(
        _record("writer", summary="Drafts release notes from findings.", tags=["notes"])
    )
    assert stored.identity.private_key is None
    hits = await registry.search(IndexQuery(query="release notes", tags=["notes"]))
    assert [hit.registration.agent_id for hit in hits] == ["writer"]
    assert (
        await registry.search(IndexQuery(query="release notes", tags=["billing"])) == []
    )
    with pytest.raises(DuplicateRegistration):
        await registry.register(_record("writer", summary="again"))
    assert await registry.unregister("writer")
    assert await registry.get_registration("writer") is None


@pytest.mark.asyncio
async def test_http_register_rejects_duplicates_and_bad_ids() -> None:
    app = create_index_app(IndexSettings(model_name="hashed"))
    body = _record("writer", summary="Drafts release notes.").model_dump(
        mode="json", exclude_none=True
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://index",
        ) as client:
            created = await client.post("/agents/register", json=body)
            assert created.status_code == 201
            assert "private_key" not in created.text
            assert (await client.post("/agents/register", json=body)).status_code == 409
            assert (await client.get("/agents/missing")).status_code == 404
            assert (await client.get("/agents/a.b")).status_code == 400


def test_invalid_records_are_client_errors() -> None:
    with pytest.raises(ValidationError):
        AgentRegistration.model_validate(
            {"agent_id": "writer", "identity": {"public_key": "x"}}
        )
    with pytest.raises(ValidationError):
        AgentRegistration(agent_id="a/b", identity=_IDENTITY)
    with pytest.raises(ValidationError):
        RegistrationUpdate.model_validate({"skills": None})


@pytest.mark.asyncio
async def test_client_writes_are_not_retried_and_rejects_a_bad_body() -> None:
    record = _record("writer", summary="Drafts release notes.")
    calls = {"n": 0}

    class _Fake:
        async def request(
            self, method: str, path: str, json: object = None
        ) -> httpx.Response:
            calls["n"] += 1
            request = httpx.Request(method, "http://index/" + path)
            if method == "GET":
                return httpx.Response(
                    200,
                    json=record.model_dump(mode="json", exclude_none=True),
                    request=request,
                )
            if method == "POST" and path == "agents/search":
                return httpx.Response(200, json={"nope": True}, request=request)
            return httpx.Response(503, request=request)

        async def aclose(self) -> None:
            return None

    client = IndexClient("http://index")
    await client._client.aclose()
    client._client = _Fake()
    found = await client.get_registration("writer")
    assert found is not None and found.agent_id == "writer"
    calls["n"] = 0
    with pytest.raises(httpx.HTTPStatusError):
        await client.register(record)
    assert calls["n"] == 1
    with pytest.raises(ValueError):
        await client.search(IndexQuery(query="release notes"))
