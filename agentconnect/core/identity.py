"""Agent identity value types.

Identity is a noun: a DID, keys, and verification status. Key generation still
uses RSA here; Ed25519 arrives with join authentication.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from agentconnect.core.types import AgentType, InteractionMode


class VerificationStatus(str, Enum):
    """Status of Agent identity verification."""

    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass
class AgentIdentity:
    """Decentralized identity for an Agent, including keys used to sign Messages."""

    did: str
    public_key: str
    private_key: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)

    @classmethod
    def create_key_based(cls) -> "AgentIdentity":
        """Create a key-based identity with a generated RSA key pair."""
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        public_key = private_key.public_key()

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        key_fingerprint = base64.urlsafe_b64encode(
            public_key.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        ).decode("utf-8")[:16]
        did = f"did:key:{key_fingerprint}"

        return cls(
            did=did,
            public_key=public_pem,
            private_key=private_pem,
            verification_status=VerificationStatus.VERIFIED,
            metadata={
                "key_type": "RSA",
                "key_size": 2048,
                "creation_method": "key_based",
            },
        )

    def sign_message(self, message: str) -> str:
        """Sign a message using the private key and return a base64 signature."""
        if not self.private_key:
            raise ValueError("Private key not available for signing")

        private_key = serialization.load_pem_private_key(
            self.private_key.encode(), password=None, backend=default_backend()
        )

        signature = private_key.sign(
            message.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode()

    def verify_signature(self, message: str, signature: str) -> bool:
        """Return True when ``signature`` matches ``message`` under the public key."""
        try:
            public_key = serialization.load_pem_public_key(
                self.public_key.encode(), backend=default_backend()
            )
            public_key.verify(
                base64.b64decode(signature),
                message.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False

    def to_dict(self) -> Dict:
        """Return a serializable public view of this identity."""
        return {
            "did": self.did,
            "public_key": self.public_key,
            "verification_status": self.verification_status.value,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "AgentIdentity":
        """Create an identity from ``to_dict`` output. The private key is omitted."""
        return cls(
            did=data["did"],
            public_key=data["public_key"],
            verification_status=VerificationStatus(data["verification_status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AgentMetadata:
    """Registration metadata for an Agent, distinct from its discovery Profile."""

    agent_id: str
    agent_type: AgentType
    identity: AgentIdentity
    organization_id: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    interaction_modes: List[InteractionMode] = field(default_factory=list)
    payment_address: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
