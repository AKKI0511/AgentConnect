import asyncio
from agentconnect.agents import AIAgent, HumanAgent
from agentconnect.core.registry import AgentRegistry
from agentconnect.communication import CommunicationHub
from agentconnect.core.types import ModelProvider, ModelName, AgentIdentity, InteractionMode
from agentconnect.utils.logging_config import setup_logging, LogLevel
import os

setup_logging(level=LogLevel.DEBUG)

async def main():
    # Create registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    # Create and register agents
    ai_agent = AIAgent(
        agent_id="assistant",
        name="AI Assistant",
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key=os.getenv("OPENAI_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT]
    )
    await hub.register_agent(ai_agent)

    human = HumanAgent(
        agent_id="human-user",
        name="Human User",
        identity=AgentIdentity.create_key_based()
    )
    await hub.register_agent(human)

    # Start interaction
    asyncio.create_task(ai_agent.run())
    await human.start_interaction(ai_agent)

if __name__ == "__main__":
    asyncio.run(main())