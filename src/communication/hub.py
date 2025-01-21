import logging
from typing import Dict, List, Optional

from src.core.agent import BaseAgent
from src.core.types import AgentType, InteractionMode, MessageType, SecurityError
from src.core.message import Message
from src.core.registry import AgentRegistration, AgentRegistry
from src.communication.protocols.agent import SimpleAgentProtocol
from src.utils.logging_config import LogLevel, setup_logging

# Configure logging
setup_logging(
    level=LogLevel.DEBUG,
    module_levels={
        "CommunicationHub": LogLevel.DEBUG,
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

            agent = self.active_agents[agent_id]
            agent.hub = None
            del self.active_agents[agent_id]

            # Update registry status
            await self.registry.update_registration(agent_id, {"status": "unavailable"})
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
            if message.message_type == MessageType.COOLDOWN:
                return await self._handle_cooldown_message(message, receiver)
            elif message.message_type == MessageType.STOP:
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

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get an active agent by ID"""
        try:
            logger.debug(f"Getting agent: {agent_id}")
            return self.active_agents.get(agent_id)
        except Exception as e:
            logger.exception(f"Error getting agent {agent_id}: {str(e)}")
            return None

    def get_message_history(self) -> List[Message]:
        """Get message history"""
        try:
            logger.debug("Retrieving message history")
            return self._message_history.copy()
        except Exception as e:
            logger.exception(f"Error getting message history: {str(e)}")
            return []
