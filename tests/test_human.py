import asyncio
import os
from dotenv import load_dotenv

from agentconnect.agents import AIAgent, HumanAgent
from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry
from agentconnect.core.types import (
    AgentIdentity,
    Capability,
    InteractionMode,
    ModelName,
    ModelProvider,
    MessageType
)

async def main():
    # Load environment variables
    load_dotenv()

    # Initialize registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    # Create agent identities
    human_identity = AgentIdentity.create_key_based()
    ai_identity = AgentIdentity.create_key_based()

    # Create a human agent
    human = HumanAgent(
        agent_id="human1",
        name="User",
        identity=human_identity,
        organization_id="org1"
    )

    # Create an AI agent
    ai_assistant = AIAgent(
        agent_id="ai1",
        name="Assistant",
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key=os.getenv("OPENAI_API_KEY"),
        identity=ai_identity,
        capabilities=[Capability(
            name="data_analysis",
            description="Analyze data and provide insights",
            input_schema={"data": "string"},
            output_schema={"analysis": "string"},
        )],
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT, InteractionMode.AGENT_TO_AGENT],
        personality="professional and thorough",
        organization_id="org1",
    )

    # Register both agents with the hub
    await hub.register_agent(human)
    await hub.register_agent(ai_assistant)

    # Start both agent processing loops
    human_task = asyncio.create_task(human.run())
    ai_task = asyncio.create_task(ai_assistant.run())

    try:
        # Simulate AI agent performing a task
        print("AI agent performing analysis...")
        await asyncio.sleep(2)  # Simulate work

        analysis_result = "Based on the data, I recommend Strategy A with 78% confidence."

        # AI sends results to human for approval
        print("AI agent requesting human approval...")
        await ai_assistant.send_message(
            receiver_id=human.agent_id,
            content=f"I've completed my analysis:\n\n{analysis_result}\n\nDo you approve this recommendation? (Type 'approve' or 'reject')",
            message_type=MessageType.TEXT
        )

        # At this point, the human will see the message in their terminal
        # and will be prompted to respond. The script will wait at this point.

        # Let the interaction run for a while
        print("Waiting for human interaction (30 seconds)...")
        await asyncio.sleep(30)

    finally:
        # Cleanup
        print("Shutting down agents...")
        await ai_assistant.stop()
        await human.stop()
        await hub.unregister_agent(human.agent_id)
        await hub.unregister_agent(ai_assistant.agent_id)
        print("Done.")

if __name__ == "__main__":
    asyncio.run(main())