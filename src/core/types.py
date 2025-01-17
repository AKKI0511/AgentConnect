from enum import Enum
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime


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
    VERIFICATION = "verification"  # New: For identity verification
    CAPABILITY = "capability"
    PROTOCOL = "protocol"


class NetworkMode(Enum):
    STANDALONE = "standalone"
    NETWORKED = "networked"


class SecurityError(Exception):
    """Raised when message verification fails"""

    pass
