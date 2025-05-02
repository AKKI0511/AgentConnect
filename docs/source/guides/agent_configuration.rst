Configuring Your AI Agent
=========================

.. _agent_configuration:

AgentConnect provides a highly configurable ``AIAgent`` class, allowing you to tailor its behavior, capabilities, and resource usage precisely to your needs. This guide covers the key configuration options available when initializing an ``AIAgent``.

Core Agent Identification
-------------------------

These parameters define the agent's basic identity and role:

*   ``agent_id``: A unique string identifier for this agent within the network.
*   ``name``: A human-readable name for the agent.
*   ``identity``: An ``AgentIdentity`` object, crucial for secure communication and verification. See :class:`agentconnect.core.AgentIdentity` for details on creating identities.
*   ``organization_id`` (Optional): An identifier for the organization the agent belongs to, useful for grouping or policy management.

Language Model Selection and Configuration
------------------------------------------

Choose the underlying language model and fine-tune its behavior:

*   ``provider_type``: Selects the AI provider (e.g., ``ModelProvider.OPENAI``, ``ModelProvider.ANTHROPIC``, ``ModelProvider.GOOGLE``, ``ModelProvider.GROQ``).
*   ``model_name``: Specifies the exact model from the chosen provider (e.g., ``ModelName.GPT4O``, ``ModelName.CLAUDE_3_5_SONNET``, ``ModelName.GEMINI1_5_PRO``, ``ModelName.LLAMA3_70B``).
*   ``api_key``: The API key for the selected provider. It's **strongly recommended** to use environment variables (e.g., ``OPENAI_API_KEY``) instead of passing keys directly in code for production environments.
*   ``model_config`` (Optional): A dictionary to pass provider-specific parameters directly to the language model (e.g., ``{"temperature": 0.7, "max_tokens": 512}``). **Note:** The valid parameters depend entirely on the selected provider and model. Consult the provider's documentation for available options.

.. code-block:: python

    from agentconnect.agents import AIAgent
    from agentconnect.core.types import AgentIdentity, ModelProvider, ModelName, InteractionMode

    # Example using OpenAI GPT-4o with custom temperature
    agent_openai = AIAgent(
        agent_id="openai-agent-1",
        name="Creative Writer",
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key="your-openai-api-key", # Better to use os.environ.get("OPENAI_API_KEY")
        identity=AgentIdentity.create_key_based(),
        model_config={"temperature": 0.8},
        # ... other parameters
    )

    # Example using Google Gemini 1.5 Pro
    agent_google = AIAgent(
        agent_id="google-agent-researcher",
        name="Research Assistant",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI1_5_PRO,
        api_key="your-google-api-key", # Better to use os.environ.get("GOOGLE_API_KEY")
        identity=AgentIdentity.create_key_based(),
        # ... other parameters
    )

Agent Behavior and Capabilities
-------------------------------

Define how the agent behaves and what it can do:

*   ``capabilities`` (Optional): A list of ``Capability`` objects describing the agent's skills (e.g., ``Capability(name="summarization", description="Can summarize long texts")``). This helps other agents discover and collaborate effectively.
*   ``personality``: A string describing the agent's desired personality (e.g., "helpful and concise", "formal and detailed", "witty and creative").
*   ``interaction_modes``: A list specifying how the agent can interact (e.g., ``InteractionMode.HUMAN_TO_AGENT``, ``InteractionMode.AGENT_TO_AGENT``).
*   ``memory_type``: Determines the type of memory the agent uses (e.g., ``MemoryType.BUFFER`` for simple short-term memory).
*   ``agent_type``: Specifies the type of workflow the agent will use internally (e.g., "ai" for standard agent, "task_decomposition" for agents that break down complex tasks, or "collaboration_request" for specialized request handling). This influences how the agent processes messages and makes decisions.
*   ``prompt_templates`` (Optional): An instance of ``PromptTemplates`` to customize the system and user prompts used by the agent's underlying workflow.
*   ``prompt_tools`` (Optional): An instance of ``PromptTools`` providing built-in functionalities like agent discovery and communication. Usually managed internally but can be customized.
*   ``custom_tools`` (Optional): A list of custom LangChain ``BaseTool`` or ``StructuredTool`` objects to extend the agent's functionality beyond built-in capabilities.

Resource Management and Control
-------------------------------

Manage the agent's resource consumption:

*   ``max_tokens_per_minute`` / ``max_tokens_per_hour``: Rate limits to control API costs and usage.
*   ``max_turns``: The maximum number of messages exchanged within a single conversation before it automatically ends.
*   ``verbose``: Set to ``True`` for detailed logging of the agent's internal operations, useful for debugging and understanding the agent's decision-making process.

Advanced Features
-----------------

Enable specialized functionalities:

*   ``enable_payments``: Set to ``True`` to enable cryptocurrency payment features via Coinbase AgentKit (requires ``coinbase-agentkit-langchain`` installation and CDP environment setup).
*   ``wallet_data_dir`` (Optional): Specifies a custom directory for storing wallet data if payments are enabled.
*   ``external_callbacks`` (Optional): A list of LangChain ``BaseCallbackHandler`` instances to monitor or interact with the agent's internal processes.
*   ``is_ui_mode``: Indicates if the agent is operating within a UI environment, potentially enabling specific UI-related behaviors or notifications.

Error Handling and Debugging
---------------------------

Configure how your agent handles errors and provides visibility into its operations:

*   ``verbose``: When set to ``True``, enables detailed logging of the agent's internal processes, including tool usage, response generation, and error handling. This is invaluable for debugging complex agent behaviors.
*   ``external_callbacks``: Add custom callback handlers to monitor specific events in the agent's lifecycle. This can help track token usage, log tool calls, or implement custom error handling logic.

The agent also has built-in resilience features:

- Automatic retry logic for failed API calls to the language model provider
- Graceful handling of timeouts during collaboration with other agents
- Proper error responses that maintain conversation context

Real-World Configuration Scenarios
---------------------------------
- **Cost-Effective Task Agent:** Use a cheaper provider (``Groq``/``Llama3``) with strict token limits and basic capabilities for routine tasks.
- **High-Performance Analyst Agent:** Use a premium model (``GPT-4o``, ``Claude 3.5 Sonnet``) with higher token limits, relevant custom tools (e.g., data analysis), and a detailed personality.
- **Multi-Agent System:** Configure agents with distinct providers, models, capabilities, and personalities to handle different parts of a complex workflow (e.g., one agent for research, another for writing, one for user interaction).
- **Debugging:** Enable ``verbose=True`` and add custom ``external_callbacks`` to inspect the agent's decision-making process.

By carefully configuring these parameters, you can create AI agents optimized for specific roles, performance requirements, and cost constraints within your AgentConnect applications.

Comprehensive Configuration Example
-----------------------------------

Here's an example demonstrating how to customize many of the available parameters when initializing an `AIAgent`:

.. code-block:: python

    import os
    from pathlib import Path
    from agentconnect.agents import AIAgent
    from agentconnect.agents.ai_agent import MemoryType
    from agentconnect.core import AgentIdentity
    from agentconnect.core.types import (
        ModelProvider, ModelName, InteractionMode, Capability
    )
    from agentconnect.utils.callbacks import ToolTracerCallbackHandler
    # Assuming you have custom tools and callbacks defined elsewhere
    # from .custom_components import MyCustomTool, MyCallbackHandler
    from langchain_core.tools import tool # Example placeholder
    from langchain_core.callbacks import BaseCallbackHandler # Example placeholder

    # --- Placeholder for custom components ---
    @tool
    def my_calculator_tool(a: int, b: int) -> int:
        """Calculates the sum of two integers."""
        return a + b

    class MyLoggingCallback(BaseCallbackHandler):
        def on_agent_action(self, action, **kwargs) -> None:
            print(f"Agent action: {action.tool} with input {action.tool_input}")

        def on_chain_end(self, outputs, **kwargs) -> None:
            print(f"Chain ended with output: {outputs}")
    # --- End Placeholder ---

    # 1. Define Agent Details
    agent_id = "complex-analyzer-007"
    agent_name = "DeepThink Analyst"
    org_id = "research-division-alpha"

    # 2. Setup Identity
    # Load from existing keys or create new ones
    identity = AgentIdentity.create_key_based()

    # 3. Choose Provider and Model
    provider = ModelProvider.GOOGLE
    model = ModelName.GEMINI2_FLASH  # Available in the ModelName enum
    # Recommended: Use environment variable for API key
    api_key = os.environ.get("GOOGLE_API_KEY", "fallback-key-if-not-set")

    # 4. Define Capabilities
    capabilities = [
        Capability(name="financial_data_analysis", description="Analyzes stock market data and trends."),
        Capability(name="report_generation", description="Generates detailed financial reports."),
    ]

    # 5. Set Personality and Interactions
    personality = "A meticulous and insightful financial analyst providing data-driven conclusions."
    interaction_modes = [InteractionMode.AGENT_TO_AGENT] # Only interacts with other agents

    # 6. Configure Model Parameters
    # Note: Available parameters depend on the specific provider
    model_config = {
        "temperature": 0.2, # More deterministic output
        "max_tokens": 2048, # Allow longer responses
        # Other parameters vary by provider - check documentation
    }

    # 7. Define Custom Tools and Callbacks
    custom_tools = [my_calculator_tool] # Add your custom tools
    external_callbacks = [ToolTracerCallbackHandler(agent_id=agent_id)] # Add your custom callbacks

    # 8. Set Resource Limits
    max_tokens_min = 50000
    max_tokens_hour = 500000
    max_turns_per_convo = 15

    # 9. Configure Memory and Workflow
    memory_type = MemoryType.BUFFER # Or other types like SUMMARY
    agent_type = "ai" # Specify a specific agent type if needed

    # 10. Enable Advanced Features (Optional)
    enable_payments = False # Set to True if AgentKit is configured
    verbose_logging = False  # Enable for debugging
    ui_mode = False
    wallet_dir = Path("./agent_wallet_data") # Custom wallet data path

    # 11. Initialize the AIAgent
    fully_customized_agent = AIAgent(
        agent_id=agent_id,
        name=agent_name,
        provider_type=provider,
        model_name=model,
        api_key=api_key,
        identity=identity,
        capabilities=capabilities,
        personality=personality,
        organization_id=org_id,
        interaction_modes=interaction_modes,
        max_tokens_per_minute=max_tokens_min,
        max_tokens_per_hour=max_tokens_hour,
        max_turns=max_turns_per_convo,
        is_ui_mode=ui_mode,
        memory_type=memory_type,
        prompt_tools=None, # Usually let AgentConnect manage this
        prompt_templates=None, # Can provide custom PromptTemplates instance here
        custom_tools=custom_tools,
        agent_type=agent_type,
        enable_payments=enable_payments,
        verbose=verbose_logging, # Pass the flag here for internal verbosity
        wallet_data_dir=wallet_dir,
        external_callbacks=external_callbacks,
        model_config=model_config,
    )

    print(f"Successfully initialized agent: {fully_customized_agent.name}")
    # Now you can register and use this agent...

Using an Agent Standalone (Direct Chat)
---------------------------------------

For simpler use cases or testing, you might want to interact with an AI agent directly without setting up the full `CommunicationHub` and `AgentRegistry`. The `AIAgent` provides an `async chat()` method for this purpose.

.. code-block:: python

    import asyncio

    async def main():
        # Assume 'fully_customized_agent' is initialized as shown above
        # Ensure API keys are set as environment variables for this example

        print("Starting standalone chat with agent...")
        print("Type 'exit' to quit.")

        conversation_history_id = "my_test_chat_session"

        while True:
            user_query = input("You: ")
            if user_query.lower() == 'exit':
                break

            try:
                # Call the chat method directly
                response = await fully_customized_agent.chat(
                    query=user_query,
                    conversation_id=conversation_history_id # Maintains context
                )
                print(f"Agent: {response}")
            except Exception as e:
                print(f"An error occurred: {e}")
                # Consider adding retry logic or breaking the loop

    # Example of how to run the async main function
    # In a real application, you would use asyncio.run(main())
    # For demonstration purposes:
    # if __name__ == "__main__":
    #     asyncio.run(main())

The ``chat()`` method handles:

- Initializing the agent's workflow automatically if needed
- Managing conversation context through the ``conversation_id`` parameter
- Providing a simple interface for direct agent interaction

This approach is perfect for prototyping, debugging your agent configuration, or creating standalone applications that don't require multi-agent functionality.

Next Steps
----------

Once you've configured your agent, you'll typically want to:

- Register it with the ``AgentRegistry`` and ``CommunicationHub`` to enable collaboration (see :doc:`multi_agent_setup` for details)
- Add it to a multi-agent system where it can discover and interact with other agents (see :doc:`collaborative_workflows`)
- Implement specific conversational patterns for your use case (see :doc:`human_in_the_loop` for interactive scenarios)
