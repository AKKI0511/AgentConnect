"""
Basic example demonstrating how to create and use agents in AgentConnect.

This example shows:
1. Creating AI and Human agents
2. Setting up direct communication between agents
3. Processing messages and handling responses
4. Using the Communication Hub for agent interaction
"""

import asyncio
import logging
import os
from dotenv import load_dotenv

from agentconnect.agents.ai_agent import AIAgent
from agentconnect.agents.human_agent import HumanAgent
from agentconnect.core.types import (
    ModelProvider,
    ModelName,
    AgentIdentity,
    InteractionMode,
    MessageType,
)
from agentconnect.core.message import Message
from agentconnect.core.registry import AgentRegistry
from agentconnect.communication.hub import CommunicationHub

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AgentExample")


async def direct_communication_example():
    """Example of direct communication between agents without using the hub"""
    logger.info("=== Direct Communication Example ===")

    # Create an AI agent
    ai_agent = AIAgent(
        agent_id="assistant",
        name="AI Assistant",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH_LITE,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        personality="helpful and friendly assistant",
        organization_id="example_org",
        interaction_modes=[
            InteractionMode.HUMAN_TO_AGENT,
            InteractionMode.AGENT_TO_AGENT,
        ],
    )

    # Create a human agent
    human_agent = HumanAgent(
        agent_id="user",
        name="Example User",
        identity=AgentIdentity.create_key_based(),
        organization_id="example_org",
    )

    # Create a message from human to AI
    message = Message.create(
        sender_id=human_agent.agent_id,
        receiver_id=ai_agent.agent_id,
        content="Hello, can you tell me what the capital of France is?",
        sender_identity=human_agent.identity,
        message_type=MessageType.TEXT,
    )

    # Process the message
    logger.info(f"Sending message: {message.content}")
    response = await ai_agent.process_message(message)

    if response:
        logger.info(f"Received response: {response.content}")
    else:
        logger.warning("No response received")


async def hub_communication_example():
    """Example of communication between agents using the Communication Hub"""
    logger.info("\n=== Hub Communication Example ===")

    # Create registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    # Create an AI agent
    ai_agent = AIAgent(
        agent_id="research_assistant",
        name="Research Assistant",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH_LITE,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        personality="knowledgeable research assistant",
        organization_id="example_org",
        interaction_modes=[
            InteractionMode.HUMAN_TO_AGENT,
            InteractionMode.AGENT_TO_AGENT,
        ],
    )

    # Create another AI agent
    ai_agent2 = AIAgent(
        agent_id="data_analyst",
        name="Data Analyst",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        personality="precise and analytical data specialist",
        organization_id="example_org",
        interaction_modes=[
            InteractionMode.HUMAN_TO_AGENT,
            InteractionMode.AGENT_TO_AGENT,
        ],
    )

    # Register agents with the hub
    await hub.register_agent(ai_agent)
    await hub.register_agent(ai_agent2)

    # Send a collaboration request
    logger.info("Sending collaboration request from research_assistant to data_analyst")
    result = await hub.send_collaboration_request(
        sender_id="research_assistant",
        receiver_id="data_analyst",
        task_description="Please analyze this dataset and provide key insights: [10, 15, 20, 25, 30]",
        timeout=30,
    )

    logger.info(f"Collaboration result: {result}")

    # Clean up
    await hub.unregister_agent("research_assistant")
    await hub.unregister_agent("data_analyst")


async def main():
    try:
        # Run the direct communication example
        await direct_communication_example()

        # Run the hub communication example
        await hub_communication_example()

        logger.info("Examples completed successfully")
    except Exception as e:
        logger.exception(f"Error in examples: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
