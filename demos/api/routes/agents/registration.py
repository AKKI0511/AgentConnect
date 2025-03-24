from fastapi import HTTPException, status
from typing import Dict
from datetime import datetime
import asyncio

from agentconnect.agents.ai_agent import AIAgent
from agentconnect.core.agent import BaseAgent
from agentconnect.core.types import AgentIdentity, ModelProvider, ModelName
from demos.utils.demo_logger import get_logger
from demos.utils.config_manager import get_config
from demos.api.models.agents import AgentConfig
from demos.utils.shared import shared

logger = get_logger("agent_registration")
config = get_config()


async def register_agent(
    agent_config: AgentConfig, current_user: str
) -> Dict[str, str]:
    """Register a new AI agent"""
    try:
        logger.info(f"Registering new agent for user {current_user}")
        logger.debug(f"Agent config: {agent_config.model_dump()}")

        # Generate unique agent ID
        agent_id = f"agent_{datetime.now().strftime('%Y%m%d%H%M%S')}_{current_user[:8]}"
        logger.debug(f"Generated agent ID: {agent_id}")

        # Use default provider/model if not specified
        if not agent_config.provider:
            logger.debug("Using default provider from config")
            agent_config.provider = config.default_agent_settings["provider"]
        if not agent_config.model:
            logger.debug("Using default model from config")
            agent_config.model = config.default_agent_settings["model"]

        logger.debug(
            f"Using provider: {agent_config.provider}, model: {agent_config.model}"
        )

        # Create agent identity
        identity = AgentIdentity.create_key_based()
        logger.debug(f"Created agent identity with DID: {identity.did}")

        # Create agent with proper metadata
        metadata = {
            "owner_id": current_user,
            "created_at": datetime.now().isoformat(),
            "capabilities": ",".join(agent_config.capabilities),
            "interaction_modes": ",".join(
                [mode for mode in agent_config.interaction_modes]
            ),
        }
        if agent_config.metadata:
            metadata.update(agent_config.metadata)
        logger.debug(f"Agent metadata: {metadata}")

        # Get API key from config
        api_key = config.get_provider_api_key(agent_config.provider)
        if not api_key:
            logger.error(f"API key not found for provider: {agent_config.provider}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"API key not found for provider: {agent_config.provider}",
            )

        agent = AIAgent(
            agent_id=agent_id,
            name=agent_config.name,
            provider_type=ModelProvider(agent_config.provider),
            model_name=ModelName(agent_config.model),
            api_key=api_key,
            identity=identity,
            capabilities=agent_config.capabilities,
            personality=agent_config.personality or "professional and efficient",
            organization_id=current_user,  # Use current_user as organization_id
            interaction_modes=agent_config.interaction_modes,
        )

        # Register with hub
        if not await shared.hub.register_agent(agent):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to register agent",
            )

        # Start agent's run task
        agent.is_running = True
        asyncio.create_task(agent.run(), name=f"agent_{agent_id}")
        logger.debug(f"Started run task for agent {agent_id}")

        return {
            "agent_id": agent_id,
            "status": "registered",
            "name": agent_config.name,
            "provider": agent_config.provider,
            "model": agent_config.model,
            "capabilities": metadata["capabilities"],
            "interaction_modes": metadata["interaction_modes"],
            "owner_id": current_user,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error registering agent: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


async def unregister_agent(agent_id: str, current_user: str) -> Dict[str, str]:
    """Unregister an AI agent"""
    try:
        logger.info(f"Unregistering agent {agent_id} requested by user {current_user}")

        # Get agent and verify ownership
        agent: BaseAgent | None = await shared.hub.get_agent(agent_id)
        if not agent:
            logger.warning(f"Agent {agent_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
            )

        if agent.metadata.organization_id != current_user:
            logger.warning(
                f"Unauthorized attempt to unregister agent {agent_id} by user {current_user}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to unregister this agent",
            )

        if not await shared.hub.unregister_agent(agent_id):
            logger.error(f"Failed to unregister agent {agent_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to unregister agent",
            )

        logger.info(f"Successfully unregistered agent {agent_id}")
        return {
            "agent_id": agent_id,
            "status": "unregistered",
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unregistering agent: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
