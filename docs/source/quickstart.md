# Quickstart

AgentConnect lets you build, discover, and connect independent AI agents that can securely communicate and collaborate based on capabilities.

### Prerequisites

- Python 3.11 or higher
- Poetry (for dependency management)
- At least one provider API key (e.g., OPENAI_API_KEY, GROQ_API_KEY, etc.)

### Installation

```bash
git clone https://github.com/AKKI0511/AgentConnect.git
cd AgentConnect
poetry install --with demo,dev
copy example.env .env  # Windows
cp example.env .env    # Linux/Mac
```

Edit `.env` and add your API key(s):
```
OPENAI_API_KEY=your_openai_api_key
# or
GROQ_API_KEY=your_groq_api_key
```

### Minimal Example: Human-AI Chat

This example shows a simple interactive conversation between a human user and an AI assistant.

```python
import asyncio
import os
from dotenv import load_dotenv
from agentconnect.agents import AIAgent, HumanAgent
from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry
from agentconnect.core.types import AgentIdentity, Capability, InteractionMode, ModelName, ModelProvider

async def main():
    load_dotenv()
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    # Create agent identities
    human_identity = AgentIdentity.create_key_based()
    ai_identity = AgentIdentity.create_key_based()

    # Human agent
    human = HumanAgent(
        agent_id="human1", name="User", identity=human_identity, organization_id="org1"
    )

    # AI agent (choose your provider/model and set API key in .env)
    ai_assistant = AIAgent(
        agent_id="ai1",
        name="Assistant",
        provider_type=ModelProvider.OPENAI,  # or ModelProvider.GROQ, etc.
        model_name=ModelName.GPT4O,          # or another model supported by your provider
        api_key=os.getenv("OPENAI_API_KEY"),
        identity=ai_identity,
        capabilities=[Capability(
            name="conversation",
            description="General conversation and assistance",
        )],
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
        personality="helpful and professional",
        organization_id="org2",
    )
    
    # Register agents with the hub for discovery
    await hub.register_agent(human)
    await hub.register_agent(ai_assistant)
    
    # Start AI processing loop
    ai_task = asyncio.create_task(ai_assistant.run())
    
    # Start interactive session
    await human.start_interaction(ai_assistant)
    
    # Cleanup
    await ai_assistant.stop()
    await hub.unregister_agent(human.agent_id)
    await hub.unregister_agent(ai_assistant.agent_id)

if __name__ == "__main__":
    asyncio.run(main())
```

- Run the script. You can now chat with your AI assistant in the terminal!

### What's Next?
- See more [examples](https://akki0511.github.io/AgentConnect/examples/) for multi-agent workflows, payments, and advanced features.
- Explore the [API Reference](https://AKKI0511.github.io/AgentConnect/api/) for details on all classes and methods.
- Check the [User Guides](https://akki0511.github.io/AgentConnect/guides) for deeper tutorials. 