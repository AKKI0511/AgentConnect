"""
Core type definitions for the AgentConnect framework.

This module provides the fundamental types, enumerations, and data structures
used throughout the framework, including agent identities, capabilities, and
message types.
"""

import base64

# Standard library imports
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

# Third-party imports
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


class ModelProvider(str, Enum):
    """
    Supported AI model providers.

    This enum defines the supported model providers for AI agents.
    """

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    GOOGLE = "google"


class ModelName(str, Enum):
    """
    Supported model names for each provider.

    This enum defines the specific model names available for each provider.
    """

    # OpenAI Models
    GPT4_5_PREVIEW = "gpt-4.5-preview-2025-02-27"
    GPT4_1 = "gpt-4.1"
    GPT4_1_MINI = "gpt-4.1-mini"
    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    O1 = "o1"
    O1_MINI = "o1-mini"
    O3 = "o3"
    O3_MINI = "o3-mini"
    O4_MINI = "o4-mini"

    # Anthropic Models
    CLAUDE_3_7_SONNET = "claude-3-7-sonnet-latest"
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet-latest"
    CLAUDE_3_5_HAIKU = "claude-3-5-haiku-latest"
    CLAUDE_3_OPUS = "claude-3-opus-latest"
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    CLAUDE_3_HAIKU = "claude-3-haiku-20240307"

    # Groq Models
    LLAMA33_70B_VTL = "llama-3.3-70b-versatile"
    LLAMA3_1_8B_INSTANT = "llama-3.1-8b-instant"
    LLAMA_GUARD3_8B = "llama-guard-3-8b"
    LLAMA3_70B = "llama3-70b-8192"
    LLAMA3_8B = "llama3-8b-8192"
    MIXTRAL = "mixtral-8x7b-32768"
    GEMMA2_90B = "gemma2-9b-it"

    # Google Models
    GEMINI2_5_PRO_PREVIEW = "gemini-2.5-pro-preview-03-25"
    GEMINI2_5_PRO_EXP = "gemini-2.5-pro-exp-03-25"
    GEMINI2_5_FLASH_PREVIEW = "gemini-2.5-flash-preview-04-17"
    GEMINI2_FLASH = "gemini-2.0-flash"
    GEMINI2_FLASH_LITE = "gemini-2.0-flash-lite"
    GEMINI2_PRO_EXP = "gemini-2.0-pro-exp-02-05"
    GEMINI2_FLASH_THINKING_EXP = "gemini-2.0-flash-thinking-exp-01-21"
    GEMINI1_5_FLASH = "gemini-1.5-flash"
    GEMINI1_5_PRO = "gemini-1.5-pro"

    @classmethod
    def get_default_for_provider(cls, provider: ModelProvider) -> "ModelName":
        """
        Get the default model for a given provider.

        Args:
            provider: The model provider to get the default model for

        Returns:
            The default model name for the provider

        Raises:
            ValueError: If no default model is defined for the provider
        """
        defaults = {
            ModelProvider.OPENAI: cls.GPT4O,
            ModelProvider.ANTHROPIC: cls.CLAUDE_3_SONNET,
            ModelProvider.GROQ: cls.LLAMA33_70B_VTL,
            ModelProvider.GOOGLE: cls.GEMINI2_FLASH,
        }

        if provider not in defaults:
            raise ValueError(f"No default model defined for provider {provider}")

        return defaults[provider]


class AgentType(str, Enum):
    """
    Types of agents in the system.

    This enum defines the different types of agents that can exist in the system.
    """

    HUMAN = "human"
    AI = "ai"


class InteractionMode(str, Enum):
    """
    Supported interaction modes between agents.

    This enum defines the different ways agents can interact with each other.
    """

    HUMAN_TO_AGENT = "human_to_agent"
    AGENT_TO_AGENT = "agent_to_agent"


class ProtocolVersion(str, Enum):
    """
    Supported protocol versions for agent communication.

    This enum defines the different protocol versions that can be used for
    communication between agents.
    """

    V1_0 = "1.0"
    V1_1 = "1.1"


class VerificationStatus(str, Enum):
    """
    Status of agent identity verification.

    This enum defines the different states of agent identity verification.
    """

    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass
class Capability:
    """
    Capability definition for agents.

    This class defines a capability that an agent can provide, including
    its name, description, and input/output schemas.

    Attributes:
        name: Name of the capability
        description: Description of what the capability does
        input_schema: Schema for the input data
        output_schema: Schema for the output data
        version: Version of the capability
    """

    name: str
    description: str
    input_schema: Optional[Dict[str, str]] = None
    output_schema: Optional[Dict[str, str]] = None
    version: str = "1.0"


@dataclass
class AgentIdentity:
    """
    Decentralized Identity for Agents.

    This class provides identity management for agents, including
    cryptographic keys for signing and verification.

    Attributes:
        did: Decentralized Identifier
        public_key: Public key for verification
        private_key: Private key for signing (optional)
        verification_status: Status of identity verification
        created_at: When the identity was created
        metadata: Additional information about the identity
    """

    did: str  # Decentralized Identifier
    public_key: str
    private_key: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)

    @classmethod
    def create_key_based(cls) -> "AgentIdentity":
        """
        Create a new key-based identity for an agent.

        This method generates a new RSA key pair and creates a key-based
        decentralized identifier (DID) for the agent.

        Returns:
            A new AgentIdentity with generated keys and DID
        """
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
        """
        Sign a message using the private key.

        Args:
            message: The message to sign

        Returns:
            Base64-encoded signature

        Raises:
            ValueError: If the private key is not available
        """
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
        """
        Verify a message signature using the public key.

        Args:
            message: The message that was signed
            signature: The base64-encoded signature to verify

        Returns:
            True if the signature is valid, False otherwise
        """
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
        """
        Convert identity to dictionary format.

        Returns:
            Dictionary representation of the identity
        """
        return {
            "did": self.did,
            "public_key": self.public_key,
            "verification_status": self.verification_status.value,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "AgentIdentity":
        """
        Create identity from dictionary format.

        Args:
            data: Dictionary containing identity data

        Returns:
            AgentIdentity instance created from the dictionary
        """
        return cls(
            did=data["did"],
            public_key=data["public_key"],
            verification_status=VerificationStatus(data["verification_status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AgentMetadata:
    """
    Metadata for an agent.

    This class contains metadata about an agent, including its ID, type,
    capabilities, and interaction modes.

    Attributes:
        agent_id: Unique identifier for the agent
        agent_type: Type of agent (human, AI)
        identity: Agent's decentralized identity
        organization_id: ID of the organization the agent belongs to
        capabilities: List of capability names the agent provides
        interaction_modes: Supported interaction modes
        payment_address: Agent's primary wallet address for receiving payments
        metadata: Additional information about the agent
    """

    agent_id: str
    agent_type: AgentType
    identity: AgentIdentity
    organization_id: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    interaction_modes: List[InteractionMode] = field(default_factory=list)
    payment_address: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


class MessageType(str, Enum):
    """
    Types of messages that can be exchanged between agents.

    This enum defines the different types of messages that can be sent
    between agents in the system.
    """

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
    IGNORE = "ignore"
    REQUEST_COLLABORATION = "request_collaboration"
    COLLABORATION_RESPONSE = "collaboration_response"
    COLLABORATION_ERROR = "collaboration_error"


class NetworkMode(str, Enum):
    """
    Network modes for agent communication.

    This enum defines the different network modes that can be used for
    agent communication.
    """

    STANDALONE = "standalone"
    NETWORKED = "networked"
