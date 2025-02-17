from fastapi import HTTPException, status
import asyncio
from typing import List

from demos.utils.demo_logger import get_logger
from demos.utils.shared import shared

logger = get_logger("session_utils")

# Global lock for session operations
_session_locks: dict[str, asyncio.Lock] = {}


async def get_session_lock(session_id: str) -> asyncio.Lock:
    """Get or create a lock for a session"""
    if session_id not in _session_locks:
        _session_locks[session_id] = asyncio.Lock()
    return _session_locks[session_id]


async def end_session(session_id: str, current_user: str):
    """End a chat session"""
    try:
        # Get session lock
        lock = await get_session_lock(session_id)
        async with lock:
            session_data = await shared.redis.hgetall(f"session:{session_id}")
            if not session_data:
                raise HTTPException(status_code=404, detail="Session not found")

            # Verify ownership
            if current_user and session_data.get("created_by") != current_user:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to end this session",
                )

            await cleanup_session(session_id, session_data)

            # Clean up the lock
            _session_locks.pop(session_id, None)

            return {"status": "success", "message": "Session ended"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


async def cleanup_session(session_id: str, session_data: dict):
    """Helper function to cleanup a session with proper error handling"""
    errors: List[str] = []

    try:
        # Unregister agents with error handling
        agent_ids = [
            session_data.get("human_agent_id"),
            session_data.get("ai_agent_id"),
            session_data.get("agent1_id"),
            session_data.get("agent2_id"),
        ]

        for agent_id in agent_ids:
            if agent_id:
                try:
                    await shared.hub.unregister_agent(agent_id)
                except Exception as e:
                    errors.append(f"Failed to unregister agent {agent_id}: {str(e)}")

        # Clean up Redis data with error handling
        redis_keys = [
            f"session:{session_id}",
            f"messages:{session_id}",
            f"connections:{session_id}",
            f"message_count:{session_id}",
            f"chat:{session_id}",  # PubSub channel
        ]

        for key in redis_keys:
            try:
                await shared.redis.delete(key)
            except Exception as e:
                errors.append(f"Failed to delete Redis key {key}: {str(e)}")

        # Log cleanup status
        if errors:
            logger.warning(
                f"Session {session_id} cleanup completed with errors: {'; '.join(errors)}"
            )
        else:
            logger.info(f"Session {session_id} cleanup completed successfully")

    except Exception as e:
        logger.error(f"Error during session cleanup for {session_id}: {str(e)}")
        raise RuntimeError(f"Session cleanup failed: {str(e)}")
