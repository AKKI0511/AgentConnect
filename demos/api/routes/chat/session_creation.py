from typing import List
from fastapi import HTTPException, BackgroundTasks, status
from datetime import datetime
import asyncio
from uuid import uuid4

from demos.api.models.chat import (
    CreateSessionRequest,
    SessionResponse,
    AgentMetadata,
    MessageType,
)
from agentconnect.core.agent import BaseAgent
from agentconnect.core.types import (
    InteractionMode,
    AgentIdentity,
    ModelName,
    ModelProvider,
)
from agentconnect.agents.ai_agent import AIAgent
from agentconnect.agents.human_agent import HumanAgent
from demos.utils.demo_logger import get_logger
from demos.utils.config_manager import get_config
from demos.utils.shared import shared
from .handlers import handle_agent_response

logger = get_logger("chat_session_creation")
config = get_config()


class SessionManager:
    """Manages chat session lifecycle and operations"""

    @staticmethod
    async def validate_user_sessions(current_user: str) -> None:
        """Validate user's active session count"""
        logger.debug(f"Validating session count for user: {current_user}")

        # Clean up expired sessions first
        await SessionManager.cleanup_expired_sessions(current_user)

        # Check remaining active sessions
        user_sessions = await shared.redis.smembers(f"user_sessions:{current_user}")
        if len(user_sessions) >= config.session_settings["max_sessions_per_user"]:
            logger.warning(f"User {current_user} has reached maximum session limit")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Maximum active sessions reached",
            )
        logger.debug(f"User {current_user} has {len(user_sessions)} active sessions")

    @staticmethod
    async def cleanup_expired_sessions(current_user: str) -> None:
        """Clean up expired sessions for a user"""
        user_sessions = await shared.redis.smembers(f"user_sessions:{current_user}")
        current_time = datetime.now().timestamp()

        for session_id in user_sessions:
            session_id = (
                session_id.decode("utf-8")
                if isinstance(session_id, bytes)
                else session_id
            )
            # Check if session has expired
            last_active = await shared.redis.get(f"session:{session_id}:last_active")
            if last_active:
                last_active = float(last_active)
                if (
                    current_time - last_active
                    > config.session_settings["max_inactive_time"]
                ):
                    logger.info(
                        f"Removing expired session {session_id} for user {current_user}"
                    )
                    # Remove session from user's set
                    await shared.redis.srem(f"user_sessions:{current_user}", session_id)
                    # Clean up session data
                    await shared.redis.delete(f"session:{session_id}")
                    await shared.redis.delete(f"session:{session_id}:last_active")
                    await shared.redis.delete(f"session:{session_id}:messages")

    @staticmethod
    def generate_session_id() -> str:
        """Generate a unique session ID"""
        session_id = (
            f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}"
        )
        logger.debug(f"Generated new session ID: {session_id}")
        return session_id

    @staticmethod
    def create_session_data(
        session_id: str, request: CreateSessionRequest, current_user: str
    ) -> dict:
        """Create initial session data"""
        logger.debug(f"Creating session data for session {session_id}")
        try:
            # Create base session data
            session_data = {
                "session_id": session_id,
                "type": MessageType.SYSTEM,
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "created_by": current_user,
                "session_type": request.session_type,
                "status": "initializing",
            }

            # Add agent-specific data based on session type
            if request.session_type == "human_agent":
                ai_config = next(iter(request.agents.values()))
                session_data.update(
                    {
                        "ai_provider": ai_config.provider,
                        "ai_model": ai_config.model
                        or ModelName.get_default_for_provider(ai_config.provider),
                        "ai_capabilities": ",".join(ai_config.capabilities),
                        "ai_personality": ai_config.personality
                        or "helpful and professional",
                    }
                )
            else:  # agent_agent
                for idx, (agent_key, agent_config) in enumerate(
                    request.agents.items(), 1
                ):
                    prefix = f"agent{idx}"
                    session_data.update(
                        {
                            f"{prefix}_provider": agent_config.provider,
                            f"{prefix}_model": agent_config.model
                            or ModelName.get_default_for_provider(
                                agent_config.provider
                            ),
                            f"{prefix}_capabilities": ",".join(
                                agent_config.capabilities
                            ),
                            f"{prefix}_personality": agent_config.personality
                            or f"AI Agent {idx} focused on collaborative problem-solving",
                        }
                    )

            # Add interaction modes if specified
            if request.interaction_modes:
                session_data["interaction_modes"] = ",".join(request.interaction_modes)

            # Add any additional metadata
            if request.metadata:
                session_data["metadata"] = str(request.metadata)

            logger.debug(f"Created session data: {session_data}")
            return session_data
        except Exception as e:
            logger.error(f"Error creating session data: {str(e)}")
            raise

    @staticmethod
    async def store_session_data(
        session_id: str, session_data: dict, current_user: str
    ) -> None:
        """Store session data in Redis with transaction"""
        logger.debug(f"Storing session data for session {session_id}")
        try:
            async with shared.redis.pipeline(transaction=True) as pipe:
                await pipe.hset(f"session:{session_id}", mapping=session_data)
                await pipe.sadd(f"user_sessions:{current_user}", session_id)
                await pipe.expire(
                    f"session:{session_id}", config.session_settings["timeout"]
                )
                await pipe.expire(
                    f"user_sessions:{current_user}", config.session_settings["timeout"]
                )
                await pipe.execute()
            logger.debug(f"Successfully stored session data for {session_id}")
        except Exception as e:
            logger.error(f"Failed to store session data: {str(e)}")
            raise


class AgentManager:
    """Manages agent creation and registration"""

    @staticmethod
    async def create_human_agent(session_id: str, current_user: str) -> HumanAgent:
        """Create a human agent"""
        logger.debug(f"Creating human agent for session {session_id}")
        try:
            identity = AgentIdentity.create_key_based()
            agent = HumanAgent(
                agent_id=f"human_{session_id}",
                name=current_user,
                identity=identity,
                organization_id="org1",
            )
            logger.debug(f"Created human agent with ID: {agent.agent_id}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create human agent: {str(e)}")
            raise

    @staticmethod
    async def create_ai_agent(
        session_id: str,
        agent_config: dict,
        agent_id: str,
        owner_id: str = "org1",
    ) -> AIAgent:
        """Create an AI agent with specific configuration"""
        logger.debug(f"Creating AI agent for session {session_id} with ID: {agent_id}")
        try:
            identity = AgentIdentity.create_key_based()
            api_key = config.get_provider_api_key(agent_config["provider"])
            if not api_key:
                logger.error(
                    f"API key not found for provider: {agent_config['provider']}"
                )
                raise ValueError(
                    f"API key not found for provider: {agent_config['provider']}"
                )

            # Get default model if none provided
            model_name = agent_config.get("model")
            if not model_name:
                model_name = ModelName.get_default_for_provider(
                    agent_config["provider"]
                )

            agent = AIAgent(
                agent_id=agent_id,
                name=f"AI Agent {agent_id}",
                provider_type=ModelProvider(agent_config["provider"]),
                model_name=ModelName(model_name),
                api_key=api_key,
                identity=identity,
                capabilities=agent_config.get("capabilities", ["conversation"]),
                personality=agent_config.get("personality"),
                organization_id=owner_id,
                interaction_modes=agent_config.get(
                    "interaction_modes",
                    [InteractionMode.AGENT_TO_AGENT, InteractionMode.HUMAN_TO_AGENT],
                ),
                max_tokens_per_minute=3000,
            )
            logger.debug(f"Created AI agent with ID: {agent.agent_id}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create AI agent: {str(e)}")
            raise

    @staticmethod
    async def register_agents(*agents: BaseAgent) -> None:
        """Register multiple agents"""
        for agent in agents:
            logger.debug(f"Registering agent: {agent.agent_id}")
            try:
                if not await shared.hub.register_agent(agent):
                    logger.error(f"Failed to register agent: {agent.agent_id}")
                    raise ValueError(f"Failed to register agent: {agent.agent_id}")
                logger.debug(f"Successfully registered agent: {agent.agent_id}")
            except Exception as e:
                logger.error(f"Error during agent registration: {str(e)}")
                raise

    @staticmethod
    async def setup_message_handlers(
        session_id: str, *agents: AIAgent, background_tasks: BackgroundTasks
    ) -> None:
        """Set up message handlers and start agent processing"""
        for agent in agents:
            logger.debug(f"Setting up message handler for agent: {agent.agent_id}")
            try:
                # Create a closure to capture session_id
                async def message_handler(msg):
                    # Handle messages from any agent in the session
                    await handle_agent_response(session_id, msg)

                # Add message handler to hub
                shared.hub.add_message_handler(agent.agent_id, message_handler)

                # Start agent processing using asyncio task
                logger.info(f"Starting processing loop for agent: {agent.agent_id}")
                asyncio.create_task(agent.run(), name=f"agent_task_{agent.agent_id}")
                logger.debug(
                    f"Successfully set up message handler for agent: {agent.agent_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to set up message handler for agent {agent.agent_id}: {str(e)}"
                )
                raise

    @staticmethod
    async def update_session_with_agents(session_id: str, **agent_ids) -> None:
        """Update session with agent IDs"""
        logger.debug(f"Updating session {session_id} with agent IDs: {agent_ids}")
        try:
            await shared.redis.hmset(
                f"session:{session_id}", {**agent_ids, "status": "active"}
            )
            logger.debug(f"Successfully updated session {session_id} with agent IDs")
        except Exception as e:
            logger.error(f"Failed to update session with agent IDs: {str(e)}")
            raise


async def setup_human_agent_session(
    session_id: str,
    request: CreateSessionRequest,
    current_user: str,
    background_tasks: BackgroundTasks,
) -> None:
    """Set up a human-agent chat session"""
    logger.info(f"Setting up human-agent session {session_id}")
    try:
        human_agent = await AgentManager.create_human_agent(session_id, current_user)

        # Get the AI agent configuration (there should be exactly one)
        ai_config = next(iter(request.agents.values()))
        ai_agent = await AgentManager.create_ai_agent(
            session_id=session_id,
            agent_config=ai_config.model_dump(),
            agent_id=f"ai1_{session_id}",
            owner_id=current_user,
        )

        await AgentManager.register_agents(human_agent, ai_agent)
        await AgentManager.setup_message_handlers(
            session_id, ai_agent, background_tasks=background_tasks
        )
        await AgentManager.update_session_with_agents(
            session_id,
            human_agent_id=human_agent.agent_id,
            ai_agent_id=ai_agent.agent_id,
        )
        logger.debug(f"Successfully set up human-agent session {session_id}")
    except Exception as e:
        logger.error(f"Failed to set up human-agent session: {str(e)}")
        raise


async def setup_agent_agent_session(
    session_id: str,
    request: CreateSessionRequest,
    current_user: str,
    background_tasks: BackgroundTasks,
) -> None:
    """Set up an agent-agent chat session"""
    logger.info(f"Setting up agent-agent session {session_id}")
    try:
        # Create both AI agents with their respective configurations
        agents: List[AIAgent] = []
        for idx, (agent_key, agent_config) in enumerate(request.agents.items(), 1):
            agent = await AgentManager.create_ai_agent(
                session_id=session_id,
                agent_config=agent_config.model_dump(),
                agent_id=f"ai{idx}_{session_id}",
                owner_id=current_user,
            )
            agents.append(agent)

        await AgentManager.register_agents(*agents)
        await AgentManager.setup_message_handlers(
            session_id, *agents, background_tasks=background_tasks
        )
        await AgentManager.update_session_with_agents(
            session_id,
            agent1_id=agents[0].agent_id,
            agent2_id=agents[1].agent_id,
        )
        logger.debug(f"Successfully set up agent-agent session {session_id}")
    except Exception as e:
        logger.error(f"Failed to set up agent-agent session: {str(e)}")
        raise


async def create_new_session(
    request: CreateSessionRequest, background_tasks: BackgroundTasks, current_user: str
) -> SessionResponse:
    """Create a new chat session with specified configuration"""
    logger.debug(f"Creating new session for user {current_user}")
    try:
        # Validate session limit
        await SessionManager.validate_user_sessions(current_user)

        # Generate session ID and create initial session data
        session_id = SessionManager.generate_session_id()
        session_data = SessionManager.create_session_data(
            session_id, request, current_user
        )
        await SessionManager.store_session_data(session_id, session_data, current_user)

        # Set up agents based on session type
        if request.session_type == "human_agent":
            await setup_human_agent_session(
                session_id, request, current_user, background_tasks
            )
        elif request.session_type == "agent_agent":
            await setup_agent_agent_session(
                session_id, request, current_user, background_tasks
            )

        # Get session info for response
        session_info = await shared.redis.hgetall(f"session:{session_id}")

        # Create agent metadata for response
        agents_metadata = {}
        if request.session_type == "human_agent":
            ai_agent_id = session_info.get("ai_agent_id")
            agents_metadata["ai_agent"] = AgentMetadata(
                agent_id=ai_agent_id,
                provider=session_info["ai_provider"],
                model=session_info["ai_model"],
                capabilities=session_info["ai_capabilities"].split(","),
                personality=session_info["ai_personality"],
                status="active",
            )
        else:
            for idx, (agent_key, _) in enumerate(request.agents.items(), 1):
                prefix = f"agent{idx}"
                agent_id = session_info.get(f"{prefix}_id")
                agents_metadata[agent_key] = AgentMetadata(
                    agent_id=agent_id,
                    provider=session_info[f"{prefix}_provider"],
                    model=session_info[f"{prefix}_model"],
                    capabilities=session_info[f"{prefix}_capabilities"].split(","),
                    personality=session_info[f"{prefix}_personality"],
                    status="active",
                )

        # Parse metadata if exists
        metadata = (
            eval(session_info.get("metadata", "{}"))
            if session_info.get("metadata")
            else None
        )

        # Create response
        response = SessionResponse(
            session_id=session_id,
            type=MessageType.SYSTEM,
            created_at=datetime.fromisoformat(session_info["created_at"]),
            status="active",
            session_type=request.session_type,
            agents=agents_metadata,
            metadata=metadata,
        )

        # Schedule cleanup
        background_tasks.add_task(
            schedule_session_cleanup, session_id, config.session_settings["timeout"]
        )

        logger.debug(f"Successfully created session {session_id}")
        return response

    except Exception as e:
        logger.error(f"Failed to create session: {str(e)}")
        await cleanup_failed_session(session_id, current_user)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


async def cleanup_failed_session(session_id: str, user_id: str):
    """Clean up resources if session creation fails"""
    try:
        await shared.redis.delete(f"session:{session_id}")
        await shared.redis.srem(f"user_sessions:{user_id}", session_id)
    except Exception as e:
        logger.error(f"Failed to cleanup session: {str(e)}")


async def schedule_session_cleanup(session_id: str, timeout: int):
    """Schedule session cleanup after timeout"""
    try:
        await asyncio.sleep(timeout)
        session_data = await shared.redis.hgetall(f"session:{session_id}")
        if session_data:
            created_at = datetime.fromisoformat(session_data["created_at"])
            if (datetime.now() - created_at).total_seconds() >= timeout:
                from .session import (
                    cleanup_session,
                )  # Import here to avoid circular dependency

                await cleanup_session(session_id, session_data)
    except Exception as e:
        logger.error(f"Error in scheduled session cleanup: {str(e)}")
