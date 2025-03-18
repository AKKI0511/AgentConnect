from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

from agentconnect.core.types import ModelProvider, ModelName, InteractionMode


class MessageType(str, Enum):
    TEXT = "text"
    PING = "ping"
    ERROR = "error"
    INFO = "info"
    SYSTEM = "system"
    RESPONSE = "response"
    STOP = "stop"
    COOLDOWN = "cooldown"

    @classmethod
    def has_value(cls, value):
        return value in [item.value for item in cls]


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Token(BaseModel):
    """Authentication token model"""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class BaseMessageModel(BaseModel):
    """Base model with datetime handling"""

    model_config = {
        "json_encoders": {datetime: lambda dt: dt.isoformat()},
        "arbitrary_types_allowed": True,
        "use_enum_values": True,
    }


class ChatMessage(BaseMessageModel):
    """Base message model for all chat communications"""

    content: str = Field(..., description="Message content")
    role: MessageRole = Field(..., description="Role of the message sender")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Message timestamp"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional message metadata"
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


class WebSocketMessage(BaseMessageModel):
    """Model for WebSocket communication"""

    type: MessageType = Field(..., description="Type of message")
    content: Optional[str] = Field(None, description="Message content")
    sender: Optional[str] = Field(None, description="Sender identifier")
    receiver: Optional[str] = Field(None, description="Receiver identifier")
    timestamp: Union[str, datetime] = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Message timestamp",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Message metadata"
    )

    @field_validator("type", mode="before")
    @classmethod
    def validate_message_type(cls, v):
        if isinstance(v, MessageType):
            return v
        if not MessageType.has_value(v):
            raise ValueError(f"Invalid message type: {v}")
        return v

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_datetime(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class AgentConfigRequest(BaseModel):
    """Configuration model for individual agents in a session"""

    provider: ModelProvider = Field(..., description="AI provider to use")
    model: Optional[ModelName] = Field(
        None, description="Specific model to use (optional)"
    )
    capabilities: Optional[List[str]] = Field(
        default=["conversation"], description="Agent capabilities"
    )
    personality: Optional[str] = Field(
        None, description="Agent personality description"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional agent-specific metadata"
    )

    model_config = {"use_enum_values": True}


class CreateSessionRequest(BaseModel):
    """Request model for creating a new chat session with multiple agents"""

    session_type: str = Field(
        ..., pattern="^(human_agent|agent_agent)$", description="Type of session"
    )
    agents: Dict[str, AgentConfigRequest] = Field(
        ...,
        description="Configuration for each agent in the session. Key is the agent identifier (e.g., 'agent1', 'agent2')",
    )
    interaction_modes: Optional[List[InteractionMode]] = Field(
        default=None, description="Interaction modes for the session"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional session metadata"
    )

    @field_validator("agents")
    @classmethod
    def validate_agents(cls, v, values):
        session_type = values.data.get("session_type")
        if session_type == "human_agent" and len(v) != 1:
            raise ValueError(
                "human_agent sessions must have exactly one AI agent configuration"
            )
        elif session_type == "agent_agent" and len(v) != 2:
            raise ValueError(
                "agent_agent sessions must have exactly two agent configurations"
            )
        return v

    model_config = {"use_enum_values": True}


class AgentMetadata(BaseModel):
    """Metadata model for agent information in session response"""

    agent_id: str = Field(..., description="Unique agent identifier")
    provider: ModelProvider = Field(..., description="AI provider used")
    model: ModelName = Field(..., description="Model used")
    capabilities: List[str] = Field(..., description="Agent capabilities")
    personality: Optional[str] = Field(None, description="Agent personality")
    status: str = Field(default="active", description="Agent status")


class SessionResponse(BaseMessageModel):
    """Enhanced response model for session operations with detailed agent information"""

    session_id: str = Field(..., description="Unique session identifier")
    type: MessageType = Field(..., description="Session type")
    created_at: datetime = Field(..., description="Session creation timestamp")
    status: str = Field(default="active", description="Session status")
    session_type: str = Field(
        ..., description="Type of session (human_agent or agent_agent)"
    )
    agents: Dict[str, AgentMetadata] = Field(
        ..., description="Information about each agent in the session"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Session metadata"
    )


class ChatSession(BaseModel):
    session_id: str = Field(..., description="Unique session identifier")
    agent_config: Dict[str, Any] = Field(
        ..., description="Agent configuration for this session"
    )
    messages: List[ChatMessage] = Field(
        default_factory=list, description="List of messages in the session"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Session creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update timestamp"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Session metadata"
    )


class AgentConfig(BaseModel):
    """Agent configuration model"""

    provider: ModelProvider = Field(..., description="AI provider")
    model: ModelName = Field(..., description="Model name")
    name: str = Field(..., description="Agent name")
    capabilities: List[str] = Field(
        default=["conversation"], description="Agent capabilities"
    )
    interaction_modes: List[InteractionMode] = Field(
        ..., description="Supported interaction modes"
    )
    personality: Optional[str] = Field(
        None, description="Agent personality description"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional agent metadata"
    )

    class Config:
        use_enum_values = True


class ChatConfig(BaseModel):
    session_id: Optional[str] = Field(
        default=None, description="Session ID for existing sessions"
    )
    agent_config: AgentConfig = Field(..., description="Agent configuration")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional configuration metadata"
    )


class ChatResponse(BaseModel):
    message: ChatMessage = Field(..., description="Response message")
    session_id: str = Field(..., description="Associated session ID")
    status: str = Field(default="success", description="Response status")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Response metadata"
    )


class MessageResponse(BaseModel):
    message_id: str
    content: str
    sender: str
    receiver: str
    timestamp: datetime
    type: MessageType
    metadata: Optional[Dict[str, Any]] = None
