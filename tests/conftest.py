"""Shared pytest hooks."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio

STORE_KINDS = ("yielding-memory", "redis")


def pytest_configure(config) -> None:
    """Keep tmp_path inside the repo so Windows user-temp locks cannot fail setup."""
    os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
    os.environ.setdefault("no_proxy", "127.0.0.1,localhost")
    if getattr(config.option, "basetemp", None):
        return
    basetemp = Path(__file__).resolve().parent.parent / ".pytest_tmp"
    basetemp.mkdir(parents=True, exist_ok=True)
    config.option.basetemp = str(basetemp)


def pytest_collection_modifyitems(items) -> None:
    """Mark Redis-backed tests at collection time so ``-m redis`` works."""
    marker = pytest.mark.redis
    for item in items:
        names = set(getattr(item, "fixturenames", ()))
        if "redis_store" in names:
            item.add_marker(marker)
        callspec = getattr(item, "callspec", None)
        if callspec is None:
            continue
        params = callspec.params
        if params.get("store_kind") == "redis" or params.get("kind") == "redis":
            item.add_marker(marker)


@pytest_asyncio.fixture(
    params=STORE_KINDS, ids=list(STORE_KINDS), loop_scope="function"
)
async def runtime_store(request: pytest.FixtureRequest):
    from tests.support.stores import open_store

    kind = str(request.param)
    if kind == "redis":
        request.node.add_marker(pytest.mark.redis)
    store = await open_store(kind)
    try:
        yield store
    finally:
        try:
            await store.clear()
        except Exception:
            pass
        await store.close()
