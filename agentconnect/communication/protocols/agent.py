"""
Agent protocol implementation that enables secure peer-to-peer communication.

This module provides the SimpleAgentProtocol, which implements the basic
communication framework for direct agent-to-agent interactions with cryptographic
security and message verification.
"""

# Standard library imports
import logging
from typing import Dict, Optional

from agentconnect.communication.protocols.base import BaseProtocol

# Absolute imports from agentconnect package
from agentconnect.core.message import Message
from agentconnect.core.types import AgentIdentity, MessageType, ProtocolVersion

# Configure logging
logger = logging.getLogger("AgentProtocol")


class SimpleAgentProtocol(BaseProtocol):
    """
    Protocol that ensures secure peer-to-peer agent communication.

    This protocol handles message formatting, cryptographic verification, and validation
    for direct communication between agents. It ensures that messages are properly
    signed and can be verified by the receiving agent, maintaining security in
    peer-to-peer interactions.
    """

    def __init__(self):
        """Initialize the agent protocol with supported message types."""
        super().__init__()
        self.version = ProtocolVersion.V1_0
        # Add all collaboration and capability message types for agent communication
        self.supported_message_types.update(
            {MessageType.CAPABILITY, MessageType.PROTOCOL}
        )

    async def format_message(
        self,
        sender_id: str,
        receiver_id: str,
        content: str,
        sender_identity: AgentIdentity,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict] = None,
    ) -> Message:
        """Format a message with proper protocol metadata"""
        try:
            logger.debug(f"Formatting message from {sender_id} to {receiver_id}")

            if not self._check_message_type(message_type):
                logger.error(f"Unsupported message type: {message_type}")
                raise ValueError(f"Message type {message_type} not supported")

            base_metadata = {
                "protocol_version": self.version,
                "protocol_type": "agent",
            }

            if metadata:
                base_metadata.update(metadata)

            message = Message.create(
                sender_id=sender_id,
                receiver_id=receiver_id,
                content=content,
                sender_identity=sender_identity,
                message_type=message_type,
                metadata=base_metadata,
            )

            logger.debug("Message formatted successfully")
            return message

        except Exception as e:
            logger.exception(f"Error formatting message: {str(e)}")
            raise

    async def validate_message(self, message: Message) -> bool:
        """Validate message against protocol requirements"""
        try:
            logger.debug(f"Validating message from {message.sender_id}")

            # Protocol version check
            protocol_version = message.protocol_version
            if protocol_version != self.version:
                logger.error(
                    f"Protocol version mismatch. Expected {self.version}, got {protocol_version}"
                )
                return False

            # Message type validation
            if not self._check_message_type(message.message_type):
                logger.error(f"Unsupported message type: {message.message_type}")
                return False

            logger.debug("Message validation successful")
            return True

        except Exception as e:
            logger.exception(f"Error validating message: {str(e)}")
            return False
