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


async def test_probe_idle_intervals_stay_near_sleep():
    probe = LoopProbe()
    await probe.start()
    await asyncio.sleep(0.05)
    intervals = await probe.stop()
    assert intervals
    assert max(extra_lag(intervals)) < 0.05
