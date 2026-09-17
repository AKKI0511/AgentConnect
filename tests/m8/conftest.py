"""M8 store fixtures: yielding memory and required Redis."""

from __future__ import annotations

import pytest
import pytest_asyncio

from tests.m8.stores import open_m8_store
from tests.m8.support import STORE_KINDS


@pytest.fixture(params=STORE_KINDS, ids=list(STORE_KINDS))
def store_kind(request: pytest.FixtureRequest) -> str:
    kind = str(request.param)
    if kind == "redis":
        request.node.add_marker(pytest.mark.redis)
    return kind


@pytest_asyncio.fixture(loop_scope="function")
async def m8_store(store_kind: str):
    store = await open_m8_store(store_kind)
    try:
        yield store
    finally:
        try:
            await store.clear()
        except Exception:
            pass
        await store.close()
