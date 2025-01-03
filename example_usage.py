# example_usage.py
import asyncio
from src.agents.human_agent import HumanAgent
from src.agents.ai_agent import AIAgent
from src.communication.hub import CommunicationHub


async def main():
    # Initialize hub
    hub = CommunicationHub()

    # Create agents
    human = HumanAgent("human1", "Alice")
    ai = AIAgent("ai1", "Assistant", ["text_processing"])

    # Register agents
    hub.register_agent(human)
    hub.register_agent(ai)

    # Send a message
    await human.send_message(ai, "Hello, can you help me?")

    # Process messages
    while not ai.message_queue.empty():
        message = await ai.message_queue.get()
        response = await ai.process_message(message)
        if response:
            await ai.send_message(human, response.content)


if __name__ == "__main__":
    asyncio.run(main())
