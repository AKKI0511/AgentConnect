"""
Basic example demonstrating how to create and use agents in AgentConnect.

This example shows:
1. Using the simple chat() method for direct interaction with an AI agent
2. Creating and configuring AI agents with different parameters
3. Using agents in standalone mode without a communication hub
4. Properly starting and stopping agents
"""

import asyncio
import os
from dotenv import load_dotenv
import logging

from agentconnect.agents.ai_agent import AIAgent
from agentconnect.core.types import (
    ModelProvider,
    ModelName,
    AgentIdentity,
    AgentProfile,
    AgentType,
    Capability,
    Skill,
)
from agentconnect.utils.logging_config import setup_logging, LogLevel

# Load environment variables
load_dotenv()

# Configure logging
setup_logging(level=LogLevel.INFO)
logger = logging.getLogger("AgentExample")


async def simple_chat_example():
    """Example of using the chat() method for direct interaction with an AI agent"""
    logger.info("=== Simple Chat Example ===")

    # Create an AI agent
    ai_agent = AIAgent(
        agent_id="simple_assistant",
        name="Simple Assistant",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH_LITE,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        personality="helpful and friendly assistant",
    )

    # Use the chat() method for direct interaction
    logger.info("Sending query to AI agent using chat() method")
    response = await ai_agent.chat(
        query="What are the benefits of using a multi-agent system?",
        conversation_id="simple_chat_example"
    )

    logger.info(f"Received response: {response}")

    # You can continue the same conversation
    logger.info("Sending follow-up query")
    follow_up_response = await ai_agent.chat(
        query="Can you give me a specific example of agents collaborating?",
        conversation_id="simple_chat_example"  # Same conversation ID to maintain context
    )

    logger.info(f"Received follow-up response: {follow_up_response}")


async def multi_conversation_example():
    """Example showing how to maintain multiple conversations with a single agent"""
    logger.info("\n=== Multiple Conversations Example ===")
    
    # Create an AI agent with AgentProfile
    agent_profile = AgentProfile(
        agent_id="multi_conv_assistant",
        agent_type=AgentType.AI,
        name="Multi-Conversation Assistant",
        summary="An assistant that can maintain multiple conversation contexts",
        description="An assistant that can handle multiple independent conversations simultaneously, maintaining context for each conversation.",
        version="1.0.0",
        capabilities=[
            Capability(
                name="context_management",
                description="Maintains separate contexts for multiple conversations",
                input_schema={"conversation_id": "string", "query": "string"},
                output_schema={"response": "string"},
            )
        ],
        skills=[
            Skill(name="context_tracking", description="Tracks conversation context across multiple threads"),
            Skill(name="topic_switching", description="Switches between different conversation topics"),
        ],
        tags=["assistant", "context", "conversation"],
        examples=[
            "Handle multiple conversations with different topics",
            "Maintain context across conversation threads"
        ]
    )
    
    ai_agent = AIAgent(
        agent_id="multi_conv_assistant",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH_LITE,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        profile=agent_profile,
        personality="helpful assistant that maintains context",
    )
    
    # Start conversation 1
    logger.info("Starting conversation 1 about programming")
    response1 = await ai_agent.chat(
        query="What are the key principles of object-oriented programming?",
        conversation_id="programming_conversation"
    )
    logger.info(f"Conversation 1 response: {response1[:100]}...")
    
    # Start conversation 2 (different topic, different conversation ID)
    logger.info("Starting conversation 2 about cooking")
    response2 = await ai_agent.chat(
        query="What are some easy recipes for beginners?",
        conversation_id="cooking_conversation"
    )
    logger.info(f"Conversation 2 response: {response2[:100]}...")
    
    # Continue conversation 1
    logger.info("Continuing conversation 1 about programming")
    follow_up1 = await ai_agent.chat(
        query="Can you give an example of polymorphism?",
        conversation_id="programming_conversation"  # Same as first query
    )
    logger.info(f"Conversation 1 follow-up: {follow_up1[:100]}...")
    
    # Continue conversation 2
    logger.info("Continuing conversation 2 about cooking")
    follow_up2 = await ai_agent.chat(
        query="How do I know when pasta is cooked properly?",
        conversation_id="cooking_conversation"  # Same as second query
    )
    logger.info(f"Conversation 2 follow-up: {follow_up2[:100]}...")
    
    logger.info("Both conversations maintained separate context successfully")


async def ai_agent_configuration_example():
    """Example showing different ways to configure an AI agent"""
    logger.info("\n=== AI Agent Configuration Example ===")
    
    # Basic configuration with AgentProfile
    basic_profile = AgentProfile(
        agent_id="basic_agent",
        agent_type=AgentType.AI,
        name="Basic Assistant",
        summary="A simple assistant with minimal configuration",
        description="A basic assistant that demonstrates minimal required configuration for an AI agent.",
        version="1.0.0",
    )
    
    basic_agent = AIAgent(
        agent_id="basic_agent",
        identity=AgentIdentity.create_key_based(),
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH_LITE,
        api_key=os.getenv("GOOGLE_API_KEY"),
        profile=basic_profile,
    )
    logger.info("Created basic agent with minimal configuration")
    
    # Advanced configuration with custom model parameters
    advanced_profile = AgentProfile(
        agent_id="advanced_agent",
        agent_type=AgentType.AI,
        name="Advanced Assistant",
        summary="An assistant with advanced configuration",
        description="An advanced assistant that demonstrates custom model parameters and advanced configuration options.",
        version="1.0.0",
        capabilities=[
            Capability(
                name="detailed_explanations",
                description="Provides detailed and analytical explanations",
                input_schema={"topic": "string"},
                output_schema={"explanation": "string"},
            )
        ],
        skills=[
            Skill(name="analytical_thinking", description="Analyzes topics in detail"),
            Skill(name="technical_explanation", description="Explains technical concepts clearly"),
        ],
    )
    
    advanced_agent = AIAgent(
        agent_id="advanced_agent",
        identity=AgentIdentity.create_key_based(),
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH,
        api_key=os.getenv("GOOGLE_API_KEY"),
        profile=advanced_profile,
        personality="analytical and detailed",
        model_config={
            "temperature": 0.7,
            "top_p": 0.95,
            "max_tokens": 500
        },
        max_tokens_per_minute=10000,
        max_tokens_per_hour=100000,
        verbose=True
    )
    logger.info("Created advanced agent with custom model parameters")
    
    # Test the advanced agent with a simple query
    response = await advanced_agent.chat(
        query="Explain how temperature affects AI text generation",
        conversation_id="config_example"
    )
    logger.info(f"Advanced agent response: {response[:100]}...")


async def agent_lifecycle_example():
    """Example showing how to properly start and stop an agent"""
    logger.info("\n=== Agent Lifecycle Example ===")
    
    # Create an AI agent with AgentProfile
    lifecycle_profile = AgentProfile(
        agent_id="lifecycle_agent",
        agent_type=AgentType.AI,
        name="Lifecycle Agent",
        summary="An agent demonstrating proper lifecycle management",
        description="An agent that demonstrates proper initialization, running, and cleanup of agent resources.",
        version="1.0.0",
    )
    
    ai_agent = AIAgent(
        agent_id="lifecycle_agent",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH_LITE,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        profile=lifecycle_profile,
        personality="helpful assistant",
    )
    
    # Start the agent's processing loop
    logger.info("Starting agent processing loop")
    agent_task = asyncio.create_task(ai_agent.run())
    
    # Allow some time for the agent to initialize
    await asyncio.sleep(1)
    
    # Send a query while the agent is running
    logger.info("Sending query to running agent")
    response = await ai_agent.chat(
        query="What's the advantage of properly starting and stopping an agent?",
        conversation_id="lifecycle_example"
    )
    logger.info(f"Response from running agent: {response[:100]}...")
    
    # Properly stop the agent
    logger.info("Stopping the agent")
    await ai_agent.stop()
    
    # Cancel the agent task
    agent_task.cancel()
    try:
        await agent_task
    except asyncio.CancelledError:
        logger.info("Agent task cancelled successfully")
    
    logger.info("Agent lifecycle example completed")


async def main():
    try:
        # Run the simple chat example
        await simple_chat_example()
        
        # Run the multiple conversations example
        await multi_conversation_example()
        
        # Run the configuration example
        await ai_agent_configuration_example()
        
        # Run the agent lifecycle example
        await agent_lifecycle_example()

        logger.info("Examples completed successfully")
    except Exception as e:
        logger.exception(f"Error in examples: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
