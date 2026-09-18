"""The benchmark loop must preserve and finish work between timing rounds."""

import asyncio

import pytest

from tests.support.async_bridge import AsyncBridge


def test_bridge_awaits_background_tasks_and_gather_on_the_same_loop():
    bridge = AsyncBridge()
    try:

        async def start():
            async def work():
                await asyncio.sleep(0)
                return asyncio.get_running_loop()

            return asyncio.create_task(work()), asyncio.gather(work(), work())

        task, burst = bridge.run(start())
        loop = bridge.run(task)
        assert bridge.run(burst) == [loop, loop]
        assert bridge.run(task) is loop

        async def fail():
            raise ValueError("background failure")

        with pytest.raises(ValueError, match="background failure"):
            bridge.run(fail())
    finally:
        bridge.close()
