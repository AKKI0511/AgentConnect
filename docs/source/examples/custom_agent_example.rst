Custom Agent Example
==================

.. _custom_agent_example:

Creating a Custom Agent
---------------------

This example demonstrates how to create a custom agent by extending the base agent classes.

Implementing a Custom Agent
------------------------

Here's how to implement a custom agent:

.. code-block:: python

   from agentconnect.core.agent import BaseAgent
   from agentconnect.core.types import AgentType, AgentIdentity, Capability, InteractionMode
   from agentconnect.core.message import Message
   from typing import Optional
   import logging

   class CustomAgent(BaseAgent):
       """A custom agent implementation with specialized behavior"""
       
       def __init__(
           self,
           agent_id: str,
           name: str,
           identity: AgentIdentity,
           special_feature: str,
           organization_id: Optional[str] = None,
       ):
           # Define agent capabilities
           capabilities = [
               Capability(
                   name="custom_capability",
                   description="A specialized capability unique to this agent",
                   input_schema={"input_data": "string"},
                   output_schema={"result": "string"},
               )
           ]
           
           # Initialize base agent
           super().__init__(
               agent_id=agent_id,
               agent_type=AgentType.AI,  # Or custom type if needed
               identity=identity,
               capabilities=capabilities,
               interaction_modes=[InteractionMode.AGENT_TO_AGENT],
               organization_id=organization_id,
           )
           
           self.name = name
           self.special_feature = special_feature
           self.logger = logging.getLogger(f"CustomAgent-{agent_id}")
           
       async def process_message(self, message: Message) -> Optional[Message]:
           """Custom message processing logic"""
           # First call the base implementation for common processing
           response = await super().process_message(message)
           if response:
               return response
               
           self.logger.info(f"Processing message with special feature: {self.special_feature}")
           
           # Custom processing logic here
           processed_content = f"Processed with {self.special_feature}: {message.content}"
           
           # Create and return response
           return Message.create(
               sender_id=self.agent_id,
               receiver_id=message.sender_id,
               content=processed_content,
               sender_identity=self.identity,
               message_type=message.message_type,
           )

Using the Custom Agent
-------------------

Here's how to use the custom agent:

.. code-block:: python

   import asyncio
   from agentconnect.core.types import AgentIdentity
   from agentconnect.core.message import Message
   from agentconnect.core.types import MessageType
   
   # Create a custom agent
   custom_agent = CustomAgent(
       agent_id="custom1",
       name="CustomProcessor",
       identity=AgentIdentity.create_key_based(),
       special_feature="advanced_nlp",
       organization_id="example_org",
   )
   
   # Create another agent to interact with the custom agent
   regular_agent = AIAgent(
       agent_id="regular1",
       name="RegularAgent",
       provider_type=ModelProvider.OPENAI,
       model_name=ModelName.GPT4O,
       api_key=os.getenv("OPENAI_API_KEY"),
       identity=AgentIdentity.create_key_based(),
       organization_id="example_org",
   )
   
   # Send a message from regular agent to custom agent
   message = Message.create(
       sender_id=regular_agent.agent_id,
       receiver_id=custom_agent.agent_id,
       content="Please process this text using your special capabilities",
       sender_identity=regular_agent.identity,
       message_type=MessageType.TEXT,
   )
   
   # Process the message
   response = await custom_agent.process_message(message)
   print(f"Response from custom agent: {response.content}")

Integrating with Communication Hub
-------------------------------

Here's how to integrate the custom agent with the communication hub:

.. code-block:: python

   import asyncio
   from agentconnect.core.registry import AgentRegistry
   from agentconnect.communication.hub import CommunicationHub
   
   # Create registry and hub
   registry = AgentRegistry()
   hub = CommunicationHub(registry)
   
   # Create message handler for tracking communication
   async def message_handler(message: Message) -> None:
       print(f"Message to custom agent: {message.content[:50]}...")
   
   # Create and register agents
   custom_agent = CustomAgent(
       agent_id="custom_agent",
       name="CustomAgent",
       identity=AgentIdentity.create_key_based(),
       special_feature="data_transformation",
       organization_id="example_org",
   )
   
   regular_agent = AIAgent(
       agent_id="regular_agent",
       name="RegularAgent",
       provider_type=ModelProvider.GOOGLE,
       model_name=ModelName.GEMINI2_FLASH,
       api_key=os.getenv("GOOGLE_API_KEY"),
       identity=AgentIdentity.create_key_based(),
       organization_id="example_org",
       interaction_modes=[InteractionMode.AGENT_TO_AGENT],
   )
   
   # Register agents with the hub
   await hub.register_agent(custom_agent)
   await hub.register_agent(regular_agent)
   
   # Add message handler to track communication with custom agent
   hub.add_message_handler("custom_agent", message_handler)
   
   # Send collaboration request
   result = await hub.send_collaboration_request(
       sender_id="regular_agent",
       receiver_id="custom_agent",
       task_description="Transform this dataset using your custom capability",
       timeout=30,
   )
   
   print(f"Collaboration result: {result}")

Advanced Custom Agent Features
---------------------------

Here are some advanced features you can implement in your custom agent:

.. code-block:: python

   import os
   import json
   from typing import Dict, Any, List
   
   class AdvancedCustomAgent(BaseAgent):
       """Advanced custom agent with memory and state management"""
       
       def __init__(self, agent_id: str, name: str, identity: AgentIdentity, **kwargs):
           super().__init__(agent_id=agent_id, identity=identity, **kwargs)
           self.name = name
           self.memory: Dict[str, Any] = {}
           self.conversation_history: List[Dict[str, str]] = []
           
       async def process_message(self, message: Message) -> Optional[Message]:
           # Track conversation history
           self.conversation_history.append({
               "sender": message.sender_id,
               "content": message.content,
               "timestamp": str(datetime.now())
           })
           
           # Custom processing using memory
           if "remember" in message.content.lower():
               # Extract what to remember
               key_value = self._extract_memory_request(message.content)
               if key_value:
                   key, value = key_value
                   self.memory[key] = value
                   return Message.create(
                       sender_id=self.agent_id,
                       receiver_id=message.sender_id,
                       content=f"I've remembered that {key} is {value}",
                       sender_identity=self.identity,
                       message_type=MessageType.TEXT,
                   )
           
           if "recall" in message.content.lower():
               # Extract what to recall
               key = self._extract_recall_request(message.content)
               if key and key in self.memory:
                   return Message.create(
                       sender_id=self.agent_id,
                       receiver_id=message.sender_id,
                       content=f"You asked me to recall {key}, it's {self.memory[key]}",
                       sender_identity=self.identity,
                       message_type=MessageType.TEXT,
                   )
           
           # Fall back to regular processing
           return await super().process_message(message)
           
       def _extract_memory_request(self, content: str) -> Optional[tuple]:
           # Simple parsing logic - in a real agent you might use NLP
           if "remember that" in content.lower():
               parts = content.lower().split("remember that", 1)[1].strip()
               if " is " in parts:
                   key, value = parts.split(" is ", 1)
                   return (key.strip(), value.strip())
           return None
           
       def _extract_recall_request(self, content: str) -> Optional[str]:
           # Simple parsing logic
           if "recall" in content.lower():
               parts = content.lower().split("recall", 1)[1].strip()
               return parts.strip()
           return None
           
       def save_state(self, filepath: str) -> None:
           """Save agent memory and history to file"""
           state = {
               "agent_id": self.agent_id,
               "memory": self.memory,
               "conversation_history": self.conversation_history
           }
           with open(filepath, 'w') as f:
               json.dump(state, f, indent=2)
               
       def load_state(self, filepath: str) -> None:
           """Load agent memory and history from file"""
           if os.path.exists(filepath):
               with open(filepath, 'r') as f:
                   state = json.load(f)
                   self.memory = state.get("memory", {})
                   self.conversation_history = state.get("conversation_history", []) 