from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from src.core.types import ModelProvider, ModelName, InteractionMode


class MessageType(str, Enum):
    TEXT = "text"
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
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Message timestamp"
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
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


class CreateSessionRequest(BaseModel):
    """Request model for creating a new chat session"""

    provider: ModelProvider = Field(..., description="AI provider to use")
    model: Optional[ModelName] = Field(
        None, description="Specific model to use (optional)"
    )
    session_type: str = Field(
        ..., pattern="^(human_agent|agent_agent)$", description="Type of session"
    )
    capabilities: Optional[List[str]] = Field(
        default=["conversation"], description="Agent capabilities"
    )
    personality: Optional[str] = Field(
        None, description="Agent personality description"
    )
    metadata: Optional[Dict] = Field(
        default=None, description="Additional session metadata"
    )

    model_config = {"use_enum_values": True}


class SessionResponse(BaseMessageModel):
    """Response model for session operations"""

    session_id: str = Field(..., description="Unique session identifier")
    type: MessageType = Field(..., description="Session type")
    created_at: datetime = Field(..., description="Session creation timestamp")
    status: str = Field(default="active", description="Session status")
    provider: ModelProvider = Field(..., description="AI provider type")
    model: Optional[ModelName] = Field(None, description="Model name")
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
