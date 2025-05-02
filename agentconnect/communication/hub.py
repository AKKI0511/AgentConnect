"""
Message routing system for the AgentConnect framework.

This module provides a communication hub that handles message routing and agent registration
without dictating agent behavior. It enables agent discovery and communication in a
peer-to-peer network where agents make independent decisions.
"""

# Standard library imports
import asyncio
import logging
import time
import uuid
from asyncio import Future
from typing import Awaitable, Callable, Dict, List, Optional

from agentconnect.communication.protocols.agent import SimpleAgentProtocol

# Absolute imports from agentconnect package
from agentconnect.core.agent import BaseAgent
from agentconnect.core.exceptions import SecurityError
from agentconnect.core.message import Message
from agentconnect.core.registry import AgentRegistration, AgentRegistry
from agentconnect.core.types import AgentType, InteractionMode, MessageType

# Set up logging
logger = logging.getLogger("CommunicationHub")


class CommunicationHub:
    """
    Message routing system that facilitates peer-to-peer agent communication.

    The CommunicationHub is NOT a central controller of agent behavior, but rather:

    1. Routes messages between independent agents
    2. Facilitates agent discovery through registration
    3. Ensures secure message delivery without dictating responses
    4. Manages communication protocols for consistent messaging
    5. Tracks message history for auditability

    Each agent connected to the hub maintains its autonomy and decision-making capability.
    The hub simply enables discovery and communication without controlling behavior.
    """

    def __init__(self, registry: AgentRegistry):
        """
        Initialize the communication hub.

        Args:
            registry: The agent registry to use for agent lookup and verification
        """
        self.registry = registry
        self.active_agents: Dict[str, BaseAgent] = {}
        self._message_history: List[Message] = []
        self.agent_protocol = SimpleAgentProtocol()
        self._message_handlers: Dict[
            str, List[Callable[[Message], Awaitable[None]]]
        ] = {}
        self._global_handlers: List[Callable[[Message], Awaitable[None]]] = []
        # Store pending requests as {request_id: Future}
        self.pending_responses: Dict[str, Future] = {}
        # Store late responses as {request_id: Message}
        self.late_responses: Dict[str, Message] = {}

    def add_message_handler(
        self, agent_id: str, handler: Callable[[Message], Awaitable[None]]
    ) -> None:
        """
        Add a message handler for a specific agent.

        Args:
            agent_id: The ID of the agent to handle messages for
            handler: Async function that takes a Message and returns None

        Raises:
            ValueError: If agent_id is None or empty, or if handler is None
        """
        if not agent_id or not handler:
            raise ValueError("agent_id and handler must be provided")

        logger.debug(f"Adding message handler for agent {agent_id}")

        # Tag the handler with the agent_id for cleanup
        setattr(handler, "__agent_id__", agent_id)

        if agent_id not in self._message_handlers:
            self._message_handlers[agent_id] = []
        if (
            handler not in self._message_handlers[agent_id]
        ):  # Prevent duplicate handlers
            self._message_handlers[agent_id].append(handler)

    def add_global_handler(self, handler: Callable[[Message], Awaitable[None]]) -> None:
        """Add a global message handler that receives all messages

        Args:
            handler (Callable): Async function that takes a Message and returns None

        Raises:
            ValueError: If handler is None
        """
        if not handler:
            raise ValueError("handler must be provided")

        logger.debug("Adding global message handler")
        if handler not in self._global_handlers:  # Prevent duplicate handlers
            self._global_handlers.append(handler)

    def remove_message_handler(
        self, agent_id: str, handler: Callable[[Message], Awaitable[None]]
    ) -> bool:
        """Remove a message handler for a specific agent

        Args:
            agent_id (str): The ID of the agent
            handler (Callable): The handler function to remove

        Returns:
            bool: True if handler was removed, False if not found
        """
        logger.debug(f"Removing message handler for agent {agent_id}")
        if agent_id in self._message_handlers:
            original_length = len(self._message_handlers[agent_id])
            self._message_handlers[agent_id] = [
                h for h in self._message_handlers[agent_id] if h != handler
            ]
            if not self._message_handlers[agent_id]:
                del self._message_handlers[agent_id]
            return len(self._message_handlers.get(agent_id, [])) < original_length
        return False

    def remove_global_handler(
        self, handler: Callable[[Message], Awaitable[None]]
    ) -> bool:
        """Remove a global message handler

        Args:
            handler (Callable): The handler function to remove

        Returns:
            bool: True if handler was removed, False if not found
        """
        logger.debug("Removing global message handler")
        original_length = len(self._global_handlers)
        self._global_handlers = [h for h in self._global_handlers if h != handler]
        return len(self._global_handlers) < original_length

    def clear_agent_handlers(self, agent_id: str) -> None:
        """Clear all message handlers for a specific agent

        Args:
            agent_id (str): The ID of the agent
        """
        logger.debug(f"Clearing all message handlers for agent {agent_id}")
        # Remove specific handlers
        if agent_id in self._message_handlers:
            # Get the handlers before deleting
            handlers = self._message_handlers[agent_id]
            # Clear any references these handlers might have
            for handler in handlers:
                if hasattr(handler, "__agent_id__"):
                    delattr(handler, "__agent_id__")
            del self._message_handlers[agent_id]

        # Also clean up any handlers in other agents' lists that might reference this agent
        for other_agent_id, handlers in list(self._message_handlers.items()):
            self._message_handlers[other_agent_id] = [
                h for h in handlers if getattr(h, "__agent_id__", None) != agent_id
            ]

    async def _notify_handlers(
        self, message: Message, is_special: bool = False
    ) -> None:
        """Notify all relevant handlers about a message

        Args:
            message (Message): The message that was received
            is_special (bool): Whether this is a special message type (e.g., COOLDOWN, STOP)
        """
        try:
            # Create a copy of handlers to avoid modification during iteration
            global_handlers = self._global_handlers.copy()

            # Notify global handlers first
            for handler in global_handlers:
                try:
                    await handler(message)
                except Exception as e:
                    logger.error(f"Error in global message handler: {str(e)}")
                    # Remove failed handler
                    if handler in self._global_handlers:
                        self._global_handlers.remove(handler)

            # For special messages, notify both sender and receiver handlers
            if is_special and message.sender_id in self._message_handlers:
                # Create a copy of sender's handlers
                sender_handlers = self._message_handlers[message.sender_id].copy()
                for handler in sender_handlers:
                    try:
                        await handler(message)
                    except Exception as e:
                        logger.error(
                            f"Error in message handler for sender {message.sender_id}: {str(e)}"
                        )
                        # Remove failed handler
                        if message.sender_id in self._message_handlers:
                            self._message_handlers[message.sender_id].remove(handler)

            # Notify receiver's handlers
            if message.receiver_id in self._message_handlers:
                # Create a copy of receiver's handlers
                receiver_handlers = self._message_handlers[message.receiver_id].copy()
                for handler in receiver_handlers:
                    try:
                        await handler(message)
                    except Exception as e:
                        logger.error(
                            f"Error in message handler for receiver {message.receiver_id}: {str(e)}"
                        )
                        # Remove failed handler
                        if message.receiver_id in self._message_handlers:
                            self._message_handlers[message.receiver_id].remove(handler)

        except Exception as e:
            logger.error(f"Error notifying message handlers: {str(e)}")

    async def register_agent(self, agent: BaseAgent) -> bool:
        """Register agent for active communication"""
        try:
            logger.info(f"Attempting to register agent: {agent.agent_id}")

            # Create registration with proper identity and verification, and Capability objects
            registration = AgentRegistration(
                agent_id=agent.agent_id,
                organization_id=agent.metadata.organization_id,
                agent_type=agent.metadata.agent_type,
                interaction_modes=agent.metadata.interaction_modes,
                capabilities=agent.capabilities,  # Use the Capability objects directly
                identity=agent.identity,
                owner_id=agent.metadata.organization_id,
                payment_address=agent.metadata.payment_address,
                metadata=agent.metadata.metadata,
            )

            # Register with central registry first
            if not await self.registry.register(registration):
                logger.error(f"Failed to register agent {agent.agent_id} with registry")
                return False

            # Add to active agents
            self.active_agents[agent.agent_id] = agent

            # Set hub and registry in the agent
            agent.hub = self
            agent.registry = self.registry
            logger.debug(f"Set registry and hub for agent {agent.agent_id}")
            logger.info(f"Successfully registered agent: {agent.agent_id}")
            return True

        except Exception as e:
            logger.exception(f"Error registering agent {agent.agent_id}: {str(e)}")
            return False

    async def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent from active communication"""
        try:
            logger.info(f"Attempting to unregister agent: {agent_id}")

            if agent_id not in self.active_agents:
                logger.warning(f"Agent {agent_id} not found in active agents")
                return False

            # First clear all message handlers for this agent
            self.clear_agent_handlers(agent_id)

            # Remove any global handlers that might be associated with this agent
            self._global_handlers = [
                h
                for h in self._global_handlers
                if getattr(h, "__agent_id__", None) != agent_id
            ]

            agent = self.active_agents[agent_id]
            agent.hub = None
            del self.active_agents[agent_id]

            # Update registry status
            await self.registry.update_registration(agent_id, {"status": "unavailable"})

            # Clean up any pending messages for this agent
            for other_agent in self.active_agents.values():
                if agent_id in other_agent.active_conversations:
                    other_agent.end_conversation(agent_id)

            logger.info(f"Successfully unregistered agent: {agent_id}")
            return True

        except Exception as e:
            logger.exception(f"Error unregistering agent {agent_id}: {str(e)}")
            return False

    async def route_message(self, message: Message) -> bool:
        """
        Route a message between agents without controlling agent behavior.

        This method verifies message security, locates the receiver, delivers the message,
        and tracks it in message history. While it ensures delivery and tracks history,
        it does not dictate how agents respond to messages - each agent maintains its
        independence in processing and responding to messages.

        Args:
            message: The message to route

        Returns:
            True if message was successfully routed, False otherwise
        """
        try:
            logger.debug(
                f"Routing message from {message.sender_id} to {message.receiver_id}"
            )

            # Special handling for system messages
            if message.message_type == MessageType.SYSTEM:
                self._message_history.append(message)
                await self._notify_handlers(message, is_special=True)
                logger.info(f"Added system message to history: {message.content}")
                return True

            # Validate that sender and receiver are different
            if message.sender_id == message.receiver_id:
                logger.error(
                    f"Cannot route message to self: {message.sender_id} -> {message.receiver_id}"
                )
                return False

            # Get sender and receiver
            sender = self.active_agents.get(message.sender_id)
            receiver = self.active_agents.get(message.receiver_id)

            if not sender or not receiver:
                logger.error(
                    f"Sender or receiver not found. Sender: {bool(sender)}, Receiver: {bool(receiver)}"
                )
                return False

            # Handle special message types
            if message.message_type in [MessageType.COOLDOWN, MessageType.STOP]:
                # Store in history and notify handlers before special handling
                self._message_history.append(message)
                await self._notify_handlers(message, is_special=True)

                if message.message_type == MessageType.COOLDOWN:
                    return await self._handle_cooldown_message(message, receiver)
                else:
                    return await self._handle_stop_message(message, sender, receiver)

            # Special handling for collaboration responses
            if message.message_type == MessageType.COLLABORATION_RESPONSE:
                logger.info(
                    f"Received collaboration response from {message.sender_id} to {message.receiver_id}"
                )

                # Check if this is a response to a pending request
                if message.metadata and "response_to" in message.metadata:
                    request_id = message.metadata["response_to"]
                    logger.debug(
                        f"Found response_to metadata with request_id: {request_id}"
                    )

                    if request_id in self.pending_responses:
                        future = self.pending_responses[request_id]
                        logger.debug(
                            f"Found pending future for request_id: {request_id}, future.done(): {future.done()}"
                        )

                        if not future.done():
                            # Check if the future has timed out
                            if hasattr(future, "_timed_out") and getattr(
                                future, "_timed_out", False
                            ):
                                logger.warning(
                                    f"Received late response for timed out request {request_id}"
                                )
                                # Store the late response for potential retrieval
                                self.late_responses[request_id] = message
                                logger.info(
                                    f"Stored late response for request {request_id} for potential future retrieval"
                                )
                                # Even though the request timed out, we still want to record the message
                                # and notify handlers, but we won't set the result on the future
                            else:
                                # Set the result on the future if it hasn't timed out
                                try:
                                    # IMPORTANT: Use call_soon_threadsafe to ensure the future is resolved in the correct event loop
                                    loop = asyncio.get_event_loop()
                                    loop.call_soon_threadsafe(
                                        future.set_result, message
                                    )
                                    logger.debug(
                                        f"Successfully set result for pending request {request_id}"
                                    )
                                except Exception as e:
                                    logger.exception(
                                        f"Error setting result for future: {str(e)}"
                                    )
                            logger.info(
                                f"Successfully handled collaboration response from {message.sender_id} to {message.receiver_id}"
                            )
                        else:
                            logger.debug(
                                f"Future for request {request_id} is already done"
                            )
                    else:
                        logger.warning(
                            f"No pending request found for response with request_id {request_id}"
                        )
                else:
                    logger.warning(
                        f"Collaboration response from {message.sender_id} to {message.receiver_id} has no response_to metadata"
                    )

                self._message_history.append(message)
                await self._notify_handlers(message)
                return True

            # Verify identities
            logger.debug("Verifying sender identity")
            if not await sender.verify_identity():
                logger.error(f"Sender {sender.agent_id} identity verification failed")
                raise SecurityError("Sender identity verification failed")

            logger.debug("Verifying receiver identity")
            if not await receiver.verify_identity():
                logger.error(
                    f"Receiver {receiver.agent_id} identity verification failed"
                )
                raise SecurityError("Receiver identity verification failed")

            # Verify message signature
            logger.debug("Verifying message signature")
            if not message.verify(sender.identity):
                logger.error(
                    f"Message signature verification failed for sender {sender.agent_id}"
                )
                raise SecurityError("Message signature verification failed")

            # Check interaction mode compatibility
            sender_modes = sender.metadata.interaction_modes
            receiver_modes = receiver.metadata.interaction_modes

            logger.debug(
                f"Checking interaction mode compatibility: {sender_modes} -> {receiver_modes}"
            )
            if not any(mode in receiver_modes for mode in sender_modes):
                logger.error(
                    f"Incompatible interaction modes between {sender.agent_id} and {receiver.agent_id}"
                )
                raise ValueError("Incompatible interaction modes")

            # Apply protocol validation for agent-to-agent communication
            if (
                InteractionMode.AGENT_TO_AGENT in sender_modes
                and InteractionMode.AGENT_TO_AGENT in receiver_modes
            ):
                logger.debug("Validating agent-to-agent protocol")
                if not await self.agent_protocol.validate_message(message):
                    logger.error("Agent protocol validation failed")
                    return False

            # Special handling for collaboration requests and responses
            if message.message_type == MessageType.REQUEST_COLLABORATION:
                # Log the collaboration request
                logger.info(
                    f"Collaboration request from {message.sender_id} to {message.receiver_id}: {message.content[:50]}..."
                )

                # Ensure collaboration chain is properly initialized
                if "collaboration_chain" not in message.metadata:
                    message.metadata["collaboration_chain"] = [message.sender_id]
                elif message.sender_id not in message.metadata["collaboration_chain"]:
                    message.metadata["collaboration_chain"].append(message.sender_id)

                # Set original sender if not already set
                if "original_sender" not in message.metadata:
                    message.metadata["original_sender"] = message.sender_id

            # Record in history
            self._message_history.append(message)

            # !IMPORTANT CHANGE: Create a task to deliver the message to the receiver
            # This ensures that the message is processed immediately without waiting for the agent's message queue
            async def deliver_message():
                try:
                    await receiver.receive_message(message)
                    logger.debug(f"Message delivered to {receiver.agent_id}")
                except Exception as e:
                    logger.exception(
                        f"Error delivering message to {receiver.agent_id}: {str(e)}"
                    )

            # Schedule the delivery task
            asyncio.create_task(deliver_message())

            # Notify message handlers
            await self._notify_handlers(message)

            logger.info(
                f"Successfully routed message from {message.sender_id} to {message.receiver_id}"
            )
            return True

        except Exception as e:
            logger.exception(f"Error routing message: {str(e)}")
            return False

    async def _handle_cooldown_message(
        self, message: Message, receiver: BaseAgent
    ) -> bool:
        # Only forward cooldown message if receiver is human
        if receiver.metadata.agent_type == AgentType.HUMAN:
            await receiver.receive_message(message)
        return True

    async def _handle_stop_message(
        self, message: Message, sender: BaseAgent, receiver: BaseAgent
    ) -> bool:
        logger.info(
            f"Received STOP message from {sender.agent_id} to {receiver.agent_id}"
        )
        # Forward the STOP message to the receiver
        await receiver.receive_message(message)
        return True

    async def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get an active agent by ID"""
        try:
            logger.debug(f"Getting agent: {agent_id}")
            return self.active_agents.get(agent_id)
        except Exception as e:
            logger.exception(f"Error getting agent {agent_id}: {str(e)}")
            return None

    async def get_all_agents(self) -> List[BaseAgent]:
        """Get all active agents

        Returns:
            List[BaseAgent]: List of all active agents

        Note:
            This method returns a copy of the active agents list to prevent
            external modification of the internal state.
        """
        try:
            logger.debug("Getting all active agents")
            return list(self.active_agents.values())
        except Exception as e:
            logger.exception(f"Error getting all agents: {str(e)}")
            return []

    async def is_agent_active(self, agent_id: str) -> bool:
        """Check if an agent is active"""
        return agent_id in self.active_agents

    def get_message_history(self) -> List[Message]:
        """Get message history"""
        try:
            logger.debug("Retrieving message history")
            return self._message_history.copy()
        except Exception as e:
            logger.exception(f"Error getting message history: {str(e)}")
            return []

    async def send_message_and_wait_response(
        self,
        sender_id: str,
        receiver_id: str,
        content: str,
        message_type: MessageType = MessageType.REQUEST_COLLABORATION,
        metadata: Optional[Dict] = {},
        timeout: int = 60,
    ) -> Optional[Message]:
        """Send a message and wait for a response.

        Note on timeout behavior:
        When a timeout occurs, this method returns None, but the future remains in pending_responses.
        If a response arrives after the timeout, it will still be processed correctly by the hub,
        but the original caller will have already moved on. Consider using a message queue library
        like asyncio-nats, aiozmq, or AgentForum for more robust agent communication.

        Args:
            sender_id: The ID of the sender agent
            receiver_id: The ID of the receiver agent
            content: The message content
            message_type: The message type
            metadata: Additional metadata to include with the message
            timeout: Maximum time to wait for response in seconds

        Returns:
            The response message, or None if no response was received
        """
        try:
            # Validate sender and receiver
            if sender_id not in self.active_agents:
                logger.error(f"Error: Sender agent {sender_id} is not active")
                return None

            if receiver_id not in self.active_agents:
                logger.error(f"Error: Receiver agent {receiver_id} is not active")
                return None

            # Validate that sender and receiver are different
            if sender_id == receiver_id:
                logger.error(
                    f"Error: Cannot send message to yourself (sender_id={sender_id}, receiver_id={receiver_id})"
                )
                return None

            # Generate a unique request ID
            request_id = metadata.get("request_id", str(uuid.uuid4()))
            logger.debug(
                f"Generated request_id: {request_id} for message from {sender_id} to {receiver_id}"
            )

            # Create metadata with request ID if not provided
            metadata["request_id"] = request_id

            # Create a future to wait for the response
            response_future = asyncio.get_event_loop().create_future()

            # Store the future in pending_responses
            self.pending_responses[request_id] = response_future
            logger.debug(
                f"Stored future for request_id: {request_id} in pending_responses"
            )

            # Create and send the message
            message = Message.create(
                sender_id=sender_id,
                receiver_id=receiver_id,
                content=content,
                sender_identity=(
                    self.active_agents[sender_id].identity
                    if sender_id in self.active_agents
                    else None
                ),
                message_type=message_type,
                metadata=metadata,
            )

            # !IMPORTANT CHANGE: Create a task to route the message
            # This ensures that the message routing doesn't block the event loop
            routing_task = asyncio.create_task(self.route_message(message))

            # Wait for the routing task to complete
            success = await routing_task

            if not success:
                if request_id in self.pending_responses:
                    del self.pending_responses[request_id]
                logger.error(
                    f"Failed to route message from {sender_id} to {receiver_id} with request_id: {request_id}"
                )
                return None

            logger.debug(
                f"Successfully routed message from {sender_id} to {receiver_id} with request_id: {request_id}"
            )

            # Wait for the response with timeout
            try:
                # Create a task to wait for the future to be resolved
                # This approach avoids issues with asyncio.shield and asyncio.wait_for
                done_waiting = False
                start_time = time.time()

                while not done_waiting:
                    # Check if the future is done
                    if response_future.done():
                        logger.debug(
                            f"Future for request_id: {request_id} is done, getting result"
                        )
                        response = response_future.result()
                        return response

                    # Check if we've exceeded the timeout
                    elapsed_time = time.time() - start_time
                    if elapsed_time >= timeout:
                        logger.warning(
                            f"Timeout waiting for response to request {request_id} after {elapsed_time:.2f} seconds"
                        )

                        # Mark the request as timed out but keep it in pending_responses
                        # This allows late responses to be properly handled
                        if request_id in self.pending_responses:
                            # Set a timeout flag on the future
                            setattr(response_future, "_timed_out", True)

                            # Schedule cleanup of the pending response after a grace period
                            # This ensures we don't accumulate too many pending responses
                            async def delayed_cleanup():
                                await asyncio.sleep(60)  # 1 minute grace period
                                if request_id in self.pending_responses:
                                    logger.debug(
                                        f"Cleaning up timed out request {request_id}"
                                    )
                                    del self.pending_responses[request_id]

                            asyncio.create_task(delayed_cleanup())

                        done_waiting = True
                        return None

                    # Yield control to the event loop to allow other tasks to run
                    # This is crucial to allow the response to be processed
                    await asyncio.sleep(0.01)  # 10ms sleep

                return None

            except Exception as e:
                logger.exception(
                    f"Error waiting for response to request {request_id}: {str(e)}"
                )
                return None

        except Exception as e:
            logger.exception(f"Error in send_message_and_wait_response: {str(e)}")
            return None

    async def send_collaboration_request(
        self,
        sender_id: str,
        receiver_id: str,
        task_description: str,
        timeout: int = 60,
        **kwargs,
    ) -> str:
        """
        Facilitate a collaboration request between agents based on capabilities.

        This method creates and routes a collaboration request without controlling the outcome.
        The receiving agent independently decides whether and how to fulfill the request
        based on its own capabilities and decision-making processes.

        Args:
            sender_id: ID of the requesting agent
            receiver_id: ID of the agent being requested to collaborate
            task_description: Description of the task to be performed
            timeout: How long to wait for a response in seconds
            **kwargs: Additional parameters for the collaboration request

        Returns:
            The response content as a string, or an error message if the request failed

        Raises:
            ValueError: If the request could not be sent
            TimeoutError: If the request times out
        """
        try:
            # Validate sender and receiver
            if sender_id not in self.active_agents:
                error_msg = f"Error: Sender agent {sender_id} is not active"
                logger.error(error_msg)
                return error_msg

            if receiver_id not in self.active_agents:
                error_msg = f"Error: Receiver agent {receiver_id} is not active"
                logger.error(error_msg)
                return error_msg

            # Validate that sender and receiver are different
            if sender_id == receiver_id:
                error_msg = f"Error: Cannot send collaboration request to yourself (sender_id={sender_id}, receiver_id={receiver_id})"
                logger.error(error_msg)
                return error_msg

            # Prepare metadata
            metadata = kwargs.copy() if kwargs else {}

            # Ensure collaboration chain is properly initialized
            if "collaboration_chain" not in metadata:
                metadata["collaboration_chain"] = [sender_id]
            elif sender_id not in metadata["collaboration_chain"]:
                metadata["collaboration_chain"].append(sender_id)

            # Set original sender if not already set
            if "original_sender" not in metadata and metadata["collaboration_chain"]:
                metadata["original_sender"] = metadata["collaboration_chain"][0]

            # Log the collaboration request
            logger.info(
                f"Sending collaboration request from {sender_id} to {receiver_id}: {task_description[:50]}..."
            )

            # Generate a unique request ID for tracking
            request_id = str(uuid.uuid4())
            if "request_id" not in metadata:
                metadata["request_id"] = request_id

            # Estimate an appropriate timeout based on task complexity
            # Base timeout of 60 seconds plus 15 seconds per 100 characters, capped at 5 minutes
            estimated_timeout = min(60 + (len(task_description) // 100) * 15, 300)
            effective_timeout = kwargs.get("timeout", estimated_timeout)

            # Send the request and wait for response
            logger.debug(
                f"Sending collaboration request with request_id: {metadata['request_id']}"
            )
            response = await self.send_message_and_wait_response(
                sender_id=sender_id,
                receiver_id=receiver_id,
                content=task_description,
                message_type=MessageType.REQUEST_COLLABORATION,
                metadata=metadata,
                timeout=effective_timeout,
            )

            # Log the response status for debugging
            if response:
                logger.info(
                    f"Received collaboration response from {receiver_id} to {sender_id} with request_id {metadata['request_id']}"
                )

                # Check if the response contains a function call
                if "<function=" in response.content:
                    logger.info(
                        f"Received function call response from {receiver_id} to {sender_id}"
                    )

                return response.content
            else:
                logger.warning(
                    f"No response received from {receiver_id} within {effective_timeout} seconds for request_id {metadata['request_id']}"
                )

                # More helpful error message that provides the request ID for later checking
                return (
                    f"No immediate response received from {receiver_id} within {effective_timeout} seconds. "
                    f"The request is still processing (ID: {metadata['request_id']}). "
                    f"If you receive a response later, it will be available. "
                    f"You can continue with other tasks and check back later."
                )

        except Exception as e:
            error_msg = f"Error sending collaboration request: {str(e)}"
            logger.exception(error_msg)
            return error_msg
