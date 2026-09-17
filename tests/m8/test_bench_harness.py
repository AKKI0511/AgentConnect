"""Benchmark labels must describe the backend and transport actually measured."""

import pytest
from tests.m8 import bench

from agentconnect.team.directory.embedder import HashedEmbedder

pytestmark = pytest.mark.asyncio


async def test_neural_benchmark_rejects_fallback(monkeypatch):
    class BrokenNeural(HashedEmbedder):
        name = "fastembed:broken"

        async def embed(self, texts):
            raise RuntimeError("simulated neural model failure")

    monkeypatch.setattr(bench, "FastEmbedEmbedder", BrokenNeural)
    monkeypatch.setattr(bench, "WARM_SAMPLES", 2)
    result = await bench._run_warm_case(
        store_kind="memory", backend="neural", members=10, transport="embedded"
    )
    assert result["status"] == "failed"
    assert "but measured hashed" in result["error"]


async def test_http_benchmark_burst_uses_http(monkeypatch):
    calls = 0
    original = bench._http_find

    async def counted_http_find(*args):
        nonlocal calls
        calls += 1
        return await original(*args)

    monkeypatch.setattr(bench, "_http_find", counted_http_find)
    monkeypatch.setattr(bench, "WARM_SAMPLES", 2)
    result = await bench._run_warm_case(
        store_kind="memory", backend="hashed", members=10, transport="http"
    )
    assert "error" not in result
    # One HTTP warmup, measured samples, one lag probe, then the HTTP burst.
    assert calls == 1 + 2 + 1 + bench.CONCURRENT_FINDERS
