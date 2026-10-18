"""Lean Index coverage: DirectoryEntry roster, hashed search, and client retries."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from urllib.parse import quote

import httpx
import pytest
from pydantic import ValidationError

from agentconnect.core.directory import DirectoryEntry
from agentconnect.core.identity import AgentIdentity
from agentconnect.core.profile import AgentProfile, Skill
from agentconnect.index._registry import Registry
from agentconnect.index.client import IndexClient
from agentconnect.index.models import IndexSettings
from agentconnect.index.service import create_index_app

_DID = AgentIdentity.create_key_based().did


def _entry(
    address: str = "writer@content-squad",
    *,
    summary: str = "Drafts release notes from findings.",
    tags: list[str] | None = None,
) -> DirectoryEntry:
    profile = AgentProfile(
        summary=summary,
        skills=[Skill(name="drafting", description="Drafts release notes.")],
        **({"tags": tags} if tags is not None else {}),
    )
    return DirectoryEntry(
        address=address,
        agent_did=_DID,
        profile=profile,
    )


def _encoded(address: str) -> str:
    return f"/entries/{quote(address, safe='')}"


@asynccontextmanager
async def _bound_client(app) -> AsyncIterator[IndexClient]:
    async with app.router.lifespan_context(app):
        http = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://index/",
        )
        client = IndexClient("http://index")
        await client._client.aclose()
        client._client = http
        try:
            yield client
        finally:
            await http.aclose()


class _FailingEmbedder:
    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        raise RuntimeError("embed failed")


class _GateEmbedder:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return [[1.0, 0.0] for _ in texts]


class _RecordingEmbedder:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.texts.extend(texts)
        return [[float(len(self.texts)), 0.0] for _ in texts]


@pytest.mark.asyncio
async def test_put_replaces_and_commits_embedding_only_after_success() -> None:
    registry = Registry("hashed")
    await registry.open()
    original = _entry(summary="Drafts release notes from findings.")
    await registry.put(original)
    recorder = _RecordingEmbedder()
    registry._embedder = recorder
    updated = _entry(summary="Reviews invoices for missing terms.")
    stored = await registry.put(updated)
    assert stored.profile.summary == updated.profile.summary
    assert any("invoices" in text for text in recorder.texts)
    found = await registry.get("writer@content-squad")
    assert found is not None
    assert found.profile.summary == updated.profile.summary

    failing = _FailingEmbedder()
    registry._embedder = failing
    with pytest.raises(RuntimeError, match="embed failed"):
        await registry.put(_entry(summary="Handles payroll questions."))
    assert failing.calls == 1
    still = await registry.get("writer@content-squad")
    assert still is not None
    assert still.profile.summary == updated.profile.summary


@pytest.mark.asyncio
async def test_cancelled_put_leaves_prior_entry() -> None:
    registry = Registry("hashed")
    await registry.open()
    original = _entry(summary="Drafts release notes from findings.")
    await registry.put(original)
    gate = _GateEmbedder()
    registry._embedder = gate
    task = asyncio.create_task(
        registry.put(_entry(summary="Reviews invoices for missing terms."))
    )
    await gate.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    found = await registry.get("writer@content-squad")
    assert found is not None
    assert found.profile.summary == original.profile.summary


@pytest.mark.asyncio
async def test_returned_entries_are_detached() -> None:
    registry = Registry("hashed")
    await registry.open()
    await registry.put(_entry(tags=["notes"]))
    found = await registry.get("writer@content-squad")
    assert found is not None and found.profile.tags is not None
    found.profile.tags.append("mutated")
    listed = await registry.list()
    assert listed[0].profile.tags == ["notes"]
    hits = await registry.search("release notes")
    hits[0].entry.profile.tags.append("hit")
    reread = await registry.get("writer@content-squad")
    assert reread is not None
    assert reread.profile.tags == ["notes"]


@pytest.mark.asyncio
async def test_http_put_get_list_search_delete_and_isolation() -> None:
    settings = IndexSettings(model_name="hashed")
    app_a = create_index_app(settings)
    app_b = create_index_app(settings)
    writer = _entry(
        "writer@content-squad",
        summary="Drafts release notes from findings.",
        tags=["notes"],
    )
    reviewer = _entry(
        "reviewer@content-squad",
        summary="Reviews invoices for missing payment terms.",
        tags=["billing"],
    )
    researcher = _entry(
        "researcher@content-squad",
        summary="Finds published sources for a topic.",
        tags=["notes"],
    )
    async with _bound_client(app_a) as client_a, _bound_client(app_b) as client_b:
        await client_a.put(writer)
        await client_a.put(reviewer)
        await client_a.put(researcher)
        ranked = await client_a.search("release notes")
        assert ranked[0].entry.address == "writer@content-squad"
        billed = await client_a.search("invoices", tags=["billing"])
        assert [hit.entry.address for hit in billed] == ["reviewer@content-squad"]
        limited = await client_a.search("notes", limit=1)
        assert len(limited) == 1
        replaced = await client_a.put(
            _entry(
                "writer@content-squad",
                summary="Drafts launch notes from findings.",
                tags=["notes"],
            )
        )
        assert replaced.profile.summary == "Drafts launch notes from findings."
        stored = await client_a.get("writer@content-squad")
        assert stored is not None
        assert stored.profile.summary == "Drafts launch notes from findings."
        listed = await client_a.list()
        assert {item.address for item in listed} == {
            "writer@content-squad",
            "reviewer@content-squad",
            "researcher@content-squad",
        }
        assert await client_b.get("writer@content-squad") is None
        assert await client_b.list() == []
        await client_a.delete("writer@content-squad")
        await client_a.delete("writer@content-squad")
        assert await client_a.get("writer@content-squad") is None


@pytest.mark.asyncio
async def test_http_missing_entry_missing_route_and_invalid_entry() -> None:
    app = create_index_app(IndexSettings(model_name="hashed"))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://index",
        ) as raw:
            missing = await raw.get(_encoded("missing@content-squad"))
            assert missing.status_code == 404
            assert missing.json() == {"detail": "entry not found"}
            missing_route = await raw.get("/no-such-route")
            assert missing_route.status_code == 404
            assert missing_route.json() != {"detail": "entry not found"}
            unqualified = await raw.get("/entries/writer")
            assert unqualified.status_code == 400
            deleted = await raw.delete(_encoded("missing@content-squad"))
            assert deleted.status_code == 204
            invalid = await raw.put(
                _encoded("writer@content-squad"),
                json={"address": "writer@content-squad", "agent_did": _DID},
            )
            assert invalid.status_code == 422
            mismatch = await raw.put(
                _encoded("writer@content-squad"),
                json=_entry("other@content-squad").to_public_dict(),
            )
            assert mismatch.status_code == 400
            client = IndexClient("http://index")
            await client._client.aclose()
            client._client = raw
            assert await client.get("missing@content-squad") is None
            with pytest.raises(httpx.HTTPStatusError):
                await client._request("GET", "no-such-route", ok=200, retry=True)
            await client.delete("missing@content-squad")


@pytest.mark.asyncio
async def test_client_writes_are_not_retried_and_rejects_a_bad_body() -> None:
    record = _entry()
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
                    json=record.to_public_dict(),
                    request=request,
                )
            if method == "POST" and path == "search":
                return httpx.Response(200, json={"nope": True}, request=request)
            return httpx.Response(503, request=request)

        async def aclose(self) -> None:
            return None

    client = IndexClient("http://index")
    await client._client.aclose()
    client._client = _Fake()
    found = await client.get("writer@content-squad")
    assert found is not None and found.address == "writer@content-squad"
    calls["n"] = 0
    with pytest.raises(httpx.HTTPStatusError):
        await client.put(record)
    assert calls["n"] == 1
    calls["n"] = 0
    with pytest.raises(httpx.HTTPStatusError):
        await client.delete("writer@content-squad")
    assert calls["n"] == 1
    with pytest.raises(ValidationError):
        await client.search("release notes")
