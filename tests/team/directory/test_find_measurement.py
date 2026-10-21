"""Measurement regressions: requested backend and genuine HTTP finds."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from tests.support.budgets import CONCURRENT_FINDERS, HTTP_WARMUPS
from tests.support.runtime import (
    assert_measured_backend,
    http_find,
    join_roster,
    start_team,
)
from tests.support.stores import open_store
from tests.team.conftest import join_member, make_did

from agentconnect.team.directory.embedder import HashedEmbedder
from agentconnect.team.http import _HTTP_PREFIX

pytestmark = pytest.mark.asyncio


async def test_measured_backend_rejects_neural_fallback():
    class BrokenNeural(HashedEmbedder):
        name = "fastembed:broken"

        async def embed(self, texts):
            raise RuntimeError("simulated neural model failure")

    store = await open_store("memory")
    embedder = BrokenNeural()
    team = await start_team(store, embeddings=embedder)
    try:
        await join_roster(team, 10, specialist=True)
        caller = await join_member(team, "researcher", agent_did=make_did("researcher"))
        found = await team.find(caller["session_token"], "similar paperwork")
        assert found["matches"]
        with pytest.raises(AssertionError, match="but measured hashed"):
            assert_measured_backend(team, embedder.name)
    finally:
        await team.stop()
        await store.close()


async def test_http_find_burst_uses_http():
    store = await open_store("memory")
    team = await start_team(store)
    try:
        await join_roster(team, 10, specialist=True)
        caller = await join_member(team, "researcher", agent_did=make_did("researcher"))
        origin = await team.serve()
        token = caller["session_token"]
        query = "similar paperwork"
        paths: list[str] = []

        async def record_request(request: httpx.Request) -> None:
            paths.append(request.url.path)

        async with httpx.AsyncClient(
            timeout=60.0,
            trust_env=False,
            event_hooks={"request": [record_request]},
        ) as client:
            for _ in range(HTTP_WARMUPS):
                found = await http_find(client, origin, token, query)
                assert found["matches"]
            burst = await asyncio.gather(
                *[
                    http_find(client, origin, token, query)
                    for _ in range(CONCURRENT_FINDERS)
                ]
            )
            assert all(item["matches"] for item in burst)
        expected = f"{_HTTP_PREFIX}/directory/find"
        assert len(paths) == HTTP_WARMUPS + CONCURRENT_FINDERS
        assert all(path == expected for path in paths)
    finally:
        await team.stop()
        await store.close()
