"""
Foundation for all communication protocols in the AgentConnect framework.

This module defines the core protocol interface that standardizes message format
and validation across different communication patterns, enabling consistent
peer-to-peer agent interactions and collaboration.
"""

import logging

# Standard library imports
from abc import ABC, abstractmethod
from typing import Dict, Optional

from agentconnect.core.message import Message

# Absolute imports from agentconnect package
from agentconnect.core.types import AgentIdentity, MessageType, ProtocolVersion

# Configure logging
logger = logging.getLogger("Protocol")


class BaseProtocol(ABC):
    """
    Foundation for all agent communication protocols.

    This abstract class defines the common interface and baseline functionality for all
    communication protocols, ensuring consistent message handling across different interaction
    patterns. It provides the foundation for both basic agent-to-agent messaging and
    more complex collaboration patterns based on capability discovery.

    The protocol system enables standardized communication without requiring central control
    of agent behavior - it simply ensures messages are properly formatted, signed, and validated.
    """

    def __init__(self):
        """Initialize the base protocol with default version and supported message types."""
        self.version = ProtocolVersion.V1_0
        self.supported_message_types = {
            MessageType.TEXT,
            MessageType.COMMAND,
            MessageType.RESPONSE,
            MessageType.VERIFICATION,
            MessageType.SYSTEM,
            MessageType.ERROR,
            # Add basic collaboration and capability types to base protocol
            MessageType.REQUEST_COLLABORATION,
            MessageType.COLLABORATION_RESPONSE,
            MessageType.COLLABORATION_ERROR,
        }

    @abstractmethod
    async def format_message(
        self,
        sender_id: str,
        receiver_id: str,
        content: str,
        sender_identity: AgentIdentity,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict] = None,
    ) -> Message:
        """
        Format a message according to protocol specifications.

        Args:
            sender_id: ID of the sending agent
            receiver_id: ID of the receiving agent
            content: Message content
            sender_identity: Identity of the sending agent
            message_type: Type of message being sent
            metadata: Additional metadata for the message

        Returns:
            A properly formatted Message object
        """
        pass

    @abstractmethod
    async def validate_message(self, message: Message) -> bool:
        """
        Validate message format and contents.

        Args:
            message: The message to validate

        Returns:
            True if the message is valid, False otherwise
        """
        pass

    def _check_message_type(self, message_type: MessageType) -> bool:
        """
        Verify message type is supported by protocol.

        Args:
            message_type: The message type to check

        Returns:
            True if the message type is supported, False otherwise
        """
        return message_type in self.supported_message_types
