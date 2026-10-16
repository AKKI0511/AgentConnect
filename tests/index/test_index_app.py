"""Index client, app, and roster behavior."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agentconnect.core.identity import AgentIdentity
from agentconnect.core.profile import Skill
from agentconnect.index.client import IndexClient
from agentconnect.index.models import (
    AgentRegistration,
    IndexQuery,
    RegistrationUpdate,
)
from agentconnect.index.service import create_index_app
from agentconnect.index._registry import Registry


def _record(
    agent_id: str, *, summary: str, tags: list[str] | None = None
) -> AgentRegistration:
    return AgentRegistration(
        agent_id=agent_id,
        identity=AgentIdentity.create_key_based(),
        name=agent_id,
        summary=summary,
        skills=[Skill(name="drafting", description="Drafts release notes.")],
        tags=tags or [],
    )


@pytest.mark.asyncio
async def test_http_client_crud_search_and_secret() -> None:
    app = create_index_app()
    record = _record(
        "writer", summary="Drafts release notes from findings.", tags=["notes"]
    )
    with TestClient(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://index"
        ) as raw:
            client = IndexClient("http://index")
            await client._client.aclose()
            client._client = raw
            stored = await client.register(record)
            assert "private_key" not in stored.model_dump_json()
            assert stored.identity.private_key is None
            fetched = await client.get_registration("writer")
            assert fetched is not None and fetched.summary.startswith("Drafts")
            updated = await client.update_registration(
                "writer",
                RegistrationUpdate(summary="Reviews invoices.", tags=["billing"]),
            )
            assert updated.name == "writer"
            assert updated.summary == "Reviews invoices."
            hits = await client.search(IndexQuery(query="invoices", tags=["billing"]))
            assert [hit.registration.agent_id for hit in hits] == ["writer"]
            assert (
                await client.search(IndexQuery(query="invoices", tags=["notes"])) == []
            )
            await client.unregister("writer")
            assert await client.get_registration("writer") is None
            with pytest.raises(httpx.HTTPStatusError) as raised:
                await client.unregister("writer")
            assert raised.value.response.status_code == 404


def test_two_apps_stay_independent_while_both_are_open() -> None:
    first = create_index_app()
    second = create_index_app()
    record = _record("writer", summary="Drafts release notes.")
    with TestClient(second) as other:
        with TestClient(first) as primary:
            created = primary.post(
                "/agents/register", json=record.model_dump(mode="json")
            )
            assert created.status_code == 201
            assert "private_key" not in created.text
            assert other.get("/agents/writer").status_code == 404
            assert primary.get("/agents/writer").status_code == 200
        assert other.get("/health").status_code == 200
        assert other.get("/agents/writer").status_code == 404
        assert (
            other.post(
                "/agents/register",
                json=_record("other", summary="Reviews invoices.").model_dump(
                    mode="json"
                ),
            ).status_code
            == 201
        )


@pytest.mark.asyncio
async def test_serialized_update_then_reregister_keeps_the_new_identity() -> None:
    registry = Registry()
    await registry.open()
    original = await registry.register(
        _record("writer", summary="Drafts release notes.")
    )
    replacement = _record("writer", summary="Reviews invoices.")
    assert original.identity.did != replacement.identity.did

    from agentconnect.team.directory.embedder import HashedEmbedder

    hashed = HashedEmbedder()

    class _GateEmbed:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.calls = 0

        async def embed(self, texts: list[str]) -> list[list[float]]:
            self.calls += 1
            if self.calls == 1:
                self.started.set()
                await self.release.wait()
            return await hashed.embed(texts)

    gate = _GateEmbed()
    registry._embedder = gate
    pending = asyncio.create_task(
        registry.update("writer", RegistrationUpdate(summary="Changed while waiting."))
    )
    await gate.started.wait()

    async def _replace() -> None:
        await registry.unregister("writer")
        await registry.register(replacement)

    replacer = asyncio.create_task(_replace())
    await asyncio.sleep(0)
    gate.release.set()
    await pending
    await replacer
    current = await registry.get_registration("writer")
    assert current is not None
    assert current.identity.did == replacement.identity.did
    assert current.summary == "Reviews invoices."


@pytest.mark.asyncio
async def test_cancelled_update_and_input_mutation_do_not_change_the_roster() -> None:
    registry = Registry()
    await registry.open()
    incoming = _record("writer", summary="Drafts release notes.", tags=["notes"])
    stored = await registry.register(incoming)
    incoming.summary = "mutated input"
    incoming.tags.append("extra")
    incoming.identity.metadata["leak"] = "yes"
    current = await registry.get_registration("writer")
    assert current is not None
    assert current.summary == "Drafts release notes."
    assert current.tags == ["notes"]
    assert "leak" not in current.identity.metadata
    stored.summary = "mutated result"
    stored.tags.append("nope")
    again = await registry.get_registration("writer")
    assert again is not None and again.summary == "Drafts release notes."
    assert again.tags == ["notes"]

    class _Cancel:
        async def embed(self, texts: list[str]) -> list[list[float]]:
            raise asyncio.CancelledError

    registry._embedder = _Cancel()
    with pytest.raises(asyncio.CancelledError):
        await registry.update("writer", RegistrationUpdate(summary="Changed."))
    after = await registry.get_registration("writer")
    assert after is not None and after.summary == "Drafts release notes."


def test_invalid_identity_and_bad_id_are_client_errors() -> None:
    with pytest.raises(ValidationError):
        AgentRegistration.model_validate(
            {"agent_id": "writer", "identity": {"public_key": "x"}}
        )
    with pytest.raises(ValidationError):
        AgentRegistration(agent_id="a/b", identity=AgentIdentity.create_key_based())
    with pytest.raises(ValidationError):
        RegistrationUpdate.model_validate({"skills": None})
    RegistrationUpdate.model_validate({"name": None, "tags": []})
    app = create_index_app()
    with TestClient(app) as client:
        response = client.get("/agents/a.b")
        assert response.status_code == 400
        with pytest.raises(ValueError):
            asyncio.run(IndexClient("http://index").get_registration("a/b"))


@pytest.mark.asyncio
async def test_client_retries_reads_only_and_rejects_a_bad_body() -> None:
    record = _record("writer", summary="Drafts release notes.")
    calls = {"n": 0}

    class _Fake:
        async def request(
            self, method: str, path: str, json: object = None
        ) -> httpx.Response:
            calls["n"] += 1
            request = httpx.Request(method, "http://index/" + path)
            if method == "GET" and calls["n"] == 1:
                return httpx.Response(503, request=request)
            if method == "GET" and calls["n"] == 2:
                return httpx.Response(
                    200, json=record.model_dump(mode="json"), request=request
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
    assert calls["n"] == 2
    calls["n"] = 0
    with pytest.raises(httpx.HTTPStatusError):
        await client.register(record)
    assert calls["n"] == 1
    with pytest.raises(ValueError):
        await client.search(IndexQuery(query="release notes"))


def test_duplicate_register_is_conflict() -> None:
    app = create_index_app()
    body = _record("writer", summary="Drafts release notes.").model_dump(mode="json")
    with TestClient(app) as client:
        assert client.post("/agents/register", json=body).status_code == 201
        assert client.post("/agents/register", json=body).status_code == 409


@pytest.mark.asyncio
async def test_missing_endpoint_is_not_an_absent_registration() -> None:
    async with IndexClient("http://index") as client:
        await client._client.aclose()
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(404, json={"detail": "Not Found"})
            ),
            base_url="http://index",
        )
        with pytest.raises(httpx.HTTPStatusError) as raised:
            await client.get_registration("writer")
        assert raised.value.response.status_code == 404


@pytest.mark.asyncio
async def test_concurrent_partial_updates_preserve_both_fields() -> None:
    registry = Registry()
    await registry.open()
    await registry.register(_record("writer", summary="Drafts release notes."))
    from agentconnect.team.directory.embedder import HashedEmbedder

    started = asyncio.Event()
    release = asyncio.Event()
    hashed = HashedEmbedder()

    class Gate:
        async def embed(self, texts: list[str]) -> list[list[float]]:
            started.set()
            await release.wait()
            return await hashed.embed(texts)

    registry._embedder = Gate()
    first = asyncio.create_task(
        registry.update("writer", RegistrationUpdate(summary="Reviews invoices."))
    )
    await started.wait()
    second = asyncio.create_task(
        registry.update("writer", RegistrationUpdate(tags=["billing"]))
    )
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(first, second)
    current = await registry.get_registration("writer")
    assert current is not None
    assert current.summary == "Reviews invoices."
    assert current.tags == ["billing"]
