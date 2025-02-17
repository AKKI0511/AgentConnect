"""Task management utilities for the API"""

import asyncio
from typing import Set
from demos.utils.demo_logger import get_logger

logger = get_logger("task_manager")

# Global state
background_tasks: Set[asyncio.Task] = set()


def add_background_task(task: asyncio.Task):
    """Add a background task to be tracked"""
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


async def cleanup_background_tasks():
    """Cleanup background tasks"""
    if not background_tasks:
        return

    logger.info(f"Cleaning up {len(background_tasks)} background tasks...")
    for task in background_tasks:
        try:
            if not task.done():
                task.cancel()
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error cancelling task {task}: {str(e)}")
        except Exception as e:
            logger.error(f"Error handling task cleanup: {str(e)}")

    background_tasks.clear()
