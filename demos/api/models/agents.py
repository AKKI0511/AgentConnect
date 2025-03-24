from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from agentconnect.core.types import (
    ModelProvider,
    ModelName,
    InteractionMode,
    MessageType,
)


class AgentConfig(BaseModel):
    """Configuration for creating or updating an agent"""

    name: str = Field(..., description="Display name of the agent")
    provider: ModelProvider = Field(..., description="AI provider for the agent")
    model: Optional[ModelName] = Field(None, description="Specific model to use")
    capabilities: List[str] = Field(
        default=["conversation"], description="List of agent capabilities"
    )
    interaction_modes: List[InteractionMode] = Field(
        default=[InteractionMode.AGENT_TO_AGENT],
        description="Supported interaction modes",
    )
    personality: Optional[str] = Field(
        None, description="Agent's personality description"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )

    class Config:
        use_enum_values = True


class AgentStatus(BaseModel):
    """Status information for an agent"""

    agent_id: str = Field(..., description="Agent's unique identifier")
    agent_type: str = Field(..., description="Type of agent (AI, Human, etc)")
    name: Optional[str] = Field(None, description="Display name of the agent")
    status: str = Field(
        ..., description="Current status of the agent (active, inactive, error)"
    )
    last_active: datetime = Field(..., description="Last activity timestamp")
    capabilities: List[str] = Field(..., description="Agent's current capabilities")
    interaction_modes: List[str] = Field(..., description="Current interaction modes")
    owner_id: str = Field(..., description="ID of the user who owns this agent")
    is_running: bool = Field(
        ..., description="Whether the agent's message processing loop is running"
    )
    message_count: int = Field(
        0, description="Number of messages processed by this agent"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional status information"
    )

    class Config:
        """Pydantic config"""

        json_schema_extra = {
            "example": {
                "agent_id": "agent_123",
                "agent_type": "AI",
                "name": "Assistant",
                "status": "active",
                "last_active": "2024-02-10T12:00:00",
                "capabilities": ["conversation"],
                "interaction_modes": ["human_to_agent"],
                "owner_id": "user_123",
                "is_running": True,
                "message_count": 42,
                "metadata": {
                    "provider": "groq",
                    "model": "llama-3.1-70b-versatile",
                    "cooldown_until": None,
                },
            }
        }


class AgentMessage(BaseModel):
    """Model for agent-to-agent messages"""

    receiver_id: str = Field(..., description="ID of the receiving agent")
    content: str = Field(..., description="Message content")
    message_type: str = Field(default="text", description="Type of message")
    structured_data: Optional[Dict[str, Any]] = Field(
        default=None, description="Structured data payload"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional message metadata"
    )


class AgentMessageRequest(BaseModel):
    """Request model for sending messages between agents"""

    receiver_id: str = Field(..., description="ID of the receiving agent")
    content: str = Field(..., description="Message content")
    message_type: MessageType = Field(
        default=MessageType.TEXT, description="Type of message"
    )
    structured_data: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional structured data payload"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional message metadata"
    )


class AgentMessageResponse(BaseModel):
    """Response model for agent message sending"""

    status: str = Field(..., description="Message delivery status")
    message_id: str = Field(..., description="Unique ID of the delivered message")
    sender: str = Field(..., description="ID of the sending agent")
    receiver: str = Field(..., description="ID of the receiving agent")
    timestamp: datetime = Field(..., description="Message delivery timestamp")


class AgentListResponse(BaseModel):
    """Response model for listing agents"""

    agents: List[Dict[str, Any]] = Field(..., description="List of agent information")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Response timestamp"
    )
    total_count: int = Field(..., description="Total number of agents")
    user_owned_count: int = Field(
        ..., description="Number of agents owned by the requesting user"
    )


class AgentCapabilitiesResponse(BaseModel):
    """Response model for agent capabilities"""

    agent_id: str = Field(..., description="Agent's unique identifier")
    agent_type: str = Field(..., description="Type of agent (AI, Human, etc)")
    capabilities: List[str] = Field(..., description="List of agent capabilities")
    interaction_modes: List[str] = Field(
        ..., description="List of supported interaction modes"
    )
    personality: Optional[str] = Field(
        None, description="Agent's personality (AI agents only)"
    )
    owner_id: Optional[str] = Field(None, description="ID of the agent owner")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Response timestamp"
    )
