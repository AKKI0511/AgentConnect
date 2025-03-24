from fastapi import HTTPException, status
from typing import List
from datetime import datetime

from agentconnect.agents.ai_agent import AIAgent
from agentconnect.core.agent import BaseAgent
from demos.utils.demo_logger import get_logger
from demos.api.models.agents import (
    AgentStatus,
    AgentListResponse,
    AgentCapabilitiesResponse,
)
from demos.utils.shared import shared

logger = get_logger("agent_status")


async def list_agents(current_user: str) -> AgentListResponse:
    """List all registered agents"""
    try:
        logger.info(f"Listing agents for user {current_user}")
        agents: List[BaseAgent] = await shared.hub.get_all_agents()

        if not agents:
            logger.warning("No agents found in hub")
            return AgentListResponse(
                agents=[], timestamp=datetime.now(), total_count=0, user_owned_count=0
            )

        agent_list = []
        user_owned_count = 0

        for agent in agents:
            # Skip non-AI agents if any
            if not isinstance(agent, AIAgent):
                logger.debug(f"Skipping non-AI agent: {agent.agent_id}")
                continue

            try:
                agent_info = {
                    "agent_id": agent.agent_id,
                    "agent_type": agent.metadata.agent_type,
                    "name": getattr(agent, "name", None),
                    "capabilities": agent.metadata.capabilities,
                    "interaction_modes": [
                        mode for mode in agent.metadata.interaction_modes
                    ],
                    "status": "active" if agent.is_running else "inactive",
                    "owner_id": agent.metadata.organization_id,
                    "last_active": datetime.now().isoformat(),
                    "message_count": len(agent.message_history),
                    "metadata": {},
                }

                # Add AI-specific information
                if isinstance(agent, AIAgent):
                    agent_info.update(
                        {
                            "provider": agent.provider_type.value,
                            "model": agent.model_name.value,
                        }
                    )
                    if agent.is_in_cooldown():
                        agent_info["status"] = "cooldown"

                # Track user ownership
                if agent.metadata.organization_id == current_user:
                    user_owned_count += 1
                    agent_info["is_owned"] = True
                else:
                    agent_info["is_owned"] = False

                agent_list.append(agent_info)

            except Exception as e:
                logger.error(f"Error processing agent {agent.agent_id}: {str(e)}")
                continue

        return AgentListResponse(
            agents=agent_list,
            timestamp=datetime.now(),
            total_count=len(agent_list),
            user_owned_count=user_owned_count,
        )

    except Exception as e:
        logger.error(f"Error listing agents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list agents: {str(e)}",
        )


async def get_agent_capabilities(
    agent_id: str, current_user: str
) -> AgentCapabilitiesResponse:
    """Get an agent's capabilities and interaction modes

    Args:
        agent_id (str): The ID of the agent to query
        current_user (str): The ID of the requesting user

    Returns:
        AgentCapabilitiesResponse: The agent's capabilities and details

    Raises:
        HTTPException: If agent not found or other errors occur
    """
    try:
        logger.info(f"Getting capabilities for agent {agent_id}")
        agent: BaseAgent | None = await shared.hub.get_agent(agent_id)

        if not agent:
            logger.warning(f"Agent {agent_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )

        # Verify ownership
        if agent.metadata.organization_id != current_user:
            logger.warning(f"Unauthorized capabilities request for agent {agent_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this agent's capabilities",
            )

        response_data = {
            "agent_id": agent_id,
            "agent_type": agent.metadata.agent_type,
            "capabilities": agent.metadata.capabilities,
            "interaction_modes": [mode for mode in agent.metadata.interaction_modes],
            "owner_id": agent.metadata.organization_id,
            "personality": getattr(agent, "personality", None),
            "timestamp": datetime.now(),
        }

        return AgentCapabilitiesResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent capabilities: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent capabilities: {str(e)}",
        )


async def get_agent_status(agent_id: str, current_user: str) -> AgentStatus:
    """Get the current status of an agent"""
    try:
        # Get agent from hub
        agent: BaseAgent | None = await shared.hub.get_agent(agent_id)
        if not agent:
            logger.warning(f"Agent {agent_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )

        # Verify ownership for all agent types
        if agent.metadata.organization_id != current_user:
            logger.warning(
                f"Unauthorized status request for agent {agent_id} by user {current_user}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this agent's status",
            )

        # Base status data available for all agent types
        status_data = {
            "agent_id": agent_id,
            "agent_type": agent.metadata.agent_type,
            "name": getattr(agent, "name", None),
            "status": "active" if agent.is_running else "inactive",
            "last_active": datetime.now(),  # Using current time as last activity
            "capabilities": agent.metadata.capabilities,
            "interaction_modes": [mode for mode in agent.metadata.interaction_modes],
            "owner_id": agent.metadata.organization_id,
            "is_running": agent.is_running,
            "message_count": len(agent.message_history),
            "metadata": {},
        }

        # Add AI-specific metadata if it's an AI agent
        if isinstance(agent, AIAgent):
            status_data["metadata"].update(
                {
                    "provider": agent.provider_type,
                    "model": agent.model_name,
                    "personality": agent.personality,
                    "cooldown_until": (
                        agent.cooldown_until if agent.is_in_cooldown() else None
                    ),
                    "active_conversations": len(agent.active_conversations),
                    "total_messages_processed": len(shared.hub._message_history),
                }
            )

            # Update status if agent is in cooldown
            if agent.is_in_cooldown():
                status_data["status"] = "cooldown"

        return AgentStatus(**status_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status for agent {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent status: {str(e)}",
        )


async def update_agent_status(agent_id: str, status_update: dict) -> None:
    """Update agent status information"""
    try:
        # Update status
        if "status" in status_update:
            await shared.redis.set(f"agent:{agent_id}:status", status_update["status"])

        # Update last active timestamp
        await shared.redis.set(
            f"agent:{agent_id}:last_active", datetime.now().isoformat()
        )

        # Increment message count if needed
        if status_update.get("increment_messages", False):
            await shared.redis.incr(f"agent:{agent_id}:message_count")

    except Exception as e:
        logger.error(f"Error updating agent status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent status: {str(e)}",
        )
