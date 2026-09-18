"""pytest-benchmark fixtures and provenance for Runtime discovery."""

from __future__ import annotations

import gc
import importlib.metadata
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.support.async_bridge import AsyncBridge
from tests.support.runtime import platform_report

from agentconnect.team.directory.embedder import (
    DEFAULT_FASTEMBED_MODEL,
    HASHED_DIM,
    HashedEmbedder,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def async_bridge():
    bridge = AsyncBridge()
    try:
        yield bridge
    finally:
        bridge.close()


@pytest.fixture(autouse=True)
def _collect_after_case():
    yield
    gc.collect()


def _git_revision() -> str:
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=str(ROOT), text=True
        ).strip()
        return f"{head}-dirty" if dirty else head
    except Exception:
        return "unknown"


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _rss_bytes() -> int | None:
    try:
        import psutil
    except ImportError:
        return None
    return int(psutil.Process().memory_info().rss)


def pytest_benchmark_update_machine_info(config, machine_info: dict[str, Any]) -> None:
    machine_info.update(platform_report())
    rss = _rss_bytes()
    if rss is not None:
        machine_info["rss_bytes"] = rss


def pytest_benchmark_update_json(
    config, benchmarks, output_json: dict[str, Any]
) -> None:
    from tests.support.budgets import (
        FIND_P95_S,
        LOOP_LAG_S_REBUILD,
        SEND_DURING_FIND_P95_S,
        WARM_SAMPLES,
    )

    output_json["revision"] = _git_revision()
    output_json["provenance"] = {
        "hashed": {"name": HashedEmbedder.name, "dim": HASHED_DIM},
        "neural": {
            "backend": f"fastembed:{DEFAULT_FASTEMBED_MODEL}",
            "model": DEFAULT_FASTEMBED_MODEL,
            "packages": {
                "fastembed": _package_version("fastembed"),
                "onnxruntime": _package_version("onnxruntime"),
                "numpy": _package_version("numpy"),
            },
        },
        "runtime_packages": {
            "redis": _package_version("redis"),
            "hiredis": _package_version("hiredis"),
            "httpx": _package_version("httpx"),
            "pydantic": _package_version("pydantic"),
            "psutil": _package_version("psutil"),
            "pytest-benchmark": _package_version("pytest-benchmark"),
        },
    }
    output_json["budgets"] = {
        "hashed_p95_s": {str(size): value for size, value in FIND_P95_S.items()},
        "send_during_find_p95_s": SEND_DURING_FIND_P95_S,
        "rebuild_lag_s": LOOP_LAG_S_REBUILD,
        "warm_samples": WARM_SAMPLES,
    }
