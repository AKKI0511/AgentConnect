"""
Basic example demonstrating how to use the CommunicationHub for agent communication.

This example shows:
1. Creating and registering agents
2. Sending messages between agents
3. Using the request-response pattern
4. Handling collaboration requests
5. Implementing agent-to-agent collaboration
"""

import asyncio
import logging
import os
from dotenv import load_dotenv

from agentconnect.core.registry import AgentRegistry
from agentconnect.core.types import (
    AgentIdentity,
    InteractionMode,
    MessageType,
    ModelName,
    ModelProvider,
)
from agentconnect.core.message import Message
from agentconnect.communication.hub import CommunicationHub
from agentconnect.agents.ai_agent import AIAgent
from agentconnect.utils.logging_config import setup_logging, LogLevel

# Load environment variables
load_dotenv()

# Configure logging
setup_logging(level=LogLevel.INFO)
logger = logging.getLogger("CommunicationExample")


async def message_handler(message: Message) -> None:
    """Example message handler that logs received messages"""
    logger.info(f"Received message: {message.content[:50]}...")


async def main():
    # Create registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    # Create agents
    agent1 = AIAgent(
        agent_id="agent1",
        name="Agent One",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH_LITE,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        personality="knowledgeable research assistant",
        interaction_modes=[
            InteractionMode.HUMAN_TO_AGENT,
            InteractionMode.AGENT_TO_AGENT,
        ],
    )

    agent2 = AIAgent(
        agent_id="agent2",
        name="Agent Two",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        personality="precise and analytical data specialist",
        interaction_modes=[
            InteractionMode.HUMAN_TO_AGENT,
            InteractionMode.AGENT_TO_AGENT,
        ],
    )

    # Register agents with the hub
    await hub.register_agent(agent1)
    await hub.register_agent(agent2)

    # Add message handlers
    hub.add_message_handler("agent1", message_handler)
    hub.add_message_handler("agent2", message_handler)

    # Example 1: Simple message sending
    logger.info("Example 1: Simple message sending")
    message = Message.create(
        sender_id="agent1",
        receiver_id="agent2",
        content="Hello from Agent One!",
        sender_identity=agent1.identity,
        message_type=MessageType.TEXT,
    )

    success = await hub.route_message(message)
    logger.info(f"Message routing success: {success}")

    # Wait a moment for the message to be processed
    await asyncio.sleep(1)

    # Example 2: Request-response pattern
    logger.info("\nExample 2: Request-response pattern")
    response = await hub.send_message_and_wait_response(
        sender_id="agent1",
        receiver_id="agent2",
        content="What's your name?",
        message_type=MessageType.TEXT,
        timeout=10,
    )

    if response:
        logger.info(f"Received response: {response.content[:50]}...")
    else:
        logger.warning("No response received within timeout")

    # Example 3: Collaboration request
    logger.info("\nExample 3: Collaboration request")
    result = await hub.send_collaboration_request(
        sender_id="agent1",
        receiver_id="agent2",
        task_description="Please analyze this data: [1, 2, 3, 4, 5]",
        timeout=20,
    )

    logger.info(f"Collaboration result: {result[:50]}...")

    # Example 4: Specialized agents collaboration
    logger.info("\nExample 4: Specialized agents collaboration")
    
    # Create specialized agents
    research_assistant = AIAgent(
        agent_id="research_assistant",
        name="Research Assistant",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH_LITE,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        personality="knowledgeable research assistant specialized in finding information",
        interaction_modes=[
            InteractionMode.HUMAN_TO_AGENT,
            InteractionMode.AGENT_TO_AGENT,
        ],
    )

    data_analyst = AIAgent(
        agent_id="data_analyst",
        name="Data Analyst",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        personality="precise and analytical data specialist who excels at interpreting numbers",
        interaction_modes=[
            InteractionMode.HUMAN_TO_AGENT,
            InteractionMode.AGENT_TO_AGENT,
        ],
    )

    # Register specialized agents
    await hub.register_agent(research_assistant)
    await hub.register_agent(data_analyst)
    
    # Send a collaboration request between specialized agents
    logger.info("Sending collaboration request from research_assistant to data_analyst")
    specialized_result = await hub.send_collaboration_request(
        sender_id="research_assistant",
        receiver_id="data_analyst",
        task_description="Please analyze this dataset and provide key insights: [10, 15, 20, 25, 30]",
        timeout=30,
    )

    logger.info(f"Specialized collaboration result: {specialized_result[:100]}...")

    # Clean up all agents
    await hub.unregister_agent("agent1")
    await hub.unregister_agent("agent2")
    await hub.unregister_agent("research_assistant")
    await hub.unregister_agent("data_analyst")

    logger.info("Example completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
