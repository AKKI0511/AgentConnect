"""Run awaited operations on one event loop for sync pytest-benchmark samples."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


class AsyncBridge:
    """Keep one ``asyncio.Runner`` so Team objects stay on a single loop."""

    def __init__(self) -> None:
        self._runner = asyncio.Runner()

    def run(self, coro: Coroutine[Any, Any, T]) -> T:
        return self._runner.run(coro)

    def close(self) -> None:
        self._runner.close()
