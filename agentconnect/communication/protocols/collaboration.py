"""
Collaboration protocol that enables dynamic capability discovery and task delegation.

This module provides the CollaborationProtocol, which implements communication patterns
for peer-to-peer collaborative interactions between agents. It enables agents to
discover each other's capabilities and delegate tasks without requiring central coordination.
"""

# Standard library imports
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from agentconnect.communication.protocols.base import BaseProtocol

# Absolute imports from agentconnect package
from agentconnect.core.message import Message
from agentconnect.core.types import AgentIdentity, MessageType, ProtocolVersion

# Configure logging
logger = logging.getLogger("CollaborationProtocol")


@dataclass
class RequestCapabilityPayload:
    """
    Payload for dynamically discovering capabilities from other agents.

    This structure enables an agent to search for specific capabilities across
    the network without needing to know in advance which agents provide them.
    """

    capability_name: Optional[str] = None
    capability_description: Optional[str] = None  # For semantic search
    input_schema: Optional[Dict[str, str]] = None
    limit: Optional[int] = 10  # Limit the number of results


@dataclass
class CapabilityResponsePayload:
    """
    Response payload containing discovered capabilities that match a request.

    This structure enables peer-to-peer capability discovery by returning
    matching capabilities from agents across the network.
    """

    request_id: str
    capabilities: List[Dict[str, Any]]  # List of simplified Capability dicts
    # capabilities: List[Capability] # List of Capability objects


@dataclass
class RequestCollaborationPayload:
    """
    Payload for requesting peer-to-peer collaboration on a specific capability.

    This structure enables an agent to request another agent's services
    based on its capabilities, forming dynamic collaborative relationships.
    """

    capability_name: str
    input_data: Dict[str, Any]


@dataclass
class CollaborationResponsePayload:
    """
    Response payload from an agent providing its capability as a service.

    This structure enables agents to share results after performing
    a requested capability, completing the peer-to-peer collaboration.
    """

    request_id: str
    success: bool
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


@dataclass
class CollaborationErrorPayload:
    """
    Error payload for a collaboration attempt that couldn't be completed.

    This structure provides standardized error reporting in peer-to-peer
    collaboration scenarios.
    """

    request_id: str
    error_code: str
    error_message: str


class CollaborationProtocol(BaseProtocol):
    """
    Protocol that enables peer-to-peer agent collaboration and capability sharing.

    This protocol facilitates dynamic discovery and utilization of capabilities across
    a network of independent agents. It allows agents to:

    1. Discover what other agents can do through capability queries
    2. Request help from agents with relevant capabilities
    3. Share results after task completion

    Agents maintain their independence - each agent decides whether to accept
    collaboration requests based on its own criteria. The protocol simply
    standardizes the communication pattern without imposing central control.
    """

    def __init__(self):
        """Initialize the collaboration protocol with supported message types."""
        super().__init__()
        self.version = ProtocolVersion.V1_0
        # Add all collaboration message types
        self.supported_message_types.update(
            {
                MessageType.CAPABILITY,
                MessageType.REQUEST_COLLABORATION,
                MessageType.COLLABORATION_RESPONSE,
                MessageType.COLLABORATION_ERROR,
            }
        )

    async def format_message(
        self,
        sender_id: str,
        receiver_id: str,
        content: str,  # Content will now often be a serialized dataclass
        sender_identity: AgentIdentity,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict] = None,
    ) -> Message:
        """Format a message according to the collaboration protocol."""
        try:
            logger.debug(f"Formatting message from {sender_id} to {receiver_id}")

            if not self._check_message_type(message_type):
                logger.error(f"Unsupported message type: {message_type}")
                raise ValueError(f"Message type {message_type} not supported")

            base_metadata = {
                "protocol_version": self.version,
                "protocol_type": "collaboration",
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
        """Validate message against protocol requirements."""
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
