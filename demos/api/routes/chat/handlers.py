from datetime import datetime
import asyncio
from fastapi.websockets import WebSocketState
from redis.asyncio.client import PubSub
from fastapi import WebSocket, HTTPException, WebSocketDisconnect
from demos.api.models.chat import (
    WebSocketMessage,
    ChatMessage,
    MessageType,
    MessageRole,
)
from demos.api.routes.chat.session_utils import end_session
from agentconnect.agents.ai_agent import AIAgent
from agentconnect.agents.human_agent import HumanAgent
from demos.utils.demo_logger import get_logger
from demos.utils.config_manager import get_config
from demos.utils.shared import shared
from agentconnect.core.message import Message
import json

logger = get_logger("chat_handlers")
config = get_config()


async def broadcast_message(session_id: str, message: WebSocketMessage):
    """Broadcast message to all connections in a session"""
    logger.debug(f"Broadcasting message to session {session_id}")
    try:
        # Convert message to JSON-safe format
        message_dict = message.model_dump()
        # Ensure timestamp is ISO format string
        if isinstance(message_dict.get("timestamp"), datetime):
            message_dict["timestamp"] = message_dict["timestamp"].isoformat()

        message_json = json.dumps(message_dict)

        # First store in Redis for persistence
        await shared.redis.rpush(f"messages:{session_id}", message_json)
        # Then broadcast to all active connections
        await shared.redis.publish(f"chat:{session_id}", message_json)

        # Update session activity
        await update_session_activity(session_id)
    except Exception as e:
        logger.error(f"Error broadcasting message: {str(e)}")
        raise


async def handle_agent_response(session_id: str, message: Message) -> None:
    """Handle agent responses and broadcast to connected clients"""
    logger.debug(f"Handling agent response for session {session_id}")
    try:
        # Update session last activity
        await shared.redis.hset(
            f"session:{session_id}", "last_activity", datetime.now().isoformat()
        )

        # Get session data
        session_data = await shared.redis.hgetall(f"session:{session_id}")
        if not session_data:
            logger.error(f"Session {session_id} not found for agent response")
            return

        # Handle cooldown and stop messages differently
        if message.message_type in [MessageType.COOLDOWN, MessageType.STOP]:
            ws_message = WebSocketMessage(
                type=message.message_type,
                content=message.content,
                sender=message.sender_id,
                receiver=message.receiver_id,
                timestamp=message.timestamp or datetime.now().isoformat(),
                metadata=message.metadata,
            )
            await broadcast_message(session_id, ws_message)
            return

        # Check message count
        message_count = await shared.redis.incr(f"message_count:{session_id}")
        if message_count >= config.session_settings["max_messages_per_session"]:
            logger.warning(f"Session {session_id} reached message limit")
            await broadcast_message(
                session_id,
                WebSocketMessage(
                    type=MessageType.SYSTEM,
                    content="Conversation limit reached. Starting new topic.",
                    timestamp=datetime.now().isoformat(),
                ),
            )
            # Reset message count for new topic
            await shared.redis.set(f"message_count:{session_id}", 0)
            return

        # Convert core Message to WebSocketMessage
        ws_message = WebSocketMessage(
            type=(
                MessageType.TEXT
                if message.message_type == MessageType.RESPONSE
                else message.message_type
            ),
            content=message.content,
            sender=message.sender_id,
            receiver=message.receiver_id,
            timestamp=message.timestamp or datetime.now().isoformat(),
            metadata={
                **(message.metadata or {}),
                "conversation_type": session_data.get("session_type", "human_agent"),
                "original_type": message.message_type,  # Store original message type
            },
        )

        # Only store and broadcast if it's an agent-agent message
        if ws_message.metadata.get("conversation_type") == "agent_agent":
            # Store message in session history
            chat_message = ChatMessage(
                content=message.content,
                role=(
                    MessageRole.ASSISTANT
                    if message.sender_id.startswith(("ai_", "agent"))
                    else MessageRole.USER
                ),
                timestamp=message.timestamp or datetime.now().isoformat(),
                metadata=message.metadata,
            )
            await shared.redis.rpush(
                f"messages:{session_id}", chat_message.model_dump_json()
            )

            # Broadcast message to all clients
            logger.debug(
                f"Broadcasting message from {ws_message.sender} to {ws_message.receiver}"
            )
            await broadcast_message(session_id, ws_message)

    except Exception as e:
        logger.error(f"Error handling agent response: {str(e)}")
        # Send error message to clients
        error_message = WebSocketMessage(
            type=MessageType.ERROR,
            content=f"Failed to process agent response: {str(e)}",
            timestamp=datetime.now().isoformat(),
        )
        await broadcast_message(session_id, error_message)


async def handle_client_messages(websocket: WebSocket, session_id: str):
    """Handle incoming messages from WebSocket client"""
    try:
        # Get session data
        session_data = await shared.redis.hgetall(f"session:{session_id}")
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")

        while True:
            try:
                # Check WebSocket state before receiving
                if websocket.client_state == WebSocketState.DISCONNECTED:
                    logger.info(f"WebSocket disconnected for session {session_id}")
                    return

                # Receive and validate message
                try:
                    data = await websocket.receive_text()
                except WebSocketDisconnect:
                    logger.info(
                        f"WebSocket disconnected while receiving for session {session_id}"
                    )
                    return
                except RuntimeError as e:
                    if (
                        "Cannot call 'receive' once a disconnect message has been received"
                        in str(e)
                    ):
                        logger.info(
                            f"WebSocket already disconnected for session {session_id}"
                        )
                        return
                    raise

                logger.debug(f"Received message: {data}")

                # Parse and validate the message
                try:
                    message = WebSocketMessage.model_validate_json(data)
                except Exception as e:
                    logger.error(f"Message validation error: {str(e)}")
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json(
                            WebSocketMessage(
                                type=MessageType.ERROR,
                                content=f"Invalid message format: {str(e)}",
                                timestamp=datetime.now().isoformat(),
                            ).model_dump()
                        )
                    continue

                # Ping message type
                if message.type == MessageType.PING:
                    continue

                # Check session limits
                if await check_session_limits(session_id, session_data):
                    return

                # Process message based on session type
                session_type = session_data.get("session_type")
                if not session_type:
                    logger.error(f"Session type not found for session {session_id}")
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json(
                            WebSocketMessage(
                                type=MessageType.ERROR,
                                content="Invalid session configuration",
                                timestamp=datetime.now().isoformat(),
                            ).model_dump()
                        )
                    return

                logger.debug(f"Processing message for session type: {session_type}")

                try:
                    if session_type == "human_agent":
                        await handle_human_agent_message(session_data, message)
                    elif session_type == "agent_agent":
                        await handle_agent_agent_message(session_data, message)
                    else:
                        logger.error(f"Invalid session type: {session_type}")
                        if websocket.client_state == WebSocketState.CONNECTED:
                            await websocket.send_json(
                                WebSocketMessage(
                                    type=MessageType.ERROR,
                                    content="Invalid session type",
                                    timestamp=datetime.now().isoformat(),
                                ).model_dump()
                            )
                        continue

                    # Update activity
                    await update_session_activity(session_id)

                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json(
                            WebSocketMessage(
                                type=MessageType.ERROR,
                                content=f"Failed to process message: {str(e)}",
                                timestamp=datetime.now().isoformat(),
                            ).model_dump()
                        )

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for session {session_id}")
                return
            except Exception as e:
                logger.error(f"Error in message loop: {str(e)}")
                if websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_json(
                            WebSocketMessage(
                                type=MessageType.ERROR,
                                content=f"WebSocket error: {str(e)}",
                                timestamp=datetime.now().isoformat(),
                            ).model_dump()
                        )
                    except Exception as e:
                        logger.error(f"Error sending error message: {str(e)}")
                return  # Exit the loop on any unhandled exception

    except Exception as e:
        logger.error(f"Fatal error in client message handler: {str(e)}")
    finally:
        # Ensure cleanup happens
        logger.info(f"Cleaning up client message handler for session {session_id}")
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
        except Exception as e:
            logger.error(f"Error closing WebSocket: {str(e)}")


async def check_session_limits(session_id: str, session_data: dict) -> bool:
    """Check session limits and return True if session should end"""
    # Check message count
    message_count = await shared.redis.llen(f"messages:{session_id}")
    if message_count >= config.session_settings["max_messages_per_session"]:
        await broadcast_message(
            session_id,
            WebSocketMessage(
                type=MessageType.SYSTEM,
                content="Message limit reached. Please create a new session.",
                timestamp=datetime.now().isoformat(),
            ),
        )
        await end_session(session_id, None)
        return True

    # Check inactive time
    last_activity = datetime.fromisoformat(
        session_data.get("last_activity", datetime.now().isoformat())
    )
    if (datetime.now() - last_activity).total_seconds() > config.session_settings[
        "max_inactive_time"
    ]:
        await broadcast_message(
            session_id,
            WebSocketMessage(
                type=MessageType.SYSTEM,
                content="Session inactive for too long. Please create a new session.",
                timestamp=datetime.now().isoformat(),
            ),
        )
        await end_session(session_id, None)
        return True

    return False


async def store_message(session_id: str, message: WebSocketMessage, role: MessageRole):
    """Store message in session history"""
    chat_message = ChatMessage(
        content=message.content,
        role=role,
        timestamp=message.timestamp or datetime.now(),
        metadata=message.metadata,
    )
    await shared.redis.rpush(f"messages:{session_id}", chat_message.model_dump_json())


async def update_session_activity(session_id: str):
    """Update session last activity timestamp"""
    await shared.redis.hset(
        f"session:{session_id}", "last_activity", datetime.now().isoformat()
    )


async def handle_human_agent_message(session_data: dict, message: WebSocketMessage):
    """Handle message in human-agent session"""
    try:
        # Get agents
        human_agent: HumanAgent | None = await shared.hub.get_agent(
            session_data["human_agent_id"]
        )
        ai_agent: AIAgent | None = await shared.hub.get_agent(
            session_data["ai_agent_id"]
        )

        if not human_agent or not ai_agent:
            raise HTTPException(status_code=500, detail="Agent not found")

        # Store the message first but don't broadcast - it will be broadcast through the hub
        await store_message(session_data["session_id"], message, MessageRole.USER)

        # Send message through hub - this will handle broadcasting
        core_message = await human_agent.send_message(
            receiver_id=ai_agent.agent_id,
            content=message.content,
            message_type=message.type,
            metadata=message.metadata,
        )

        if not core_message:
            raise ValueError("Failed to send message through hub")

        try:
            # Wait for AI response in human agent's message queue
            async with asyncio.timeout(30.0):
                while True:
                    # Process messages in human agent's queue
                    if not human_agent.message_queue.empty():
                        response: Message = await human_agent.message_queue.get()

                        # Check if this is a response from the AI agent
                        if (
                            response.sender_id == ai_agent.agent_id
                            and response.message_type
                            in [MessageType.TEXT, MessageType.RESPONSE]
                        ):

                            # Convert AI response to WebSocket message
                            ai_message = WebSocketMessage(
                                type=MessageType.TEXT,
                                content=response.content,
                                sender=ai_agent.agent_id,
                                receiver=human_agent.agent_id,
                                timestamp=datetime.now().isoformat(),
                                metadata=response.metadata,
                            )

                            # Store and broadcast AI response
                            await store_message(
                                session_data["session_id"],
                                ai_message,
                                MessageRole.ASSISTANT,
                            )
                            await broadcast_message(
                                session_data["session_id"], ai_message
                            )
                            break

                        # Handle error messages
                        elif response.message_type == MessageType.ERROR:
                            error_message = WebSocketMessage(
                                type=MessageType.ERROR,
                                content=f"AI agent error: {response.content}",
                                timestamp=datetime.now().isoformat(),
                                metadata=response.metadata,
                            )
                            await broadcast_message(
                                session_data["session_id"], error_message
                            )
                            break

                        # Re-queue other messages
                        else:
                            await human_agent.message_queue.put(response)

                    await asyncio.sleep(0.1)  # Small delay to prevent CPU spinning

        except asyncio.TimeoutError:
            logger.warning(
                f"Timeout waiting for AI response in session {session_data['session_id']}"
            )
            # Send timeout notification
            timeout_message = WebSocketMessage(
                type=MessageType.SYSTEM,
                content="The AI agent is taking longer than expected to respond. Please try again.",
                timestamp=datetime.now().isoformat(),
            )
            await broadcast_message(session_data["session_id"], timeout_message)

    except Exception as e:
        logger.error(f"Error in human-agent message handler: {str(e)}")
        error_message = WebSocketMessage(
            type=MessageType.ERROR,
            content=f"Error processing message: {str(e)}",
            timestamp=datetime.now().isoformat(),
        )
        await broadcast_message(session_data["session_id"], error_message)
        raise


async def handle_agent_agent_message(session_data: dict, message: WebSocketMessage):
    """Handle message in agent-agent session"""
    # Get agents from session
    logger.debug("Getting agents for agent-agent message handling")
    agent1: AIAgent | None = await shared.hub.get_agent(session_data["agent1_id"])
    agent2: AIAgent | None = await shared.hub.get_agent(session_data["agent2_id"])

    if not agent1 or not agent2:
        raise HTTPException(status_code=500, detail="Agent not found")

    # Use sender/receiver from message if provided, otherwise determine based on last sender
    if message.sender and message.receiver:
        sender_id = message.sender
        receiver_id = message.receiver
        logger.debug(f"Using provided sender {sender_id} and receiver {receiver_id}")
    else:
        last_sender = await shared.redis.get(
            f"last_sender:{session_data['session_id']}"
        )
        if not last_sender or last_sender == agent2.agent_id:
            sender_id = agent1.agent_id
            receiver_id = agent2.agent_id
        else:
            sender_id = agent2.agent_id
            receiver_id = agent1.agent_id
        logger.debug(
            f"Determined sender {sender_id} and receiver {receiver_id} based on last sender"
        )

    # Get sender agent
    sender = agent1 if sender_id == agent1.agent_id else agent2
    logger.debug(f"Got sender agent: {sender.agent_id}")

    # Convert message type string to MessageType enum
    try:
        message_type = MessageType(message.type)
        logger.debug(f"Converted message type: {message_type}")
    except ValueError:
        raise ValueError(f"Invalid message type: {message.type}")

    # Send message through hub - BaseAgent.send_message will handle identity and protocol
    metadata = {
        **(message.metadata or {}),
        "session_id": session_data["session_id"],  # Include session context
        "conversation_type": "agent_agent",  # Add conversation type for proper handling
    }
    logger.debug(f"Prepared message metadata: {metadata}")

    logger.debug(f"Sending message through hub from {sender.agent_id} to {receiver_id}")
    core_message = await sender.send_message(
        receiver_id=receiver_id,
        content=message.content,
        message_type=message_type,
        metadata=metadata,
    )

    if not core_message:
        raise ValueError("Failed to send message through hub")

    logger.debug(
        f"Successfully sent message through hub, updating last sender to {sender_id}"
    )
    # Update last sender
    await shared.redis.set(f"last_sender:{session_data['session_id']}", sender_id)

    # Remove the direct store and broadcast of the message
    # The response will be handled and broadcasted by handle_agent_response
    # await store_message(session_data["session_id"], message, MessageRole.ASSISTANT)
    # ws_message = WebSocketMessage(
    #     type=message_type,
    #     content=message.content,
    #     sender=sender_id,
    #     receiver=receiver_id,
    #     timestamp=datetime.now().isoformat(),
    #     metadata=metadata
    # )
    # await broadcast_message(session_data["session_id"], ws_message)


async def handle_broadcasts(websocket: WebSocket, pubsub: PubSub):
    """Handle broadcasting messages to WebSocket client"""
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message and message["type"] == "message":
                try:
                    message_data = message["data"]
                    if isinstance(message_data, bytes):
                        message_data = message_data.decode("utf-8")

                    # Parse the message to check if it's from agent-agent communication
                    message_obj = json.loads(message_data)
                    if isinstance(message_obj, dict):
                        metadata = message_obj.get("metadata", {})
                        if metadata.get("conversation_type") == "agent_agent":
                            logger.debug(
                                f"Broadcasting agent-agent message: {message_data}"
                            )

                    # Send the message to the WebSocket client
                    await websocket.send_text(message_data)
                except Exception as e:
                    logger.error(f"Error sending message to WebSocket: {str(e)}")
                    raise
    except asyncio.CancelledError:
        logger.info("Broadcast handler cancelled")
        raise
    except Exception as e:
        logger.error(f"Error in broadcast handler: {str(e)}")
        raise


# async def get_session_clients(session_id: str) -> list[WebSocket]:
#     """Get all connected WebSocket clients for a session"""
#     logger.debug(f"Getting connected clients for session {session_id}")
#     try:
#         clients = shared.active_connections.get(session_id, [])
#         logger.debug(f"Found {len(clients)} connected clients")
#         return clients
#     except Exception as e:
#         logger.error(f"Error getting session clients: {str(e)}")
#         return []

# async def validate_message(message: Dict[str, Any]) -> Optional[str]:
#     """Validate incoming message format"""
#     logger.debug("Validating message format")
#     try:
#         required_fields = ["content", "type"]
#         for field in required_fields:
#             if field not in message:
#                 error = f"Missing required field: {field}"
#                 logger.warning(error)
#                 return error

#         if not isinstance(message["content"], str):
#             error = "Message content must be a string"
#             logger.warning(error)
#             return error

#         if message["type"] not in [t.value for t in MessageType]:
#             error = f"Invalid message type: {message['type']}"
#             logger.warning(error)
#             return error

#         logger.debug("Message validation successful")
#         return None

#     except Exception as e:
#         error = f"Message validation error: {str(e)}"
#         logger.error(error)
#         return error

# async def handle_system_message(session_id: str, message: Dict[str, Any]) -> None:
#     """Handle system messages"""
#     logger.info(f"Processing system message for session {session_id}")
#     try:
#         # Process system commands
#         command = message.get("content", "").lower()

#         if command == "end_session":
#             logger.info(f"System command: end session {session_id}")
#             await end_session(session_id)
#         elif command == "pause_session":
#             logger.info(f"System command: pause session {session_id}")
#             await pause_session(session_id)
#         else:
#             logger.warning(f"Unknown system command: {command}")

#     except Exception as e:
#         logger.error(f"Error handling system message: {str(e)}")
