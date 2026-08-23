Local Discovery
===============

.. _discovery_registry_local:

Prerequisites
-------------

Complete :doc:`../../../installation` before starting. Read :doc:`../../core_concepts` for the mental model and :doc:`../agent_profile_and_capabilities` to understand how agent profiles shape discovery.

What Is Local Discovery
------------------------

Local discovery is how agents in the same process find each other by capability. Register your agents with the hub once, and any agent in the system can search for collaborators using a capability name or a plain text description. No registry server, no database, no network calls.

.. admonition:: At a glance
   :class: tip

   - Register agents via ``hub.register_agent(agent)``. The hub handles the rest.
   - Search by exact capability name or by describing what you need in natural language.
   - Configure storage and embedding behavior via ``agentconnect.yaml``.
   - All registrations are held in memory for the lifetime of the process.

When To Use It
--------------

Use local discovery when all your agents run in the same process. It is the right choice for prototypes, tests, single-application multi-agent systems, and local development.

Use :doc:`discovery_registry_remote` when agents span multiple processes or machines, or when you need a shared registry that outlives individual process restarts.

Registering Agents
------------------

Pass your agent to ``hub.register_agent()``. The hub reads the agent's profile (name, capabilities, skills, tags) and makes it immediately findable by capability name and semantically searchable by description.

.. code-block:: python

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
        ModelName,
        ModelProvider,
        Skill,
    )

    async def main():
        load_dotenv()

        registry = AgentRegistry()
        hub = CommunicationHub(registry)

        profile = AgentProfile(
            agent_id="sql-agent-001",
            agent_type=AgentType.AI,
            name="SQL Query Agent",
            summary="Converts natural language questions into SQL SELECT queries for PostgreSQL.",
            capabilities=[
                Capability(
                    name="natural_language_to_sql",
                    description=(
                        "Converts a natural language question into a SQL SELECT query. "
                        "Supports JOINs, aggregations, CTEs, and window functions."
                    ),
                ),
            ],
            skills=[
                Skill(name="PostgreSQL", description="PostgreSQL 14+ dialect and internals"),
            ],
            tags=["sql", "database", "postgresql"],
            default_input_modes=["text"],
            default_output_modes=["text", "application/json"],
        )

        agent = AIAgent(
            agent_id=profile.agent_id,
            identity=AgentIdentity.create_key_based(),
            profile=profile,
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O,
            api_key=os.getenv("OPENAI_API_KEY"),
        )

        await hub.register_agent(agent)

    asyncio.run(main())

To remove an agent from discovery when you are done:

.. code-block:: python

    await hub.unregister_agent("sql-agent-001")

.. admonition:: Profile quality determines discoverability
   :class: important

   The richer and more precise your profile's ``capabilities``, ``skills``, ``summary``, and ``tags`` are, the better other agents find yours through semantic search. See :doc:`../agent_profile_and_capabilities` for guidance on writing effective profiles.

Registering Without a Hub
--------------------------

The registry can also be used on its own, independent of the hub and messaging layer. This is useful when building service directories, writing integration tests with mock agents, or integrating the registry into a custom framework that does not use the hub at all.

.. code-block:: python

    import asyncio
    from agentconnect.core.registry import AgentRegistry, AgentRegistration
    from agentconnect.core.types import (
        AgentIdentity,
        AgentType,
        Capability,
        InteractionMode,
        Skill,
    )

    async def main():
        registry = AgentRegistry()

        await registry.register(AgentRegistration(
            agent_id="data-analyst-001",
            agent_type=AgentType.AI,
            interaction_modes=[InteractionMode.AGENT_TO_AGENT],
            identity=AgentIdentity.create_key_based(),
            name="Data Analyst",
            summary="Analyzes structured datasets and produces statistical summaries.",
            capabilities=[
                Capability(
                    name="statistical_analysis",
                    description=(
                        "Computes descriptive statistics, correlations, and distributions "
                        "from tabular data. Accepts CSV or JSON input."
                    ),
                ),
            ],
            skills=[Skill(name="Pandas", description="Python data analysis with Pandas and NumPy")],
            tags=["data", "analysis", "statistics"],
        ))

        results = await registry.get_by_capability_semantic(
            capability_description="analyze data and produce summaries",
            limit=3,
        )
        for agent_reg, score in results:
            print(f"{agent_reg.name} ({score:.3f}): {agent_reg.summary}")

    asyncio.run(main())

To update a registration or remove it later:

.. code-block:: python

    # Update capabilities or profile fields in-place
    await registry.update_registration(
        "data-analyst-001",
        {"tags": ["data", "analysis", "statistics", "ml"], "version": "1.1.0"},
    )

    # Remove from registry and clear its vector embeddings
    await registry.unregister("data-analyst-001")

Finding Agents
--------------

By Capability Name
^^^^^^^^^^^^^^^^^^^

Exact match against registered capability names. Fast and deterministic. If no exact match is found and the semantic search stack is ready, it automatically falls back to a semantic search using the same string as the query:

.. code-block:: python

    agents = await registry.get_by_capability("natural_language_to_sql")
    for agent in agents:
        print(f"{agent.name}: {agent.summary}")

Full parameter reference: :meth:`AgentRegistry.get_by_capability <agentconnect.core.registry.AgentRegistry.get_by_capability>`.

By Description (Semantic Search)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Pass any natural language description. The registry encodes it as an embedding and returns ranked matches from the vector index:

.. code-block:: python

    results = await registry.get_by_capability_semantic(
        capability_description="convert natural language questions to database queries",
        limit=5,
        similarity_threshold=0.3,
    )

    for agent_reg, score in results:
        print(f"{agent_reg.name} ({score:.3f}): {agent_reg.summary}")

Full parameter reference: :meth:`AgentRegistry.get_by_capability_semantic <agentconnect.core.registry.AgentRegistry.get_by_capability_semantic>`.

**Narrowing results with filters**

Add a ``filters`` dict to restrict the candidate set before semantic scoring. All filter values are exact matches:

.. code-block:: python

    results = await registry.get_by_capability_semantic(
        capability_description="data transformation and reporting",
        limit=5,
        similarity_threshold=0.2,
        filters={
            "tags": ["data", "etl"],            # agent must have at least one of these tags
            "organization": "acme-corp",         # agent's organization must match exactly
            "default_output_modes": ["application/json"],
        },
    )

Supported filter keys: ``tags``, ``organization``, ``developer``, ``default_input_modes``, ``default_output_modes``, ``auth_schemes``.

Other Lookups
^^^^^^^^^^^^^

Use these when you already know a structural attribute and do not need semantic matching:

.. code-block:: python

    from agentconnect.core.types import InteractionMode

    # All agents in an organization
    org_agents = await registry.get_by_organization("acme-corp")

    # All agents supporting a specific interaction mode
    a2a_agents = await registry.get_by_interaction_mode(InteractionMode.AGENT_TO_AGENT)

    # All agents whose identity passed DID verification
    verified = await registry.get_verified_agents()

    # Every registered agent
    all_agents = await registry.get_all_agents()

    # All unique capability names currently registered
    capability_names = await registry.get_all_capabilities()

    # Single agent by id
    reg = await registry.get_registration("sql-agent-001")

Configuration
-------------

.. note::

   ``agentconnect.yaml`` sets the defaults that apply when ``AgentRegistry()`` is instantiated with no arguments. The file is read once at process startup; changes require a restart. Settings in the YAML do not require any changes to your Python code; swapping the deployment mode or embedding model is purely a config file change.

   If you have not used ``agentconnect.yaml`` before, read :doc:`../../configuration/sdk_configuration` first. It explains the file format, where to place it, and how precedence works.

Deployment Mode
^^^^^^^^^^^^^^^

The main choice is where the embedding vectors are stored. Drop an ``agentconnect.yaml`` file in your project root with one of the following ``registry.vector_search.deployment`` blocks:

.. code-block:: yaml

    registry:
      vector_search:
        deployment:
          type: "in_memory"        # default: no persistence, vectors reset on restart

.. code-block:: yaml

    registry:
      vector_search:
        deployment:
          type: "local_file"
          path: "./qdrant_db"      # embedding index persists to disk between restarts

.. code-block:: yaml

    registry:
      vector_search:
        deployment:
          type: "remote"
          url: "http://localhost:6333"    # set QDRANT_API_KEY env var for Qdrant Cloud

.. admonition:: What persists and what does not
   :class: important

   All three modes hold agent registration records (names, profiles, capabilities) in the running process's memory. They are gone on restart regardless of deployment mode. The deployment mode only controls where the **embedding vectors** are stored. With ``local_file`` or ``remote``, the embedding index survives restarts and does not need to rebuild; with ``in_memory``, vectors are rebuilt each run.

   For a persistent shared registry, use :doc:`discovery_registry_remote`.

Advanced Configuration
^^^^^^^^^^^^^^^^^^^^^^

The full YAML block for the registry covers the embedding model path, storage directories, and Qdrant tuning knobs:

.. code-block:: yaml

    registry:
      vector_search:
        model_name: "sentence-transformers/all-mpnet-base-v2"
        cache_folder: "./.cache/huggingface/embeddings"
        vector_store_path: "./.cache/vector_stores"
        deployment:
          type: "local_file"
          path: "./qdrant_db"
        advanced:
          use_quantization: true     # INT8 quantization — 4x storage reduction, <1% accuracy loss
          batch_size: 50             # lower if you see memory spikes during bulk registration
          timeout: 60                # Qdrant client timeout in seconds
          prefer_grpc: false         # use gRPC instead of HTTP (remote mode only)
          vectors_on_disk: false     # store vectors on disk instead of RAM
          index_on_disk: false       # store HNSW index on disk instead of RAM

For the full list of knobs and what each one does, see the `Registry README on GitHub <https://github.com/AKKI0511/AgentConnect/blob/main/agentconnect/core/registry/README.md>`_.

In-code Configuration
^^^^^^^^^^^^^^^^^^^^^

To override configuration at runtime without touching ``agentconnect.yaml``, pass a :class:`VectorSearchSettings <agentconnect.config.models.VectorSearchSettings>` object directly:

.. code-block:: python

    from agentconnect.config.models import VectorSearchSettings
    from agentconnect.core.registry import AgentRegistry

    registry = AgentRegistry(
        vector_search_config=VectorSearchSettings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",   # faster, smaller model
            deployment={"type": "local_file", "path": "./my_qdrant_db"},
        )
    )

Runtime config takes precedence over ``agentconnect.yaml``. Use it for tests, multi-tenant scenarios, or any situation where you need different registry configurations in the same process.

Using Discovery via Tools
--------------------------

Most agents do not call the registry directly. They interact with it through tools that wrap search and return structured results back to the agent's reasoning loop. There are three patterns, ordered from least to most custom.

Built-in Collaboration Tools
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``AIAgent`` receives three tools automatically when registered with a hub:

- ``search_for_agents`` — semantic search across all registered agent profiles, with tag filtering and configurable result detail
- ``send_collaboration_request`` — sends a task to a found agent and waits for the response
- ``check_collaboration_result`` — polls for a late response from a previous request that timed out

These tools let your AI agent discover collaborators and delegate work without any explicit registry calls in your code. The agent's LLM uses them during its reasoning and decides when and who to delegate to. See :doc:`../../systems/agent_toolbox` for how these tools fit together, what inputs they accept, and how the collaboration loop works.

Discovery MCP Server
^^^^^^^^^^^^^^^^^^^^^

The registry can be exposed as an MCP server so that Claude Desktop, Cursor, or any MCP-compatible client can search your registered agents by natural language query:

.. code-block:: bash

    agentconnect mcp start

Once running, MCP clients can query the registry without any Python code on the client side. See :doc:`../../integrations/mcp/discovery_mcp` for setup, configuration, and how to connect it to your MCP client.

Custom Search Tools
^^^^^^^^^^^^^^^^^^^^

The :mod:`agentconnect.core.registry.search` module provides typed input/output schemas on top of the raw registry API:

- :class:`AgentSearchInput <agentconnect.core.registry.search.AgentSearchInput>` for query parameters
- :func:`populate_search_result_item <agentconnect.core.registry.search.populate_search_result_item>` to convert raw ``(AgentRegistration, score)`` pairs into structured results
- :class:`AgentSearchOutput <agentconnect.core.registry.search.AgentSearchOutput>` for compact, token-efficient JSON serialization

Two primary patterns: using the registry as a RAG source to enrich LLM prompts, and wrapping it as a tool for a different AI framework.

**RAG-style context injection**

Any agent registered via ``hub.register_agent()`` gets ``self.registry`` set automatically. A coordinator or router agent can query the registry for a domain it cares about and inject the results into its LLM system prompt before inference:

.. code-block:: python

    from agentconnect.core.agent import BaseAgent
    from agentconnect.core.message import Message
    from agentconnect.core.registry.search import (
        AgentSearchInput,
        AgentSearchOutput,
        populate_search_result_item,
    )

    class CoordinatorAgent(BaseAgent):

        async def _get_network_context(self, domain: str) -> str:
            """Query the registry for a capability domain and return compact JSON context."""
            search_input = AgentSearchInput(query=domain, top_k=5, output_detail="capabilities")
            raw = await self.registry.get_by_capability_semantic(
                capability_description=search_input.query,
                limit=search_input.top_k,
                similarity_threshold=search_input.strictness,
            )
            items = [
                populate_search_result_item(reg, score, search_input.output_detail)
                for reg, score in raw
            ]
            return str(AgentSearchOutput(message=f"Found {len(items)} agents.", results=items))

        async def process_message(self, message: Message) -> Message | None:
            # Query for agents relevant to this coordinator's domain
            context = await self._get_network_context("data analysis and transformation")
            system_prompt = (
                f"You are a coordinator. Available specialized agents:\n{context}\n\n"
                "Route the task to the most appropriate agent listed above."
            )
            # Pass system_prompt and message.content to your LLM call
            ...

:class:`AgentSearchOutput.__str__() <agentconnect.core.registry.search.AgentSearchOutput>` returns compact JSON ready to paste into a prompt. Use ``output_detail="summary"`` for routing decisions and ``"capabilities"`` when the LLM needs the full capability list to choose correctly.

**Building a search tool for a different framework**

If you are building an agent with Google ADK, OpenAI Agents SDK, or another framework, define the tool function inside your ``BaseAgent`` subclass and close over ``self.registry``. The function's type hints and docstring are used by the framework to generate the tool schema automatically:

.. code-block:: python

    from google.adk.agents import Agent
    from agentconnect.core.agent import BaseAgent
    from agentconnect.core.registry.search import (
        AgentSearchInput,
        AgentSearchOutput,
        populate_search_result_item,
    )

    class MyADKAgent(BaseAgent):

        def _make_search_tool(self):
            """Return a plain async function; Google ADK auto-wraps it as a FunctionTool."""

            async def search_agents(query: str, top_k: int = 5) -> dict:
                """Search AgentConnect agents by capability.

                Args:
                    query: Natural language description of the capability needed.
                    top_k: Maximum number of results to return.
                """
                search_input = AgentSearchInput(query=query, top_k=top_k)
                raw = await self.registry.get_by_capability_semantic(
                    capability_description=search_input.query,
                    limit=search_input.top_k,
                    similarity_threshold=search_input.strictness,
                )
                items = [
                    populate_search_result_item(reg, score, search_input.output_detail)
                    for reg, score in raw
                ]
                output = AgentSearchOutput(
                    message=f"Found {len(items)} agents.", results=items
                )
                return output.model_dump(exclude_none=True)

            return search_agents

        async def start(self):
            adk_agent = Agent(
                name="my-adk-agent",
                model="gemini-2.0-flash",
                tools=[self._make_search_tool()],  # self.registry is available after hub.register_agent()
            )
            ...

Troubleshooting
---------------

**Semantic search returns no results**

Lower ``similarity_threshold`` toward ``0.05``. If your query is phrased very differently from the capability descriptions in the profile, even a threshold of ``0.1`` may filter everything out. Also check that capability descriptions in your profiles are detailed; a single-word capability like ``"query"`` is hard to match semantically.

**Agent not found by exact capability name**

The capability name index is case-sensitive. Confirm the ``name`` field in your ``Capability`` objects exactly matches what you pass to ``get_by_capability()``. Also confirm all searches use the same ``registry`` instance; a second ``AgentRegistry()`` is a separate, empty registry.

**Registrations gone after restart**

Expected. Re-run your startup code to re-register agents. If you need registrations to persist across restarts, you need the remote registry: :doc:`discovery_registry_remote`.

Next Steps
----------

- :doc:`discovery_registry_remote` — scale discovery across processes and machines
- :doc:`../../configuration/sdk_configuration` — full ``agentconnect.yaml`` reference
- :doc:`../../systems/agent_network_setup` — build a complete multi-agent system with local discovery
- :doc:`../../systems/agent_toolbox` — enable agents to find and call each other autonomously
- :doc:`../../integrations/mcp/discovery_mcp` — expose local discovery to MCP-compatible clients (Cursor, Claude Desktop)
- `Registry README <https://github.com/AKKI0511/AgentConnect/blob/main/agentconnect/core/registry/README.md>`_ — internals, advanced configuration, and dependency setup
