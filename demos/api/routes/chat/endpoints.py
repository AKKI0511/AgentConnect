from fastapi import (
    WebSocket,
    HTTPException,
    BackgroundTasks,
    status,
    WebSocketDisconnect,
)
from datetime import datetime
import json
import asyncio
from typing import Optional

from fastapi.websockets import WebSocketState
from redis.asyncio.client import PubSub

from demos.api.models.chat import (
    CreateSessionRequest,
    SessionResponse,
)
from demos.utils.demo_logger import get_logger
from demos.utils.config_manager import get_config
from demos.utils.api_validation import validate_ws_connection
from demos.utils.shared import shared

from .handlers import handle_client_messages, handle_broadcasts
from .session import end_session
from .session_creation import create_new_session

logger = get_logger("chat_endpoints")
config = get_config()


async def websocket_endpoint_handler(
    websocket: WebSocket,
    session_id: str,
    current_user: str,
):
    """WebSocket endpoint for real-time chat"""
    logger.info(
        f"WebSocket connection request for session {session_id} from user {current_user}"
    )
    pubsub: Optional[PubSub] = None
    tasks = []

    try:
        # Validate connection
        if not await validate_ws_connection(websocket, session_id):
            await websocket.close(code=4003)
            return

        # Validate session exists and ownership
        session_data = await shared.redis.hgetall(f"session:{session_id}")
        if not session_data:
            await websocket.close(code=4004)
            return

        if session_data.get("created_by") != current_user:
            await websocket.close(code=4003)
            return

        # Accept connection
        await websocket.accept()
        logger.debug(f"WebSocket connection accepted for session {session_id}")

        # Register with shared resources for cleanup
        shared.register_websocket(websocket)

        try:
            # Add to active connections
            await shared.redis.sadd(f"connections:{session_id}", websocket.client.host)

            # Subscribe to session channel for broadcasts
            pubsub = shared.redis.pubsub()
            await pubsub.subscribe(f"chat:{session_id}")

            # Create tasks with proper names for tracking
            receive_task = asyncio.create_task(
                handle_client_messages(websocket, session_id),
                name=f"ws_receive_{session_id}",
            )
            broadcast_task = asyncio.create_task(
                handle_broadcasts(websocket, pubsub), name=f"ws_broadcast_{session_id}"
            )
            heartbeat_task = asyncio.create_task(
                handle_heartbeat(websocket, session_id),
                name=f"ws_heartbeat_{session_id}",
            )

            # Add tasks to tracking
            tasks.extend([receive_task, broadcast_task, heartbeat_task])

            # Wait for tasks to complete
            try:
                done, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )

                # Log completed tasks
                for task in done:
                    if task.exception():
                        logger.error(
                            f"Task {task.get_name()} failed: {str(task.exception())}"
                        )
                    else:
                        logger.info(f"Task {task.get_name()} completed successfully")

                # Cancel remaining tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logger.error(
                            f"Error cancelling task {task.get_name()}: {str(e)}"
                        )

            except Exception as e:
                logger.error(f"Error in task management: {str(e)}")
                raise

        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected: {session_id}")
        finally:
            # Cancel all tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logger.error(f"Error cancelling task: {str(e)}")

            # Cleanup resources
            if pubsub:
                try:
                    await pubsub.unsubscribe(f"chat:{session_id}")
                    await pubsub.close()
                except Exception as e:
                    logger.error(f"Error closing pubsub: {str(e)}")

            try:
                await shared.redis.srem(
                    f"connections:{session_id}", websocket.client.host
                )
            except Exception as e:
                logger.error(f"Error removing connection from Redis: {str(e)}")

            # Close websocket if still connected
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.close()
                except Exception as e:
                    logger.error(f"Error closing WebSocket: {str(e)}")

            # Unregister from shared resources
            shared.unregister_websocket(websocket)

    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close(code=4000)
        except Exception as e:
            logger.error(f"Error closing WebSocket: {str(e)}")
        finally:
            # Ensure websocket is unregistered
            shared.unregister_websocket(websocket)


async def handle_heartbeat(websocket: WebSocket, session_id: str):
    """Handle WebSocket heartbeat to maintain connection health"""
    try:
        while True:
            try:
                if websocket.client_state != WebSocketState.CONNECTED:
                    logger.warning(
                        f"WebSocket disconnected during heartbeat: {session_id}"
                    )
                    break

                # Send ping frame
                await websocket.send_json(
                    {"type": "ping", "timestamp": datetime.now().isoformat()}
                )

                # Update last activity
                await shared.redis.hset(
                    f"session:{session_id}", "last_activity", datetime.now().isoformat()
                )

                await asyncio.sleep(30)  # Send heartbeat every 30 seconds

            except WebSocketDisconnect:
                logger.info(f"Client disconnected during heartbeat: {session_id}")
                break
            except Exception as e:
                logger.error(f"Error in heartbeat handler: {str(e)}")
                if "close message has been sent" in str(e):
                    break
                raise

    except asyncio.CancelledError:
        logger.debug("Heartbeat task cancelled")
    except Exception as e:
        logger.error(f"Fatal error in heartbeat handler: {str(e)}")
        raise


async def create_session_handler(
    request: CreateSessionRequest, background_tasks: BackgroundTasks, current_user: str
) -> SessionResponse:
    """Create a new chat session"""
    logger.info(f"Session creation request from user {current_user}")
    try:
        logger.debug(f"Creating session with agents: {request.agents}")
        return await create_new_session(request, background_tasks, current_user)
    except Exception as e:
        logger.error(f"Error in create session handler: {str(e)}")
        raise


async def get_session_handler(session_id: str, current_user: str) -> SessionResponse:
    """Get session information"""
    logger.info(f"Session info request for {session_id} from user {current_user}")
    try:
        session_data = await shared.redis.hgetall(f"session:{session_id}")
        if not session_data:
            logger.warning(f"Session {session_id} not found")
            raise HTTPException(status_code=404, detail="Session not found")

        # Verify ownership
        if session_data.get("created_by") != current_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this session",
            )

        metadata = json.loads(session_data.get("metadata", "{}"))

        return SessionResponse(
            session_id=session_id,
            type=session_data["type"],
            created_at=datetime.fromisoformat(session_data["created_at"]),
            status=session_data["status"],
            provider=session_data["provider"],
            model=session_data["model"],
            metadata=metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving session info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


async def delete_session_handler(session_id: str, current_user: str):
    """Delete a chat session"""
    logger.info(f"Session deletion request for {session_id} from user {current_user}")
    try:
        return await end_session(session_id, current_user)
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}")
        raise
