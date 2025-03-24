Basic Example
=============

.. _basic_example:

Getting Started with AgentConnect
-------------------------------

This example demonstrates the basic usage of AgentConnect to create and use AI agents.

Creating a Simple Agent
--------------------

Here's how to create a simple AI agent:

.. code-block:: python

   from agentconnect.agents.ai_agent import AIAgent
   from agentconnect.core.types import (
       ModelProvider,
       ModelName,
       AgentIdentity,
       InteractionMode,
   )
   import os

   # Create an AI agent
   ai_agent = AIAgent(
       agent_id="assistant",
       name="AI Assistant",
       provider_type=ModelProvider.GOOGLE,  # Or any provider you prefer
       model_name=ModelName.GEMINI2_FLASH_LITE,  # Or any model you prefer
       api_key=os.getenv("GOOGLE_API_KEY"),
       identity=AgentIdentity.create_key_based(),
       personality="helpful and friendly assistant",
       organization_id="example_org",
       interaction_modes=[
           InteractionMode.HUMAN_TO_AGENT,
           InteractionMode.AGENT_TO_AGENT,
       ],
   )

Sending Messages to an Agent
-------------------------

Once you have created an agent, you can send messages to it:

.. code-block:: python

   from agentconnect.agents.human_agent import HumanAgent
   from agentconnect.core.message import Message
   from agentconnect.core.types import MessageType

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
   response = await ai_agent.process_message(message)

   if response:
       print(f"Received response: {response.content}")
   else:
       print("No response received")

Using the Communication Hub
-------------------------

AgentConnect provides a communication hub for agent interaction:

.. code-block:: python

   from agentconnect.core.registry import AgentRegistry
   from agentconnect.communication.hub import CommunicationHub

   # Create registry and hub
   registry = AgentRegistry()
   hub = CommunicationHub(registry)

   # Create AI agents
   ai_agent1 = AIAgent(
       agent_id="research_assistant",
       name="Research Assistant",
       provider_type=ModelProvider.GOOGLE,
       model_name=ModelName.GEMINI2_FLASH_LITE,
       api_key=os.getenv("GOOGLE_API_KEY"),
       identity=AgentIdentity.create_key_based(),
       personality="knowledgeable research assistant",
       organization_id="example_org",
       interaction_modes=[InteractionMode.AGENT_TO_AGENT],
   )

   ai_agent2 = AIAgent(
       agent_id="data_analyst",
       name="Data Analyst",
       provider_type=ModelProvider.GOOGLE,
       model_name=ModelName.GEMINI2_FLASH,
       api_key=os.getenv("GOOGLE_API_KEY"),
       identity=AgentIdentity.create_key_based(),
       personality="precise and analytical data specialist",
       organization_id="example_org",
       interaction_modes=[InteractionMode.AGENT_TO_AGENT],
   )

   # Register agents with the hub
   await hub.register_agent(ai_agent1)
   await hub.register_agent(ai_agent2)
   
   # Add a message handler to track communication
   async def message_handler(message):
       print(f"Message: {message.sender_id} → {message.receiver_id}: {message.content[:50]}...")
   
   hub.add_message_handler(ai_agent1.agent_id, message_handler)
   hub.add_message_handler(ai_agent2.agent_id, message_handler)

Complete Example
-------------

Here's a complete example that puts everything together:

.. code-block:: python

   import asyncio
   import os
   from dotenv import load_dotenv
   
   from agentconnect.agents.ai_agent import AIAgent
   from agentconnect.agents.human_agent import HumanAgent
   from agentconnect.core.message import Message
   from agentconnect.core.registry import AgentRegistry
   from agentconnect.communication.hub import CommunicationHub
   from agentconnect.core.types import (
       ModelProvider,
       ModelName,
       AgentIdentity,
       InteractionMode,
       MessageType,
   )
   
   async def main():
       # Load environment variables
       load_dotenv()
       
       # Create registry and hub
       registry = AgentRegistry()
       hub = CommunicationHub(registry)
       
       # Create agents
       ai_agent = AIAgent(
           agent_id="ai_assistant",
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
       
       # Register agent with the hub
       await hub.register_agent(ai_agent)
       
       # Start AI processing
       ai_task = asyncio.create_task(ai_agent.run())
       
       # Create a human agent
       human = HumanAgent(
           agent_id="human_user",
           name="Human User",
           identity=AgentIdentity.create_key_based(),
           organization_id="example_org",
       )
       
       # Register human with hub
       await hub.register_agent(human)
       
       # Start interaction
       await human.start_interaction(ai_agent)
       
       # Cleanup
       ai_agent.is_running = False
       await ai_task
       await hub.unregister_agent(human.agent_id)
       await hub.unregister_agent(ai_agent.agent_id)
   
   if __name__ == "__main__":
       asyncio.run(main())
