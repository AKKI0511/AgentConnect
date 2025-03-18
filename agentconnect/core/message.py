"""
Message handling for the AgentConnect framework.

This module provides the Message class for creating, signing, and verifying
messages exchanged between agents in the system.
"""

import base64
import hashlib
import uuid

# Standard library imports
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

# Absolute imports from agentconnect package
from agentconnect.core.exceptions import SecurityError
from agentconnect.core.types import (
    AgentIdentity,
    MessageType,
    ProtocolVersion,
    VerificationStatus,
)


@dataclass
class Message:
    """
    Message class for agent communication.

    This class represents messages exchanged between agents, with support for
    content, metadata, and cryptographic signatures for verification.

    Attributes:
        id: Unique identifier for the message
        sender_id: ID of the sending agent
        receiver_id: ID of the receiving agent
        content: Message content
        message_type: Type of message (text, command, response, etc.)
        timestamp: When the message was created
        metadata: Additional information about the message
        protocol_version: Version of the communication protocol
        signature: Cryptographic signature for verification
    """

    id: str
    sender_id: str
    receiver_id: str
    content: str
    message_type: MessageType
    timestamp: datetime
    metadata: Dict = field(default_factory=dict)
    protocol_version: ProtocolVersion = ProtocolVersion.V1_0
    signature: Optional[str] = None

    @classmethod
    def create(
        cls,
        sender_id: str,
        receiver_id: str,
        content: str,
        sender_identity: AgentIdentity,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict] = None,
    ) -> "Message":
        """
        Create a new signed message.

        Args:
            sender_id: ID of the sending agent
            receiver_id: ID of the receiving agent
            content: Message content
            sender_identity: Identity of the sending agent
            message_type: Type of message being sent
            metadata: Additional information about the message

        Returns:
            A signed Message object

        Raises:
            ValueError: If the sender identity doesn't have a private key for signing
        """
        msg = cls(
            id=str(uuid.uuid4()),
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
            message_type=message_type,
            timestamp=datetime.now(),
            metadata=metadata or {},
            protocol_version=ProtocolVersion.V1_0,
        )
        msg.sign(sender_identity)
        return msg

    def sign(self, identity: AgentIdentity) -> None:
        """
        Sign message with sender's private key.

        Args:
            identity: The identity containing the private key for signing

        Raises:
            ValueError: If the identity doesn't have a private key
        """
        if not identity.private_key:
            raise ValueError("Private key required for signing")

        # Create message digest
        message_content = self._get_signable_content()
        digest = hashlib.sha256(message_content.encode()).digest()

        # For MVP, we'll use a simple signature scheme
        # In production, use proper asymmetric encryption
        signature = base64.b64encode(digest).decode()
        self.signature = signature

    def verify(self, sender_identity: AgentIdentity) -> bool:
        """
        Verify message signature using sender's public key.

        Args:
            sender_identity: The identity containing the public key for verification

        Returns:
            True if the signature is valid, False otherwise

        Raises:
            SecurityError: If the sender identity is not verified
        """
        if not self.signature:
            return False

        if sender_identity.verification_status != VerificationStatus.VERIFIED:
            raise SecurityError("Sender identity not verified")

        # Recreate message digest
        message_content = self._get_signable_content()
        current_digest = hashlib.sha256(message_content.encode()).digest()

        # Compare with stored signature
        stored_digest = base64.b64decode(self.signature)
        return current_digest == stored_digest

    def _get_signable_content(self) -> str:
        """
        Get message content for signing/verification.

        Returns:
            A string representation of the message content for signing
        """
        return f"{self.id}:{self.sender_id}:{self.receiver_id}:{self.content}:{self.timestamp.isoformat()}"
