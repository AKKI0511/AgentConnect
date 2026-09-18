"""Shared Runtime benchmark helpers."""

from __future__ import annotations

from typing import Any

from tests.support.stores import CountingStore, connect_redis

from agentconnect.team.store.memory import MemoryStore


async def open_bench_store(kind: str) -> CountingStore:
    """Memory or Redis store with call counters, matching the former warm cases."""
    if kind == "memory":
        inner = MemoryStore()
        await inner.open()
        store = CountingStore(inner)
        await store.open()
        return store
    inner = await connect_redis()
    wrapped = CountingStore(inner)
    wrapped.persistence = "durable"
    return wrapped


async def close_bench_store(store: CountingStore) -> None:
    await store.clear()
    await store.close()


def sample_seconds(benchmark: Any) -> list[float]:
    """Return one duration per pytest-benchmark round."""
    stats = getattr(benchmark, "stats", None)
    raw = getattr(stats, "stats", stats)
    data = getattr(raw, "data", None)
    if not data:
        raise AssertionError("benchmark produced no samples")
    return [float(item) for item in data]


def queue_stats(team: Any) -> dict[str, int]:
    directory = team._directory
    embedder = getattr(directory, "_active", None)
    cpu = getattr(directory, "_cpu", None)
    work = getattr(embedder, "_work", None)
    return {
        "search_in_flight_peak": int(getattr(directory, "search_in_flight_peak", 0)),
        "dir_cpu_peak_pending": int(getattr(cpu, "peak_pending", 0) or 0),
        "embed_peak_pending": int(getattr(work, "peak_pending", 0) or 0),
        "dir_worker_threads": len(cpu._pool._threads) if cpu else 0,
        "embed_worker_threads": len(work._pool._threads) if work else 0,
    }
