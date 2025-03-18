import logging
from typing import Awaitable, Callable, Dict, List, Optional

from src.communication.protocols.agent import SimpleAgentProtocol
from src.core.agent import BaseAgent
from src.core.message import Message
from src.core.registry import AgentRegistration, AgentRegistry
from src.core.types import AgentType, InteractionMode, MessageType, SecurityError
from src.utils.logging_config import LogLevel, setup_logging

# Configure logging
setup_logging(
    level=LogLevel.INFO,
    module_levels={
        "CommunicationHub": LogLevel.INFO,
        "AgentRegistry": LogLevel.INFO,
        "src.core.agent": LogLevel.INFO,
        "src.core.types": LogLevel.INFO,
        "src.core.message": LogLevel.INFO,
        "src.core.registry": LogLevel.INFO,
        "src.communication.protocols.agent": LogLevel.INFO,
        "src.utils.logging_config": LogLevel.INFO,
    },
)
logger = logging.getLogger("CommunicationHub")


class CommunicationHub:
    """Handles all agent communication and message routing"""

    def __init__(self, registry: AgentRegistry):
        logger.info("Initializing CommunicationHub")
        self.registry = registry
        self.active_agents: Dict[str, BaseAgent] = {}
        self._message_history: List[Message] = []
        self.agent_protocol = SimpleAgentProtocol()
        self._message_handlers: Dict[
            str, List[Callable[[Message], Awaitable[None]]]
        ] = {}
        self._global_handlers: List[Callable[[Message], Awaitable[None]]] = []

    def add_message_handler(
        self, agent_id: str, handler: Callable[[Message], Awaitable[None]]
    ) -> None:
        """Add a message handler for a specific agent

        Args:
            agent_id (str): The ID of the agent to handle messages for
            handler (Callable): Async function that takes a Message and returns None

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

            # Create registration with proper identity and verification
            registration = AgentRegistration(
                agent_id=agent.agent_id,
                organization_id=agent.metadata.organization_id,
                agent_type=agent.metadata.agent_type,
                interaction_modes=agent.metadata.interaction_modes,
                capabilities=agent.metadata.capabilities,
                identity=agent.identity,
                owner_id=agent.metadata.organization_id,
                metadata=agent.metadata.metadata,
            )

            # Register with central registry first
            if not await self.registry.register(registration):
                logger.error(f"Failed to register agent {agent.agent_id} with registry")
                return False

            # Add to active agents
            self.active_agents[agent.agent_id] = agent
            agent.hub = self
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
        """Route message between agents with verification"""
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

            # Record in history and deliver
            self._message_history.append(message)
            await receiver.receive_message(message)

            # Notify message handlers
            await self._notify_handlers(message)

            logger.info(
                f"Successfully routed message from {sender.agent_id} to {receiver.agent_id}"
            )
            return True

        except SecurityError as e:
            logger.error(f"Security error in message routing: {str(e)}")
            raise
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

    def get_message_history(self) -> List[Message]:
        """Get message history"""
        try:
            logger.debug("Retrieving message history")
            return self._message_history.copy()
        except Exception as e:
            logger.exception(f"Error getting message history: {str(e)}")
            return []
