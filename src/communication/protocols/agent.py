import logging
from typing import Dict, Optional

from src.core.message import Message
from src.core.types import MessageType, AgentIdentity, ProtocolVersion
from .base import BaseProtocol

logger = logging.getLogger("AgentProtocol")


class SimpleAgentProtocol(BaseProtocol):
    """Protocol implementation for agent-to-agent communication"""

    def __init__(self):
        super().__init__()
        self.version = ProtocolVersion.V1_0
        # Add CAPABILITY and PROTOCOL message types for agent communication
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

            # Basic message structure validation
            if not all(
                [
                    message.sender_id,
                    message.receiver_id,
                    message.content,
                    message.signature,
                    isinstance(message.message_type, MessageType),
                ]
            ):
                logger.error("Message missing required fields")
                return False

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
