from datetime import datetime
import asyncio
from fastapi import HTTPException, status
from demos.api.models.chat import (
    WebSocketMessage,
    MessageType,
)

from demos.utils.demo_logger import get_logger
from demos.utils.config_manager import get_config
from demos.utils.shared import shared
from .handlers import broadcast_message
from .session_utils import cleanup_session, get_session_lock

logger = get_logger("chat_session")
config = get_config()


async def cleanup_inactive_sessions() -> None:
    """Cleanup inactive sessions periodically"""
    while True:
        try:
            # Get all session keys
            session_keys = []
            try:
                session_keys = await shared.redis.keys("session:*")
            except Exception as e:
                logger.error(f"Error getting session keys: {str(e)}")
                await asyncio.sleep(60)
                continue

            current_time = datetime.now()

            for key in session_keys:
                try:
                    session_id = key.split(":")[-1]

                    # Try to get lock with timeout
                    lock = await get_session_lock(session_id)
                    try:
                        async with asyncio.timeout(
                            5.0
                        ):  # Use asyncio.timeout instead of lock timeout
                            async with lock:
                                session_data = await shared.redis.hgetall(key)
                                if not session_data:
                                    continue

                                should_cleanup = False
                                cleanup_reason = None

                                # Check last activity
                                last_activity = datetime.fromisoformat(
                                    session_data.get(
                                        "last_activity", current_time.isoformat()
                                    )
                                )
                                inactive_time = (
                                    current_time - last_activity
                                ).total_seconds()

                                if (
                                    inactive_time
                                    > config.session_settings["max_inactive_time"]
                                ):
                                    should_cleanup = True
                                    cleanup_reason = "Session inactive for too long"

                                # Check message count
                                message_count = await shared.redis.llen(
                                    f"messages:{session_id}"
                                )
                                if (
                                    message_count
                                    >= config.session_settings[
                                        "max_messages_per_session"
                                    ]
                                ):
                                    should_cleanup = True
                                    cleanup_reason = "Maximum message count reached"

                                if should_cleanup:
                                    logger.info(
                                        f"Session {session_id} cleanup triggered: {cleanup_reason}"
                                    )
                                    try:
                                        await broadcast_message(
                                            session_id,
                                            WebSocketMessage(
                                                type=MessageType.SYSTEM,
                                                content=f"{cleanup_reason}. Session will be closed.",
                                                timestamp=current_time.isoformat(),
                                            ),
                                        )
                                        await cleanup_session(session_id, session_data)
                                    except Exception as e:
                                        logger.error(
                                            f"Error during cleanup of session {session_id}: {str(e)}"
                                        )

                    except asyncio.TimeoutError:
                        logger.warning(
                            f"Timeout acquiring lock for session {session_id}"
                        )
                    except Exception as e:
                        logger.error(f"Error processing session {session_id}: {str(e)}")

                except Exception as e:
                    logger.error(f"Error handling session key {key}: {str(e)}")

            await asyncio.sleep(60)  # Check every minute

        except asyncio.CancelledError:
            logger.info("Session cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in session cleanup loop: {str(e)}")
            await asyncio.sleep(60)  # Retry after a minute


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
            if session_data.get("created_by") != current_user:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to end this session",
                )

            # Notify users
            try:
                await broadcast_message(
                    session_id,
                    WebSocketMessage(
                        type=MessageType.SYSTEM,
                        content="Session is being closed by the owner.",
                        timestamp=datetime.now(),
                    ),
                )
            except Exception as e:
                logger.warning(f"Could not send session end notification: {str(e)}")

            await cleanup_session(session_id, session_data)
            return {"status": "success", "message": "Session ended"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
