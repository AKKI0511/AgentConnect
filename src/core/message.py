from dataclasses import dataclass, field
from datetime import datetime
import uuid
from typing import Dict, Optional
import hashlib
import base64

from src.core.types import (
    MessageType,
    AgentIdentity,
    ProtocolVersion,
    SecurityError,
    VerificationStatus,
)


@dataclass
class Message:
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
        """Create a new signed message"""
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
        """Sign message with sender's private key"""
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
        """Verify message signature using sender's public key"""
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
        """Get message content for signing/verification"""
        return f"{self.id}:{self.sender_id}:{self.receiver_id}:{self.content}:{self.timestamp.isoformat()}"
