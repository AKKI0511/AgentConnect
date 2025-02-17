from fastapi import APIRouter, Path, Depends, Response
from typing import Dict
from fastapi_limiter.depends import RateLimiter
from fastapi.security import OAuth2PasswordBearer
from contextlib import asynccontextmanager

from demos.utils.demo_logger import get_logger
from demos.utils.api_validation import verify_token
from demos.api.models.agents import (
    AgentConfig,
    AgentStatus,
    AgentListResponse,
    AgentMessageRequest,
    AgentMessageResponse,
    AgentCapabilitiesResponse,
)
from demos.utils.shared import shared

from .registration import register_agent, unregister_agent
from .messaging import send_agent_message
from .status import list_agents, get_agent_capabilities, get_agent_status


@asynccontextmanager
async def lifespan(router: APIRouter):
    """Lifespan context manager for agent router"""
    # Startup
    logger.info("Agent router started")
    yield
    # Shutdown
    try:
        # Get all agents directly from hub
        agents = await shared.hub.get_all_agents()
        if agents:
            for agent in agents:
                try:
                    await shared.hub.unregister_agent(agent.agent_id)
                except Exception as e:
                    logger.error(
                        f"Error unregistering agent {agent.agent_id}: {str(e)}"
                    )
        logger.info("All agents cleaned up during shutdown")
    except Exception as e:
        logger.error(f"Error during agent cleanup: {str(e)}")


router = APIRouter(lifespan=lifespan)
logger = get_logger("agent_routes")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


@router.post(
    "/register",
    response_model=Dict[str, str],
    summary="Register a new agent",
    description="Register a new AI agent with the system",
    response_description="Registration confirmation with agent details",
)
async def register_agent_endpoint(
    response: Response,
    agent_config: AgentConfig,
    token: str = Depends(oauth2_scheme),
    rate_limiter: bool = Depends(RateLimiter(times=5, seconds=60)),
):
    """Register a new agent endpoint"""
    payload = verify_token(token)
    current_user = payload["sub"]
    return await register_agent(agent_config, current_user)


@router.delete(
    "/{agent_id}",
    response_model=Dict[str, str],
    summary="Unregister an agent",
    description="Unregister and remove an AI agent from the system",
    response_description="Unregistration confirmation",
)
async def unregister_agent_endpoint(
    response: Response,
    agent_id: str = Path(..., description="The ID of the agent to unregister"),
    token: str = Depends(oauth2_scheme),
    rate_limiter: bool = Depends(RateLimiter(times=5, seconds=60)),
):
    """Unregister an agent endpoint"""
    payload = verify_token(token)
    current_user = payload["sub"]
    return await unregister_agent(agent_id, current_user)


@router.get(
    "/list",
    response_model=AgentListResponse,
    summary="List all agents",
    description="List all available agents in the system",
    response_description="List of all agents with their details",
)
async def list_agents_endpoint(
    response: Response,
    token: str = Depends(oauth2_scheme),
    rate_limiter: bool = Depends(RateLimiter(times=10, seconds=60)),
):
    """List all agents endpoint"""
    payload = verify_token(token)
    current_user = payload["sub"]
    return await list_agents(current_user)


@router.post(
    "/{agent_id}/message",
    response_model=AgentMessageResponse,
    summary="Send agent message",
    description="Send a message from one agent to another with optional structured data",
    response_description="Message delivery confirmation",
)
async def send_message_endpoint(
    response: Response,
    message: AgentMessageRequest,
    agent_id: str = Path(..., description="ID of the sending agent"),
    token: str = Depends(oauth2_scheme),
    rate_limiter: bool = Depends(RateLimiter(times=20, seconds=60)),
):
    payload = verify_token(token)
    current_user = payload["sub"]
    return await send_agent_message(agent_id, message, current_user)


@router.get(
    "/{agent_id}/capabilities",
    response_model=AgentCapabilitiesResponse,
    summary="Get agent capabilities",
    description="Get the capabilities, interaction modes, and other details of an agent",
    response_description="Agent capabilities and details",
    responses={
        404: {"description": "Agent not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_capabilities_endpoint(
    response: Response,
    agent_id: str = Path(..., description="The ID of the agent to query"),
    token: str = Depends(oauth2_scheme),
    rate_limiter: bool = Depends(RateLimiter(times=10, seconds=60)),
):
    """Get agent capabilities endpoint"""
    payload = verify_token(token)
    current_user = payload["sub"]
    return await get_agent_capabilities(agent_id, current_user)


@router.get(
    "/status/{agent_id}",
    response_model=AgentStatus,
    summary="Get agent status",
    description="Get detailed status information about an agent, including its current state, capabilities, and activity metrics",
    response_description="Current status and details of the agent",
    responses={
        200: {
            "description": "Successful response with agent status",
            "content": {
                "application/json": {
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
            },
        },
        403: {"description": "Not authorized to view this agent's status"},
        404: {"description": "Agent not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_status_endpoint(
    response: Response,
    agent_id: str = Path(
        ..., description="The unique identifier of the agent to query"
    ),
    token: str = Depends(oauth2_scheme),
    rate_limiter: bool = Depends(RateLimiter(times=10, seconds=60)),
):
    """Get detailed status information about an agent

    This endpoint provides comprehensive status information about an agent, including:
    - Basic information (ID, type, name)
    - Current status (active, inactive, cooldown)
    - Activity metrics (message count, last active time)
    - Capabilities and interaction modes
    - AI-specific details for AI agents (provider, model, cooldown status)

    The user must be the owner of the agent to view its status.
    """
    payload = verify_token(token)
    current_user = payload["sub"]
    return await get_agent_status(agent_id, current_user)
