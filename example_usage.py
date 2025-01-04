import asyncio
import os
from dotenv import load_dotenv
from src.agents.human_agent import HumanAgent
from src.agents.ai_agent import AIAgent
from src.communication.hub import CommunicationHub
from src.core.types import ModelProvider, ModelName
from src.providers.provider_factory import ProviderFactory

async def main():
    load_dotenv()  # Load environment variables from .env file
    
    # Get provider type and model from user input
    print("Available providers:")
    for provider in ModelProvider:
        print(f"- {provider.value}")
    
    provider_name = input("Select provider: ").lower()
    provider_type = ModelProvider(provider_name)
    
    # Create provider instance to get available models
    api_key = os.getenv(f"{provider_name.upper()}_API_KEY")
    provider = ProviderFactory.create_provider(provider_type, api_key)
    
    print("\nAvailable models:")
    available_models = provider.get_available_models()
    for model in available_models:
        print(f"- {model.value}")
    
    model_name = ModelName(input("Select model: "))
    
    # Initialize hub and agents
    hub = CommunicationHub()
    human = HumanAgent("human1", "User")
    ai_assistant = AIAgent(
        "ai1", 
        "Assistant",
        provider_type,
        model_name,
        api_key,
        ["conversation"]
    )
    
    # Register agents
    hub.register_agent(human)
    hub.register_agent(ai_assistant)
    
    # Start AI agent's message processing loop
    ai_task = asyncio.create_task(ai_assistant.run())
    
    # Start interactive chat
    try:
        await human.start_interaction(ai_assistant)
    except KeyboardInterrupt:
        print("\nChat session ended by user.")
    finally:
        # Clean up
        ai_assistant.is_running = False  # Stop the AI agent's loop
        await ai_task  # Wait for AI agent to finish
        print("AI chat history:\n", str([f'{m.sender_id}: {m.content}\n' for m in ai_assistant.message_history]))
        print("-"*60)
        print("Human chat history:\n", [f'{m.sender_id}: {m.content}\n' for m in human.message_history])
        print("-"*60)
        print("AI conversation history:\n", str([f'{m.sender_id}: {m.content}\n' for m in ai_assistant.conversation_history]))


        hub.unregister_agent(human.agent_id)
        hub.unregister_agent(ai_assistant.agent_id)

if __name__ == "__main__":
    asyncio.run(main())
