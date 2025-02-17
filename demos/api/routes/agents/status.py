from fastapi import HTTPException, status
from typing import List
from datetime import datetime

from src.agents.ai_agent import AIAgent
from src.core.agent import BaseAgent
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

        # Get all active agents from hub
        agents: List[BaseAgent] = await shared.hub.get_all_agents()
        if not agents:
            logger.warning("No agents found in hub")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve agents",
            )

        logger.debug(f"Found {len(agents)} total agents")

        # Filter and format agent information
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
                    "name": agent.name,
                    "provider": agent.provider_type,
                    "model": agent.model_name,
                    "capabilities": agent.metadata.capabilities,
                    "interaction_modes": [
                        mode for mode in agent.metadata.interaction_modes
                    ],
                    "status": "active",
                    "owner_id": agent.metadata.organization_id,
                    "last_active": datetime.now().isoformat(),
                }

                # Check if current user owns this agent
                if agent.metadata.organization_id == current_user:
                    user_owned_count += 1
                    logger.debug(f"Found user-owned agent: {agent.agent_id}")
                    agent_info["is_owned"] = True
                else:
                    agent_info["is_owned"] = False

                agent_list.append(agent_info)

            except Exception as e:
                logger.error(f"Error processing agent {agent.agent_id}: {str(e)}")
                continue

        logger.info(
            f"Returning {len(agent_list)} agents ({user_owned_count} owned by user)"
        )
        return AgentListResponse(
            agents=agent_list,
            timestamp=datetime.now(),
            total_count=len(agent_list),
            user_owned_count=user_owned_count,
        )

    except HTTPException:
        raise
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

        # Get agent from hub
        agent: BaseAgent | None = await shared.hub.get_agent(agent_id)
        if not agent:
            logger.warning(f"Agent {agent_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )

        # Verify ownership
        if agent.metadata.organization_id != current_user:
            logger.warning(
                f"Unauthorized capabilities request for agent {agent_id} by user {current_user}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this agent's capabilities",
            )

        logger.debug(f"Retrieving capabilities for agent {agent_id}")
        response_data = {
            "agent_id": agent_id,
            "agent_type": agent.metadata.agent_type,
            "capabilities": agent.metadata.capabilities,
            "interaction_modes": [mode for mode in agent.metadata.interaction_modes],
            "owner_id": agent.metadata.organization_id,
            "personality": None,  # Default for non-AI agents
        }

        # Add AI-specific data if it's an AI agent
        if isinstance(agent, AIAgent):
            response_data["personality"] = agent.personality

            # For AI agents, verify if the requesting user has permission to see full details
            if agent.metadata.organization_id != current_user:
                # Remove sensitive information for non-owners
                response_data["capabilities"] = [
                    "conversation"
                ]  # Show only basic capability
                response_data["personality"] = None

        logger.info(f"Successfully retrieved capabilities for agent {agent_id}")
        return AgentCapabilitiesResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent capabilities for {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent capabilities: {str(e)}",
        )


async def get_agent_status(agent_id: str, current_user: str) -> AgentStatus:
    """Get the current status of an agent

    Args:
        agent_id (str): The ID of the agent to query
        current_user (str): The ID of the requesting user

    Returns:
        AgentStatus: Detailed status information about the agent

    Raises:
        HTTPException: If agent not found, unauthorized, or other errors occur
    """
    try:
        logger.info(f"Getting status for agent {agent_id}")

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

        logger.debug(f"Retrieving status information for agent {agent_id}")

        # Base status data available for all agent types
        status_data = {
            "agent_id": agent_id,
            "agent_type": agent.metadata.agent_type,
            "name": getattr(agent, "name", None),
            "status": "active" if agent.is_running else "inactive",
            "last_active": datetime.now(),  # TODO: Track actual last activity time
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

        try:
            logger.info(f"Successfully retrieved status for agent {agent_id}")
            return AgentStatus(**status_data)
        except Exception as e:
            logger.error(f"Error creating AgentStatus for {agent_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error creating agent status response",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status for agent {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent status: {str(e)}",
        )
