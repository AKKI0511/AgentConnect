from fastapi import HTTPException, status
from datetime import datetime

from agentconnect.agents.ai_agent import AIAgent
from agentconnect.core.agent import BaseAgent
from agentconnect.core.message import Message
from agentconnect.core.types import MessageType, SecurityError
from demos.utils.demo_logger import get_logger
from demos.utils.shared import shared
from demos.api.models.agents import AgentMessageRequest, AgentMessageResponse

logger = get_logger("agent_messaging")


async def send_agent_message(
    agent_id: str, message: AgentMessageRequest, user_id: str
) -> AgentMessageResponse:
    """Send a message from one agent to another with optional structured data"""
    try:
        logger.info(
            f"Processing message request from agent {agent_id} to {message.receiver_id}"
        )
        logger.debug(f"Message details: {message.model_dump()}")

        # Get sender agent and verify ownership
        sender: BaseAgent | None = await shared.hub.get_agent(agent_id)
        if not sender:
            logger.warning(f"Sender agent {agent_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sender agent {agent_id} not found",
            )

        # Verify agent ownership
        if (
            not isinstance(sender, AIAgent)
            or sender.metadata.organization_id != user_id
        ):
            logger.warning(
                f"Unauthorized message attempt from agent {agent_id} by user {user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to use this agent",
            )

        # Get receiver agent
        receiver: BaseAgent | None = await shared.hub.get_agent(message.receiver_id)
        if not receiver:
            logger.warning(f"Receiver agent {message.receiver_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Receiver agent {message.receiver_id} not found",
            )

        logger.debug(
            f"Found both sender ({agent_id}) and receiver ({message.receiver_id}) agents"
        )

        # Combine structured data with metadata if provided
        combined_metadata = message.metadata or {}
        if message.structured_data:
            combined_metadata["structured_data"] = message.structured_data
            logger.debug(f"Combined metadata: {combined_metadata}")

        try:
            # Send message through agent
            logger.debug(
                f"Attempting to send message from {agent_id} to {message.receiver_id}"
            )
            sent_message: Message = await sender.send_message(
                receiver_id=message.receiver_id,
                content=message.content,
                message_type=MessageType.TEXT,
                metadata=combined_metadata,
            )

            logger.info(
                f"Successfully sent message from {agent_id} to {message.receiver_id}"
            )
            return AgentMessageResponse(
                status="sent",
                message_id=sent_message.id,
                sender=agent_id,
                receiver=message.receiver_id,
                timestamp=datetime.now(),
            )

        except SecurityError as e:
            logger.error(
                f"Security verification failed for message from {agent_id} to {message.receiver_id}: {str(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Security verification failed: {str(e)}",
            )
        except Exception as e:
            logger.error(
                f"Error sending message from {agent_id} to {message.receiver_id}: {str(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send message: {str(e)}",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in send_agent_message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
