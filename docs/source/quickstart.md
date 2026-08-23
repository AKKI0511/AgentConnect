# Quickstart

AgentConnect lets you build, discover, and connect independent AI agents that can securely communicate and collaborate based on capabilities.

### Prerequisites

- Python 3.11 or higher
- Poetry (for dependency management)
- At least one provider API key (e.g., OPENAI_API_KEY, GROQ_API_KEY, GOOGLE_API_KEY)

### Installation

```bash
git clone https://github.com/AKKI0511/AgentConnect.git
cd AgentConnect
poetry install --with demo,dev --extras "telegram payments cli"
copy example.env .env  # Windows
cp example.env .env    # Linux/Mac
```

Edit `.env` and add at least one provider API key:
```
# Choose one provider and set its key
OPENAI_API_KEY=your_openai_api_key
# or
GROQ_API_KEY=your_groq_api_key
# or
GOOGLE_API_KEY=your_google_api_key
```

## Programmatic Agent Discovery + A2A

This example demonstrates **Agent Discovery** and **Agent-to-Agent (A2A) Communication** using `AIAgent.chat()`. The assistant agent discovers the research agent and delegates a task to it programmatically.

```python
import asyncio
import os
from dotenv import load_dotenv

from agentconnect.prebuilt import AIAgent
from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry
from agentconnect.core.types import (
    AgentIdentity,
    AgentProfile,
    AgentType,
    Capability,
    Skill,
    ModelName,
    ModelProvider,
)

async def main():
    load_dotenv()

    # Local registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    # Create a research agent
    research_profile = AgentProfile(
        agent_id="researcher_1",
        agent_type=AgentType.AI,
        name="Researcher",
        summary="Expert researcher with deep knowledge on any topic",
        capabilities=[
            Capability(name="research", description="Research and summarize any topic in depth"),
        ],
        skills=[
            Skill(name="Information synthesis", description="Expert at synthesizing complex information"),
            Skill(name="Academic research", description="Deep knowledge of research methodologies"),
        ],
    )

    research = AIAgent(
        agent_id=research_profile.agent_id,
        identity=AgentIdentity.create_key_based(),
        provider_type=ModelProvider.OPENAI,  # or GROQ/GOOGLE/ANTHROPIC
        model_name=ModelName.GPT4O,
        api_key=os.getenv("OPENAI_API_KEY"),
        profile=research_profile,
        personality="You are a deep research agent with a passion for knowledge. You are able to research and summarize any topic in depth.",
    )

    # Create an assistant agent
    assistant_profile = AgentProfile(
        agent_id="assistant_1",
        agent_type=AgentType.AI,
        name="Assistant",
        summary="General helper that can collaborate",
        capabilities=[
            Capability(name="conversation", description="General conversation and assistance"),
        ],
        skills=[
            Skill(name="Collaboration", description="Expert at coordinating with other agents"),
        ],
    )

    assistant = AIAgent(
        agent_id=assistant_profile.agent_id,
        identity=AgentIdentity.create_key_based(),
        provider_type=ModelProvider.OPENAI,  # or GROQ/GOOGLE/ANTHROPIC
        model_name=ModelName.GPT4O,
        api_key=os.getenv("OPENAI_API_KEY"),
        profile=assistant_profile,
        personality="helpful and concise",
    )

    # Register agents to enable discovery
    await hub.register_agent(research)
    await hub.register_agent(assistant)

    # Start workers so delegated requests are processed
    r_task = asyncio.create_task(research.run())
    a_task = asyncio.create_task(assistant.run())

    # Agent Discovery + A2A: assistant finds research agent and delegates a task
    result = await assistant.chat(
        "Find a research agent and ask them to summarize RAG in 3 short bullets."
    )
    print(result)

    # Cleanup
    await assistant.stop()
    await research.stop()
    await hub.unregister_agent(assistant.agent_id)
    await hub.unregister_agent(research.agent_id)
    r_task.cancel()
    a_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
```

**Key Points:**

- **Connect before first chat**: Register agents with the hub and registry before calling `.chat()` to enable Agent Discovery and A2A tools.
- **Discovery-only** (no run loops): If you only need to discover agents (e.g., "Find a research agent and show the best profile"), you don't need to start `run()` loops.
- **A2A delegation** (with run loops): To send tasks to other agents and receive responses, start their `run()` loops so they can process incoming requests.
- **Skills and Capabilities**: Agent Discovery searches across both capabilities (specific tasks) and skills (expertise areas). Use both for richer discovery.

Save this as `examples/programmatic_a2a.py` and run it with Poetry: `poetry run python examples/programmatic_a2a.py`.

---

## Interactive CLI Chat

For interactive terminal-based chat, use `HumanAgent` to communicate with an AI agent:

```python
import asyncio
import os
from dotenv import load_dotenv

from agentconnect.prebuilt import AIAgent, HumanAgent
from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry
from agentconnect.core.types import (
    AgentIdentity,
    AgentProfile,
    AgentType,
    Capability,
    InteractionMode,
    ModelName,
    ModelProvider,
)

async def main():
    load_dotenv()

    # Local registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    # Create identities
    human_identity = AgentIdentity.create_key_based()
    ai_identity = AgentIdentity.create_key_based()

    # Define the AI agent via AgentProfile
    ai_profile = AgentProfile(
        agent_id="ai_assistant_01",
        agent_type=AgentType.AI,
        name="Assistant",
        summary="Helpful conversational assistant",
        capabilities=[
            Capability(name="conversation", description="General conversation and assistance"),
        ],
    )

    # Instantiate agents
    human = HumanAgent(
        agent_id="human_01",
        name="User",
        identity=human_identity,
    )

    ai_assistant = AIAgent(
        agent_id=ai_profile.agent_id,
        identity=ai_identity,
        provider_type=ModelProvider.OPENAI,  # or GROQ/GOOGLE/ANTHROPIC
        model_name=ModelName.GPT4O,
        api_key=os.getenv("OPENAI_API_KEY"),
        profile=ai_profile,
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
        personality="helpful and professional",
    )

    # Register with the local hub
    await hub.register_agent(human)
    await hub.register_agent(ai_assistant)

    # Start AI processing loop
    ai_task = asyncio.create_task(ai_assistant.run())

    try:
        # Start interactive session in terminal
        await human.start_interaction(ai_assistant)
    finally:
        # Cleanup
        await ai_assistant.stop()
        await hub.unregister_agent(human.agent_id)
        await hub.unregister_agent(ai_assistant.agent_id)

if __name__ == "__main__":
    asyncio.run(main())
```

- Save this as `examples/interactive_cli.py` and run it with Poetry: `poetry run python examples/interactive_cli.py`.
- You can now chat with your AI assistant in the terminal. Type "exit", "quit", or "bye" to end the conversation.

For more details on `HumanAgent`, see the [HumanAgent guide](https://AKKI0511.github.io/AgentConnect/guides/core/agents/human_agent).

---

### What's Next?
- Explore more advanced topics in the [User Guides](https://AKKI0511.github.io/AgentConnect/guides/), including Agent Discovery, A2A workflows, and MCP tools.
- See more [Examples](https://AKKI0511.github.io/AgentConnect/examples/) for multi-agent workflows and extended capabilities.
- Browse the [API Reference](https://AKKI0511.github.io/AgentConnect/api/) for class and method details.
