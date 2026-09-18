"""Run awaited operations on one event loop for sync pytest-benchmark samples."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")


class AsyncBridge:
    """Keep one ``asyncio.Runner`` so Team objects stay on a single loop."""

    def __init__(self) -> None:
        self._runner = asyncio.Runner()

    def run(self, awaitable: Awaitable[T]) -> T:
        # Runner.run only accepts coroutines on Python 3.11–3.13. Tasks and
        # gather Futures also occur when a benchmark overlaps operations.
        async def wait() -> T:
            return await awaitable

        return self._runner.run(wait())

    def close(self) -> None:
        self._runner.close()
