"""Pytest wrapper for the Runtime discovery benchmark.

The reproducible entry point is ``python tests/m8/bench.py``. This test
exists so ``pytest -m perf`` runs the same matrix.
"""

from __future__ import annotations

import os

import pytest
from tests.m8.bench import DEFAULT_OUT, run_benchmark, write_report

pytestmark = [pytest.mark.asyncio, pytest.mark.perf]


async def test_runtime_discovery_benchmark():
    required = os.environ.get("AGENTCONNECT_REQUIRE_NEURAL", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    report = await run_benchmark(
        quick=False,
        stress=False,
        require_neural=required,
    )
    write_report(report, DEFAULT_OUT)
    assert report["failed_names"] == [], report["failed_names"]
