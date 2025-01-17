from abc import ABC, abstractmethod
from typing import Optional, Dict
import logging

from src.core.message import Message
from src.core.types import MessageType, AgentIdentity, ProtocolVersion

# Configure logging
logger = logging.getLogger("Protocol")


class BaseProtocol(ABC):
    """Base protocol interface for all communication types"""

    def __init__(self):
        self.version = ProtocolVersion.V1_0
        self.supported_message_types = {
            MessageType.TEXT,
            MessageType.COMMAND,
            MessageType.RESPONSE,
            MessageType.VERIFICATION,
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
        """Format a message according to protocol specifications"""
        pass

    @abstractmethod
    async def validate_message(self, message: Message) -> bool:
        """Validate message format and contents"""
        pass

    def _check_message_type(self, message_type: MessageType) -> bool:
        """Verify message type is supported by protocol"""
        return message_type in self.supported_message_types
