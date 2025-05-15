Configuring Your AI Agent
=========================

.. _agent_configuration:

AgentConnect provides a highly configurable :class:`AIAgent <agentconnect.agents.AIAgent>` class, allowing you to tailor its behavior, capabilities, and resource usage precisely to your needs. This guide covers the key configuration options available when initializing an ``AIAgent``.

Introduction to AIAgent Configuration
------------------------------------

The ``AIAgent`` class is the core building block for creating autonomous AI agents in the AgentConnect framework. Configuring an ``AIAgent`` involves defining two key aspects:

1. **External Representation**: How the agent presents itself to other agents and humans for discovery and interaction (identity, capabilities, skills, etc.)
2. **Internal Behavior**: How the agent operates internally (LLM provider, tools, personality, resource limits, etc.)

The recommended approach for configuring an ``AIAgent`` is to use a combination of the ``profile`` parameter (for external representation) and direct parameters (for internal behavior).

Recommended: Using AgentProfile for Agent Definition
--------------------------------------------------

The **recommended method** for defining an ``AIAgent``'s core identity, purpose, and discoverable features is through the ``profile: AgentProfile`` parameter in its constructor. :class:`AgentProfile <agentconnect.core.types.AgentProfile>` consolidates and expands upon previously individual parameters like ``name``, ``capabilities`` into a single, structured Pydantic model.

This approach provides several benefits:

- Better organization of agent metadata
- Richer metadata for improved semantic discovery via the ``AgentRegistry``
- Clearer separation of an agent's definition from its runtime behavior
- More comprehensive agent descriptions for better collaboration

Here's an illustrative example of creating a research assistant agent using ``AgentProfile``:

.. code-block:: python

    import os
    from agentconnect.agents import AIAgent
    from agentconnect.core.types import (
        AgentProfile, AgentType, Capability, Skill, 
        ModelProvider, ModelName, AgentIdentity, InteractionMode
    )

    # Create a detailed AgentProfile for a research assistant
    research_assistant_profile = AgentProfile(
        agent_id="research_assistant_001",
        agent_type=AgentType.AI,
        name="Research Copilot",
        summary="AI assistant for conducting research, finding papers, and summarizing information.",
        description="This agent specializes in academic research. It can search online databases, retrieve scientific papers, analyze text, and provide concise summaries. It's equipped with tools for web browsing and document processing.",
        capabilities=[
            Capability(
                name="search_academic_papers", 
                description="Searches PubMed, Google Scholar and other academic databases for papers.",
                input_schema={"query": "string", "max_results": "integer"},
                output_schema={"papers": "list"}
            ),
            Capability(
                name="summarize_document", 
                description="Provides a summary of a given text document.",
            ),
            Capability(
                name="extract_key_information", 
                description="Extracts key entities and facts from text.",
            )
        ],
        skills=[
            Skill(name="NLP", description="Natural Language Processing"),
            Skill(name="Information Retrieval", description="Efficiently finding relevant information"),
            Skill(name="Academic Writing", description="Understanding structure of academic papers")
        ],
        tags=["research", "academic", "summary", "nlp", "papers"],
        version="1.2.0",
        examples=[
            "Find recent papers about quantum computing advancements",
            "Summarize this research paper on climate change",
            "Extract key findings from this medical study"
        ]
    )

    # Use the profile when initializing the AIAgent
    research_agent = AIAgent(
        agent_id=research_assistant_profile.agent_id,  # Use the ID from the profile
        identity=AgentIdentity.create_key_based(),     # Cryptographic identity
        provider_type=ModelProvider.OPENAI,            # LLM provider
        model_name=ModelName.GPT4O,                    # Specific model
        api_key=os.getenv("OPENAI_API_KEY"),           # API key from environment
        profile=research_assistant_profile,            # Pass the complete profile
        personality="You are a meticulous and insightful research assistant. Always cite your sources.",
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT, InteractionMode.AGENT_TO_AGENT],
        # ... other AIAgent-specific settings as needed
    )

.. note::

    The ``personality`` parameter is not exposed in the ``AgentProfile`` model. It is a parameter of the ``AIAgent`` class that sets the personality of the agent and is passed in the system prompt.

Notice that the ``AgentProfile`` contains all the metadata about what the agent is and what it can do, while the ``AIAgent`` constructor still requires parameters that define how it operates (provider, model, API key, etc.).

Core Agent Identification
-------------------------

While most identification is now handled by the ``AgentProfile``, these parameters are still required:

*   ``agent_id``: A unique string identifier for this agent within the network (should match the ID in the profile).
*   ``identity``: An ``AgentIdentity`` object, crucial for secure communication and verification. See :class:`AgentIdentity <agentconnect.core.AgentIdentity>` for details on creating identities.

Language Model Selection and Configuration
------------------------------------------

Choose the underlying language model and fine-tune its behavior:

*   ``provider_type``: Selects the AI provider (e.g., ``ModelProvider.OPENAI``, ``ModelProvider.ANTHROPIC``, ``ModelProvider.GOOGLE``, ``ModelProvider.GROQ``).
*   ``model_name``: Specifies the exact model from the chosen provider (e.g., ``ModelName.GPT4O``, ``ModelName.CLAUDE_3_5_SONNET``, ``ModelName.GEMINI1_5_PRO``, ``ModelName.LLAMA3_70B``).
*   ``api_key``: The API key for the selected provider. It's **strongly recommended** to use environment variables (e.g., ``OPENAI_API_KEY``) instead of passing keys directly in code for production environments.
*   ``model_config`` (Optional): A dictionary to pass provider-specific parameters directly to the language model (e.g., ``{"temperature": 0.7, "max_tokens": 512}``). **Note:** The valid parameters depend entirely on the selected provider and model. Consult the provider's documentation for available options.

.. code-block:: python

    # Example of model configuration
    model_config = {
        "temperature": 0.3,        # Lower temperature for more deterministic responses
        "max_tokens": 1024,        # Maximum response length
        "top_p": 0.95              # Nucleus sampling parameter
    }
    
    # Use in AIAgent initialization
    agent = AIAgent(
        # ... other parameters
        provider_type=ModelProvider.ANTHROPIC,
        model_name=ModelName.CLAUDE_3_5_SONNET,
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model_config=model_config,
        # ... other parameters
    )

Configuring AIAgent Behavior (Internal Settings)
----------------------------------------------

These parameters define the agent's internal workings and are not part of the ``AgentProfile``:

**Agent Persona**

*   ``personality``: A string describing the agent's desired personality (e.g., "helpful and concise", "formal and detailed"). This is used in the system prompt and affects how the agent responds.

.. code-block:: python

    # Example personality string
    personality = "You are a friendly, patient tutor who explains complex concepts in simple terms. Use analogies when helpful and always check if the user understands before moving on."

**Interaction & Resource Management**

*   ``interaction_modes``: A list specifying how the agent can interact (e.g., ``InteractionMode.HUMAN_TO_AGENT``, ``InteractionMode.AGENT_TO_AGENT``).
*   ``max_tokens_per_minute`` / ``max_tokens_per_hour``: Rate limits to control API costs and usage.
*   ``max_turns``: The maximum number of messages exchanged within a single conversation before it automatically ends.

**Memory & Tools**

*   ``memory_type``: Determines the type of memory the agent uses (e.g., ``MemoryType.BUFFER`` for simple short-term memory).
*   ``agent_type``: Specifies the type of workflow the agent will use internally (e.g., "ai" for standard agent, "task_decomposition" for agents that break down complex tasks).
*   ``prompt_templates`` (Optional): An instance of ``PromptTemplates`` to customize the system and user prompts.
*   ``prompt_tools`` (Optional): An instance of ``PromptTools`` providing built-in functionalities like agent discovery and communication.
*   ``custom_tools`` (Optional): A list of custom LangChain ``BaseTool`` or ``StructuredTool`` objects to extend the agent's functionality.

**Debugging & Advanced Features**

*   ``verbose``: Set to ``True`` for detailed logging of the agent's internal operations.
*   ``enable_payments``: Set to ``True`` to enable cryptocurrency payment features via Coinbase AgentKit.
*   ``wallet_data_dir`` (Optional): Specifies a custom directory for storing wallet data if payments are enabled.
*   ``external_callbacks`` (Optional): A list of LangChain ``BaseCallbackHandler`` instances for monitoring.
*   ``is_ui_mode``: Indicates if the agent is operating within a UI environment.

Practical Example: Research Assistant with Custom Configuration
-------------------------------------------------------------

Here's a complete example that combines a well-defined ``AgentProfile`` with specific behavioral settings to create a research assistant agent:

.. code-block:: python

    import os
    import asyncio
    from pathlib import Path
    from agentconnect.agents import AIAgent
    from agentconnect.agents.ai_agent import MemoryType
    from agentconnect.core.types import (
        AgentProfile, AgentType, Capability, Skill,
        AgentIdentity, ModelProvider, ModelName, InteractionMode
    )
    from langchain_community.tools.tavily_search import TavilySearchResults
    from langchain_community.tools.arxiv import ArxivQueryRun
    
    # 1. Create the AgentProfile (external representation)
    research_profile = AgentProfile(
        agent_id="research_copilot_007",
        agent_type=AgentType.AI,
        name="ResearchCopilot",
        summary="AI assistant for academic research and paper analysis",
        description="A specialized research assistant that can search academic databases, analyze papers, and provide summaries and insights. Ideal for researchers, students, and academics.",
        capabilities=[
            Capability(
                name="academic_search",
                description="Search academic databases for relevant papers",
                input_schema={"query": "string", "max_results": "integer"},
                output_schema={"papers": "list"}
            ),
            Capability(
                name="paper_summary",
                description="Generate concise summaries of academic papers",
                input_schema={"paper_text": "string", "focus_area": "string"},
                output_schema={"summary": "string", "key_points": "list"}
            )
        ],
        skills=[
            Skill(name="literature_review", description="Comprehensive literature review"),
            Skill(name="academic_writing", description="Academic writing and formatting"),
            Skill(name="data_analysis", description="Basic analysis of research data")
        ],
        tags=["research", "academic", "papers", "analysis", "education"],
        version="1.0.0",
        examples=[
            "Find recent papers on machine learning for climate science",
            "Summarize this paper on quantum computing algorithms",
            "What are the key findings in recent CRISPR research?"
        ]
    )
    
    # 2. Set up research tools
    research_tools = []
    if os.getenv("TAVILY_API_KEY"):
        research_tools.append(TavilySearchResults(
            max_results=5,
            include_raw_content=True
        ))
    research_tools.append(ArxivQueryRun())
    
    # 3. Configure model settings for research quality
    model_config = {
        "temperature": 0.2,  # More deterministic for research accuracy
        "max_tokens": 2048,  # Allow longer responses for detailed analysis
    }
    
    # 4. Create the research agent with both profile and behavior settings
    research_agent = AIAgent(
        # Core identification
        agent_id=research_profile.agent_id,
        identity=AgentIdentity.create_key_based(),
        
        # LLM configuration
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key=os.getenv("OPENAI_API_KEY"),
        model_config=model_config,
        
        # External representation
        profile=research_profile,
        
        # Internal behavior
        personality="You are a meticulous academic researcher with expertise across multiple disciplines. You provide balanced, evidence-based responses with proper citations. You're careful to distinguish between established facts and emerging theories.",
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT, InteractionMode.AGENT_TO_AGENT],
        custom_tools=research_tools,
        memory_type=MemoryType.BUFFER,
        max_tokens_per_minute=60000,
        max_tokens_per_hour=600000,
        max_turns=25,
        verbose=True  # Enable for debugging
    )
    
    # Example usage
    async def demo():
        response = await research_agent.chat(
            "What are the latest developments in fusion energy research?",
            conversation_id="research_session_001"
        )
        print(f"Research Agent: {response}")
    
    # asyncio.run(demo())  # Uncomment to run the demo

This example demonstrates:

1. A comprehensive ``AgentProfile`` that clearly defines what the agent is and what it can do
2. Custom tools specific to the research domain
3. Model configuration optimized for research tasks
4. Personality and behavioral settings appropriate for academic research

Real-World Configuration Scenarios
---------------------------------
- **Cost-Effective Task Agent:** Use a cheaper provider (``Groq``/``Llama3``) with strict token limits and basic capabilities for routine tasks.
- **High-Performance Analyst Agent:** Use a premium model (``GPT-4o``, ``Claude 3.7 Sonnet``) with higher token limits, relevant custom tools (e.g., data analysis), and a detailed personality.
- **Multi-Agent System:** Configure agents with distinct providers, models, capabilities, and personalities to handle different parts of a complex workflow (e.g., one agent for research, another for writing, one for user interaction).
- **Debugging:** Enable ``verbose=True`` and add custom ``external_callbacks`` to inspect the agent's decision-making process.

By carefully configuring these parameters, you can create AI agents optimized for specific roles, performance requirements, and cost constraints within your AgentConnect applications.

Using an Agent Standalone (Direct Chat)
---------------------------------------

For simpler use cases or testing, you might want to interact with an AI agent directly without setting up the full `CommunicationHub` and `AgentRegistry`. The `AIAgent` provides an `async chat()` method for this purpose.

.. code-block:: python

    import asyncio

    async def main():
        # Assume 'research_agent' is initialized as shown above
        # Ensure API keys are set as environment variables for this example

        print("Starting standalone chat with research agent...")
        print("Type 'exit' to quit.")

        conversation_history_id = "my_research_session"

        while True:
            user_query = input("You: ")
            if user_query.lower() == 'exit':
                break

            try:
                # Call the chat method directly
                response = await research_agent.chat(
                    query=user_query,
                    conversation_id=conversation_history_id # Maintains context
                )
                print(f"Research Agent: {response}")
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
