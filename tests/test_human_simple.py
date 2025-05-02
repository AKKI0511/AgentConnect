import asyncio
import os
import sys
from dotenv import load_dotenv

from agentconnect.agents import AIAgent, HumanAgent
from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry
from agentconnect.utils.logging_config import setup_logging, LogLevel, disable_all_logging
from agentconnect.core.types import (
    AgentIdentity,
    Capability,
    InteractionMode,
    ModelName,
    ModelProvider,
    MessageType
)

# Global variables for state tracking
human_responded = asyncio.Event()
conversation_ended = asyncio.Event()

# Callback to notify when human responds
def response_handler(response_data):
    """Callback when human sends a message"""
    global human_responded, conversation_ended
    
    # Check if this is an exit message
    message_type = response_data.get('message_type', MessageType.TEXT)
    if message_type == MessageType.STOP or response_data.get('content') == "__EXIT__":
        print("Human requested to end the conversation.")
        conversation_ended.set()
        
    # Signal response received
    human_responded.set()

async def main():
    setup_logging(LogLevel.INFO)
    load_dotenv()
    
    # Basic test to verify human-in-the-loop works
    print("=== SIMPLIFIED HUMAN-IN-THE-LOOP TEST ===")
    print("You can now interact with the AI agent.")
    print("- Type any message to respond")
    print("- Press Enter without typing to skip responding")
    print("- Type 'exit', 'quit', or 'bye' to end the conversation")
    
    # Initialize registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)
    
    # Create identities
    human_identity = AgentIdentity.create_key_based()
    ai_identity = AgentIdentity.create_key_based()
    
    # Create agents
    human = HumanAgent(
        agent_id="human1",
        name="User",
        identity=human_identity,
        organization_id="org1",
        response_callbacks=[response_handler]
    )
    
    ai_assistant = AIAgent(
        agent_id="ai1",
        name="Assistant",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_5_FLASH_PREVIEW,
        api_key=os.getenv("GOOGLE_API_KEY", "fake-key-for-testing"),
        identity=ai_identity,
        capabilities=[],
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
        personality="helpful",
        organization_id="org1",
    )
    
    try:
        # Register and start agents
        await hub.register_agent(human)
        await hub.register_agent(ai_assistant)
        
        human_task = asyncio.create_task(human.run())
        ai_task = asyncio.create_task(ai_assistant.run())
        
        # Reset events
        human_responded.clear()
        conversation_ended.clear()
        
        # AI sends a simple message to human
        print("\nAI sending test message to start conversation...")
        await ai_assistant.send_message(
            receiver_id=human.agent_id,
            content="Hello! This is a test of the human-in-the-loop interaction. You can respond normally, "
                   "skip responding by pressing Enter, or end the conversation by typing 'exit'.",
            message_type=MessageType.TEXT
        )
        
        # Wait for conversation to end or max timeout (5 minutes)
        print("\nConversation active - waiting for it to end naturally or timeout after 5 minutes...")
        try:
            await asyncio.wait_for(conversation_ended.wait(), timeout=300)
            print("\nTest successful! Conversation ended naturally.")
        except asyncio.TimeoutError:
            print("\nTest timeout reached after 5 minutes.")
        
    except Exception as e:
        print(f"Error during test: {str(e)}")
    finally:
        # Clean up
        print("\nShutting down...")
        await ai_assistant.stop()
        await human.stop()
        await hub.unregister_agent(human.agent_id)
        await hub.unregister_agent(ai_assistant.agent_id)
        
        # Cancel tasks
        human_task.cancel()
        ai_task.cancel()
        try:
            await human_task
        except asyncio.CancelledError:
            pass
        try:
            await ai_task
        except asyncio.CancelledError:
            pass
        
        print("Test completed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest terminated by user.")
        sys.exit(0) 