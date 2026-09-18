"""Lag observer catches startup and late stalls across the whole workload."""

from __future__ import annotations

import asyncio
import time

import pytest
from tests.support.budgets import extra_lag
from tests.support.runtime import LoopProbe, probe_during

pytestmark = pytest.mark.asyncio


async def test_probe_catches_startup_stall():
    async def work():
        time.sleep(0.3)
        return "ok"

    result, intervals = await probe_during(work(), members=10, enforce=False)
    assert result == "ok"
    assert max(extra_lag(intervals)) >= 0.2


async def test_probe_catches_late_stall():
    async def work():
        await asyncio.sleep(0.2)
        time.sleep(0.3)
        return "ok"

    result, intervals = await probe_during(work(), members=10, enforce=False)
    assert result == "ok"
    assert max(extra_lag(intervals)) >= 0.2


async def test_broken_eight_sample_probe_misses_late_stall():
    """The previous observer yielded, then stopped after eight 10ms samples."""

    async def work():
        await asyncio.sleep(0.2)
        time.sleep(0.3)
        return "ok"

    task = asyncio.create_task(work())
    await asyncio.sleep(0)
    delays: list[float] = []
    for _ in range(8):
        started = time.perf_counter()
        await asyncio.sleep(0.01)
        delays.append(time.perf_counter() - started)
    result = await task
    assert result == "ok"
    assert max(extra_lag(delays)) < 0.05


async def test_probe_idle_intervals_stay_near_sleep():
    probe = LoopProbe()
    await probe.start()
    await asyncio.sleep(0.05)
    intervals = await probe.stop()
    assert intervals
    assert max(extra_lag(intervals)) < 0.05
