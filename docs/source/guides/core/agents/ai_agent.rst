AIAgent
=======

.. _ai_agent:

Prerequisites
-------------

Before you start, complete the :doc:`../../../installation` setup. If you're new to the framework, skim :doc:`../../core_concepts` for the mental model.

What Is AIAgent
---------------

:class:`AIAgent <agentconnect.prebuilt.AIAgent>` is a ready-to-use AI-powered agent that extends :class:`BaseAgent <agentconnect.core.agent.BaseAgent>` with language model capabilities. It provides intelligent message processing using LLMs from providers like OpenAI, Anthropic, Google, and Groq, and includes built-in collaboration tools for agent discovery and agent-to-agent (A2A) communication.

``AIAgent`` is the recommended choice when you need an autonomous agent that generates intelligent responses, collaborates with other agents, and integrates seamlessly with the AgentConnect ecosystem—without building your own orchestration logic.

.. admonition:: At a glance
   :class: tip

   - Ready-to-use: Built on :class:`BaseAgent <agentconnect.core.agent.BaseAgent>` with LangChain/LangGraph workflows
   - Use ``.chat()`` for direct queries with or without hub/registry setup
   - Auto-enables collaboration: Built-in tools (search/send/check) activate when connected to hub + registry
   - Supports customization: Add your own LangChain tools, configure rate limits, enable payments

When To Use It
--------------

Use ``AIAgent`` when:

- You need an LLM-powered agent for conversational or reasoning tasks
- You want built-in Agent discovery and Agent-to-Agent Collaboration tools (search, send, check)
- You need rate limiting, token management, and safety controls
- You want to quickly prototype agent-based systems

Use ``BaseAgent`` instead when:

- You need complete control over message processing logic
- You're integrating an existing framework (AutoGen, CrewAI, Google ADK) or wrapping provider SDKs directly (OpenAI, Anthropic)
- You want to implement custom orchestration or state management

How To Use It
-------------

``AIAgent`` can be used in two ways: via the ``.chat()`` method for direct interaction, or programmatically via ``send_message()`` and ``process_message()`` for custom workflows.

Using chat() (Direct Interaction)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``.chat()`` method provides a simple interface for interacting with the agent:

.. code-block:: python

    import asyncio
    import os
    from dotenv import load_dotenv
    from agentconnect.prebuilt import AIAgent
    from agentconnect.communication import CommunicationHub
    from agentconnect.core.registry import AgentRegistry
    from agentconnect.core.types import AgentIdentity, ModelProvider, ModelName

    async def main():
        load_dotenv()

        ##### Standalone: works immediately, no A2A tools
        agent = AIAgent(
            agent_id="chat_bot",
            name="Chat Bot",
            identity=AgentIdentity.create_key_based(),
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O_MINI,
            api_key=os.getenv("OPENAI_API_KEY"),
            personality="friendly and conversational",
        )
        # response = await agent.chat("Explain RAG in 2 sentences.")
        # print(response)

        ##### Connected: register first to enable A2A tools
        registry = AgentRegistry()
        hub = CommunicationHub(registry)
        await hub.register_agent(agent)  # Now A2A tools are available
        response = await agent.chat("Explain what tools you have access to.")
        print(response)

    if __name__ == "__main__":
        asyncio.run(main())

.. admonition:: Standalone vs Connected
   :class: tip

   - **Standalone** (no hub/registry): Custom tools work; A2A tools gracefully unavailable
   - **Connected** (with hub/registry): Custom tools + A2A tools (search/send/check) active
   - **Gotcha**: Register **before** first ``.chat()`` call to enable A2A tools; workflow initializes once

Using Programmatic Workflows
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For custom message handling and multi-agent coordination, use ``send_message()`` and override ``process_message()``:

.. code-block:: python

    import asyncio
    from agentconnect.prebuilt import AIAgent
    from agentconnect.communication import CommunicationHub
    from agentconnect.core.registry import AgentRegistry
    from agentconnect.core.message import Message
    from agentconnect.core.types import AgentIdentity, MessageType, ModelProvider, ModelName
    import os
    
    async def main():
        registry = AgentRegistry()
        hub = CommunicationHub(registry)
        
        # Create and register agents
        agent = AIAgent(
            agent_id="assistant",
            name="Assistant",
            identity=AgentIdentity.create_key_based(),
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
        await hub.register_agent(agent)
        
        # Send message programmatically
        await agent.send_message(
            receiver_id="other_agent",  # An agent with this ID must be registered with the hub
            content="Please analyze this data",
            message_type=MessageType.REQUEST_COLLABORATION,
        )
        
        # Start processing loop - Receive incoming messages and send responses
        await agent.run()
    
    if __name__ == "__main__":
        asyncio.run(main())

``AIAgent`` inherits ``send_message()`` and ``process_message()`` from :class:`BaseAgent <agentconnect.core.agent.BaseAgent>`. For advanced patterns like overriding ``process_message()`` with ``super()`` interplay, correlation handling, and multi-message replies, see :ref:`overriding_process_message`.

Interactive CLI
^^^^^^^^^^^^^^^

For direct interaction, use :class:`HumanAgent <agentconnect.prebuilt.HumanAgent>` to chat with your ``AIAgent`` via a terminal CLI:

.. code-block:: python

    import asyncio
    from agentconnect.prebuilt import AIAgent, HumanAgent
    
    # Create AIAgent
    ai_agent = AIAgent(...)
    await hub.register_agent(ai_agent)
    task = asyncio.create_task(ai_agent.run())
    
    # Create HumanAgent for CLI interaction
    human = HumanAgent(agent_id="human_01", name="User", identity=AgentIdentity.create_key_based())
    await hub.register_agent(human)
    
    # Start interactive CLI session
    await human.start_interaction(ai_agent)

This launches a terminal interface where you can type messages and see the ``AIAgent``'s responses in real-time. 

**See also:**

- :doc:`human_agent` - Complete HumanAgent guide with CLI features, approval workflows, and multi-agent patterns
- :doc:`../first_agent` - Your first agent example

Built-in A2A Tools
------------------

When connected to a hub and registry, ``AIAgent`` automatically gains three collaboration tools for **Agent Discovery** and **Agent-to-Agent (A2A) Communication**:

- ``search_for_agents``: Semantic search across agent profiles (capabilities, skills, tags etc.) to find collaborators
- ``send_collaboration_request``: Delegate tasks to other agents and await responses
- ``check_collaboration_result``: Retrieve late responses from timed-out requests

These tools are initialized automatically—no manual setup required. For complete documentation including arguments, return values, usage patterns, and examples, see :doc:`../../systems/agent_toolbox`.

Designing Specialist AIAgents
------------------------------

Think of each ``AIAgent`` as a **specialist** with unique skills, capabilities, and tools. Example archetypes:

- **Research Specialist**: Web search + document parsing tools; skills in information synthesis
- **Code Reviewer**: Static analysis + security scanning tools; skills in Python and security

**Creating a specialist:**

.. code-block:: python

    from langchain_core.tools import tool
    from agentconnect.prebuilt import AIAgent
    from agentconnect.core.types import (
        AgentIdentity, AgentProfile, AgentType,
        Capability, Skill, ModelProvider, ModelName
    )
    import os
    
    @tool
    def analyze_code(code: str) -> str:
        """Analyzes code complexity."""
        return "Complexity: Medium, Lines: 150"
    
    specialist = AIAgent(
        agent_id="code_reviewer",
        identity=AgentIdentity.create_key_based(),
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key=os.getenv("OPENAI_API_KEY"),
        personality="meticulous and constructive",  # System prompt (Not exposed in profile, internal only)
        custom_tools=[analyze_code],
        profile=AgentProfile(  # External representation of the agent (exposed to other agents for discovery and collaboration)
            agent_id="code_reviewer",
            agent_type=AgentType.AI,
            name="Code Reviewer",
            summary="Python security and quality expert",
            description="A specialist code reviewer who can review code for bugs and security",
            capabilities=[Capability(name="code_review", description="Reviews code for bugs and security")],
            skills=[Skill(name="Python", description="Expert-level knowledge")],
            tags=["code-review", "python"],
        ),
    )

For multi-agent system patterns and specialist collaboration strategies, see :doc:`../../systems/agent_network_setup`.

Parameters & Configuration
---------------------------

**Full API:** :class:`AIAgent <agentconnect.prebuilt.ai_agent.AIAgent>`

Required Parameters
^^^^^^^^^^^^^^^^^^^

- **agent_id** (*str*): Unique identifier for the agent (should match the ID in the profile).
- **identity** (:class:`AgentIdentity`): Cryptographic identity for signing/verification
- **provider_type** (:class:`ModelProvider`): LLM provider (``OPENAI``, ``ANTHROPIC``, ``GOOGLE``, ``GROQ``)
- **model_name** (:class:`ModelName`): Specific model to use (e.g., ``GPT4O_MINI``, ``CLAUDE_3_5_SONNET``, ``GEMINI2_5_PRO``, ``LLAMA3_70B``)
- **api_key** (*str*): API key for the selected provider (use environment variables in production)

Optional Parameters
^^^^^^^^^^^^^^^^^^^

Agent Definition (External Representation)
""""""""""""""""""""""""""""""""""""""""""

How the agent presents itself for discovery and collaboration:

- **profile** (:class:`AgentProfile`, optional): **Recommended** - Comprehensive profile including name, summary, description, capabilities, skills, tags, version, examples. Provides richer metadata for semantic discovery.
- **name** (*str*, optional): Human-readable name (fallback if not using profile)
- **capabilities** (List[:class:`Capability`], optional): Agent capabilities (fallback if not using profile)

.. admonition:: Profile vs name
   :class: tip

   Use ``profile`` for production systems to enable richer discovery. The ``name`` and ``capabilities`` parameters are legacy fallbacks. See :doc:`../agent_profile_and_capabilities` for complete profile configuration.

**Profile Configuration:**

Capabilities vs Skills: **Capabilities** are specific tasks (e.g., "code_review"); **Skills** are expertise areas (e.g., "Python programming"). Both are searchable during Agent Discovery. See :doc:`../agent_profile_and_capabilities` for complete profile configuration including examples.

Agent Behavior (Internal Operation)
""""""""""""""""""""""""""""""""""""

How the agent operates internally:

- **personality** (*str*, default: "helpful and professional"): Agent's personality for system prompt (**not** part of profile; internal only)
- **interaction_modes** (List[:class:`InteractionMode`], default: [HUMAN_TO_AGENT, AGENT_TO_AGENT]): Supported interaction patterns
- **custom_tools** (List[BaseTool], optional): LangChain tools for extended functionality (appended to built-in tools)

.. note::
   
   The ``personality`` parameter is internal to the agent and used in the system prompt. It is NOT exposed in the ``AgentProfile`` model, which represents the agent's external presentation.

Model Configuration
""""""""""""""""""""

Fine-tune LLM behavior with provider-specific parameters:

- **model_config** (*Dict[str, Any]*, optional): Provider-specific parameters passed directly to the LLM

  .. code-block:: python

      model_config = {
          "temperature": 0.3,      # Lower = more deterministic
          "max_tokens": 1024,      # Maximum response length
          "top_p": 0.95,           # Nucleus sampling
      }

Rate Limiting & Safety
""""""""""""""""""""""

Control token usage and conversation length to manage cost and prevent runaway loops:

- **max_tokens_per_minute** (*int*, default: 70000): Token budget per minute
- **max_tokens_per_hour** (*int*, default: 700000): Token budget per hour
- **max_turns** (*int*, default: 20): Maximum conversation turns before auto-stop

**Effects:** When token budgets are exceeded, the agent enters cooldown and returns ``COOLDOWN`` messages. When ``max_turns`` is reached, the conversation ends gracefully with a ``STOP`` message.

Payment Integration
""""""""""""""""""""

Enable blockchain payment capabilities via Coinbase AgentKit:

- **enable_payments** (*bool*, default: False): Enable payment tools via Coinbase AgentKit
- **wallet_data_dir** (*str | Path*, optional): Custom directory for wallet storage

**Effects:** When enabled, payment tools are automatically added to the agent's toolset. See :doc:`../../payments/agent_payment` for details.

Debugging & Monitoring
""""""""""""""""""""""

- **verbose** (*bool*, default: False): Enable verbose LLM logging
- **external_callbacks** (List[BaseCallbackHandler], optional): LangChain callback handlers

Advanced Usage
--------------

.. _overriding_process_message:

Overriding process_message()
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When overriding ``process_message()`` in ``AIAgent``, you have three patterns depending on how much control you need:

Pattern 1: Use AIAgent + BaseAgent validation (recommended)
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Call ``super().process_message()`` to get both BaseAgent validation (signature verification, cooldown, STOP handling, correlation) AND AIAgent's LLM processing:

.. code-block:: python

    from agentconnect.prebuilt import AIAgent
    from agentconnect.core.message import Message
    
    class CustomAIAgent(AIAgent):
        async def process_message(self, message: Message) -> Message | None:
            # Custom pre-processing
            if message.metadata and message.metadata.get("is_telegram_message"):
                # Handle Telegram-specific logic
                return await self._handle_telegram_message(message)
            
            # Let AIAgent (which calls BaseAgent) handle everything else
            return await super().process_message(message)

Pattern 2: Use only BaseAgent validation, skip AIAgent LLM
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

Call ``BaseAgent.process_message()`` directly to get validation but skip AIAgent's LLM workflow:

.. code-block:: python

    from agentconnect.prebuilt import AIAgent
    from agentconnect.core.message import Message

    class CustomAIAgent(AIAgent):
        async def process_message(self, message: Message) -> Message | None:
            # Get BaseAgent validation (verification, cooldown, correlation)
            base_response = await super(AIAgent, self).process_message(message)
            if base_response:
                return base_response

            # Custom logic without LLM
            if "urgent" in message.content.lower():
                return Message.create(
                    sender_id=self.agent_id,
                    receiver_id=message.sender_id,
                    content="Urgent request acknowledged",
                    sender_identity=self.identity,
                )

            # Optionally call AIAgent LLM for specific cases
            return await super().process_message(message)

Pattern 3: Full manual control (advanced)
"""""""""""""""""""""""""""""""""""""""""

Don't call ``super()`` at all—handle everything yourself:

.. code-block:: python

    from agentconnect.prebuilt import AIAgent
    from agentconnect.core.message import Message
    
    class CustomAIAgent(AIAgent):
        async def process_message(self, message: Message) -> Message | None:
            # You must handle: verification, cooldown, STOP, correlation
            # See BaseAgent "Super vs manual handling" for requirements

            # Access the LangGraph workflow runnable (for advanced usage):
            # self.workflow
            
            # Your custom logic
            return Message.create(...)

**Which pattern to use:**

- **Pattern 1**: Most cases—you want validation + LLM processing + custom routing
- **Pattern 2**: You need validation but want custom logic instead of LLM for some messages
- **Pattern 3**: You need complete control (rare; requires implementing all BaseAgent responsibilities)

For detailed guidance on BaseAgent responsibilities (correlation, multi-message replies, ``send_message()`` usage), see:

- :ref:`Core APIs <core_apis>` - Scroll to "Core APIs" section
- :ref:`Super vs manual handling <super_vs_manual_handling>` - Scroll to "Super vs manual handling" section
- :ref:`Correlation patterns <correlation_patterns>` - Direct link to correlation patterns

Workflow Initialization Nuances
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``AIAgent`` initializes its LangGraph workflow once when:

1. The first ``.chat()`` call is made, OR
2. The first message arrives via ``process_message()``

**Key behaviors:**

- **Connect before first chat**: If you call ``.chat()`` standalone, then connect to hub/registry, the workflow won't auto-rebuild. Solution: register **before** first ``.chat()``, or create a new agent instance.
- **Workflow caching**: The workflow is cached in ``self.workflow`` and reused for all subsequent interactions.
- **Tool availability**: A2A tools are only included if hub + registry are set during workflow initialization.

Custom Tools Best Practices
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When adding custom tools, follow LangChain conventions:

.. code-block:: python

    from langchain_core.tools import tool
    from pydantic import BaseModel, Field
    from agentconnect.prebuilt input AIAgent
    
    class AnalysisInput(BaseModel):
        code: str = Field(description="Code to analyze")
        check_security: bool = Field(default=True, description="Run security checks")
    
    @tool(args_schema=AnalysisInput)
    def analyze_code(code: str, check_security: bool = True) -> str:
        """Analyzes code for complexity and optionally security issues.
        
        Use this when you need to review code quality or find vulnerabilities.
        """
        # Typed inputs help LLM provide correct arguments
        return f"Analysis: {len(code)} lines, security={'checked' if check_security else 'skipped'}"

    agent = AIAgent(
        # ... other params ...
        custom_tools=[analyze_code],
    )

**Tips:**

- Use typed inputs (Pydantic models) for complex tools
- Write clear docstrings—LLMs use these to decide when to call tools

Observability & Monitoring
^^^^^^^^^^^^^^^^^^^^^^^^^^^

AgentConnect provides built-in callbacks for monitoring agent activity. Use :class:`ToolTracerCallbackHandler <agentconnect.utils.callbacks.ToolTracerCallbackHandler>` for detailed tracing:

.. code-block:: python

    from agentconnect.prebuilt import AIAgent
    from agentconnect.utils.callbacks import ToolTracerCallbackHandler
    
    tracer = ToolTracerCallbackHandler(
        agent_id="my_agent",
        print_tool_activity=True,      # Log tool calls
        print_reasoning_steps=True,    # Log LLM reasoning
    )
    
    agent = AIAgent(
        agent_id="my_agent",
        # ... other params ...
        external_callbacks=[tracer],
        # verbose=True,  # Optional: Enable verbose logging
    )

**LangSmith Integration:**

For production monitoring and debugging, integrate with LangSmith. Set environment variables:

.. code-block:: bash

    export LANGSMITH_TRACING=true
    export LANGSMITH_ENDPOINT=https://api.smith.langchain.com
    export LANGSMITH_API_KEY=<your-api-key>
    export LANGSMITH_PROJECT=my_agentconnect_project

See the `LangSmith documentation <https://docs.smith.langchain.com/>`_ for detailed tracing, evaluation, and monitoring capabilities.

Payment Integration
^^^^^^^^^^^^^^^^^^^

Enable Coinbase AgentKit for blockchain payments:

.. code-block:: python

    agent = AIAgent(
        agent_id="service_agent",
        # ... other params ...
        enable_payments=True,  # Adds payment tools
        # wallet_data_dir="path/to/wallets",  # Optional custom wallet storage location
    )

Payment tools are automatically initialized and available to the LLM. For wallet setup, payment workflows, and examples, see :doc:`../../payments/agent_payment`.

Roadmap & Compatibility Notes
------------------------------

The following high-level changes are planned for future releases. Current usage patterns will remain valid, but APIs may be renamed or enhanced:

**Identity (future):**

- DID will become the canonical agent identifier. External APIs will prefer identity-driven references.
- Current ``agent_id`` usage remains valid; migration path will be provided.

**Messaging (future):**

- Move from metadata ``request_id`` / ``response_to`` to Message v2 with first-class ``correlation_id`` and typed payloads.
- Current correlation patterns remain valid; metadata fields may be renamed.

**Hub queues & lifecycle (future):**

- Shift to hub-owned mailboxes with agent pull workers for better scalability and backpressure.
- Registration flow will change to agent-initiated (``agent.register(hub)``); current ``hub.register_agent(agent)`` remains supported during transition.
- The ``run()`` loop will be replaced by worker pulls; agents will drive their own processing.

**Per-hub MCP (future):**

- Collaboration tooling and auth will be hub-owned.
- ``AIAgent`` will obtain MCP access via hub context instead of managing access tokens directly.

These changes aim to improve scalability, security, and developer experience while maintaining backward compatibility during transitions.

Next Steps
----------

Now that you understand ``AIAgent``, explore:

- :doc:`base_agent` - Foundation and custom agent patterns
- :doc:`../../systems/agent_toolbox` - A2A workflows and tool details
- :doc:`../../systems/agent_network_setup` - Multi-agent system architecture
- :doc:`../agent_profile_and_capabilities` - Profile configuration guide
- :doc:`../../payments/agent_payment` - Payment integration
- :doc:`human_agent` - Human-in-the-loop patterns
- :doc:`../../../examples/index` - Complete examples
