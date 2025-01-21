from enum import Enum
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
import base64


class ModelProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    GOOGLE = "google"
    META = "meta"
    XMISTRAL = "mistral"
    OLLAMA = "ollama"


class ModelName(Enum):
    # OpenAI Models
    GPT4_TURBO = "gpt-4-turbo-preview"
    GPT4 = "gpt-4"
    GPT35_TURBO = "gpt-3.5-turbo"

    # Anthropic Models
    CLAUDE_3_OPUS = "claude-3-opus-20240229"
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    CLAUDE_3_HAIKU = "claude-3-haiku-20240307"

    # Groq Models
    MIXTRAL = "mixtral-8x7b-32768"
    LLAMA3_70B = "llama3-70b-8192"
    LLAMA3_8B = "llama3-8b-8192"
    LLAMA33_70B_VTL = "llama-3.3-70b-versatile"
    LLAMA_GUARD3_8B = "llama-guard-3-8b"
    GEMMA2_90B = "gemma2-9b-it"

    # Google Models
    GEMINI_PRO = "gemini-pro"
    GEMINI_PRO_VISION = "gemini-pro-vision"

    # Meta Models (via Ollama)
    LLAMA2_7B = "llama2:7b"
    LLAMA2_13B = "llama2:13b"
    LLAMA2_70B_OLLAMA = "llama2:70b"

    # Mistral Models
    MISTRAL_TINY = "mistral-tiny"
    MISTRAL_SMALL = "mistral-small"
    MISTRAL_MEDIUM = "mistral-medium"


class AgentType(Enum):
    HUMAN = "human"
    AI = "ai"


class InteractionMode(Enum):
    HUMAN_TO_AGENT = "human_to_agent"
    AGENT_TO_AGENT = "agent_to_agent"


class ProtocolVersion(Enum):
    V1_0 = "1.0"
    V1_1 = "1.1"


class VerificationStatus(Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass
class AgentIdentity:
    """Decentralized Identity for Agents"""

    did: str  # Decentralized Identifier
    public_key: str
    private_key: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)

    @classmethod
    def create_key_based(cls) -> "AgentIdentity":
        """Create a new key-based identity for an agent"""
        # Generate RSA key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        public_key = private_key.public_key()

        # Serialize keys to PEM format
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        # Generate DID using key fingerprint
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
        """Sign a message using the private key"""
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
        """Verify a message signature using the public key"""
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
        """Convert identity to dictionary format"""
        return {
            "did": self.did,
            "public_key": self.public_key,
            "verification_status": self.verification_status.value,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "AgentIdentity":
        """Create identity from dictionary format"""
        return cls(
            did=data["did"],
            public_key=data["public_key"],
            verification_status=VerificationStatus(data["verification_status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AgentMetadata:
    agent_id: str
    agent_type: AgentType
    identity: AgentIdentity
    organization_id: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    interaction_modes: List[InteractionMode] = field(default_factory=list)
    verification_status: bool = False
    metadata: Dict = field(default_factory=dict)


class MessageType(Enum):
    TEXT = "text"
    COMMAND = "command"
    RESPONSE = "response"
    ERROR = "error"
    VERIFICATION = "verification"
    CAPABILITY = "capability"
    PROTOCOL = "protocol"
    STOP = "stop"
    SYSTEM = "system"
    COOLDOWN = "cooldown"


class NetworkMode(Enum):
    STANDALONE = "standalone"
    NETWORKED = "networked"


class SecurityError(Exception):
    """Raised when message verification fails"""

    pass
