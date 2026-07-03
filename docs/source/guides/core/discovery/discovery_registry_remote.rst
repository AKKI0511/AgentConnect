Remote Discovery
================

.. _discovery_registry_remote:

Prerequisites
-------------

Complete :doc:`../../../installation` before starting. Read :doc:`../../core_concepts` for the mental model and :doc:`../agent_profile_and_capabilities` to understand how agent profiles drive discovery. If you haven't used local discovery yet, read :doc:`discovery_registry_local` first, since this guide builds on those concepts.

What Is Remote Discovery
------------------------

Remote discovery runs the same :class:`AgentRegistry <agentconnect.core.registry.AgentRegistry>` you know from local discovery but as a standalone server accessible over HTTP. Agents in separate processes, containers, or machines all connect to the same server and share one discovery space. The :class:`RegistryAPIClient <agentconnect.clients.RegistryAPIClient>` mirrors the ``AgentRegistry`` interface so your application code works identically regardless of which backend you use.

.. admonition:: At a glance
   :class: tip

   - Start the server with ``agentconnect serve registry``. All configuration comes from environment variables.
   - SDK clients read ``clients.registry.base_url`` from ``agentconnect.yaml``. No env vars needed on the client side.
   - Swap ``AgentRegistry`` for ``RegistryAPIClient`` and the rest of your code stays unchanged.
   - Built-in retry with exponential backoff, configurable connection pool, timeouts, and search thresholds.
   - Interactive API docs at ``http://localhost:8000/docs`` when the server is running.

When To Use It
--------------

Use remote discovery when agents span more than one process, container, or machine. It is also the right choice when you need a shared registry that outlives individual process restarts.

Use :doc:`discovery_registry_local` when all agents run in the same process. Local discovery has no network overhead, no extra server to operate, and zero configuration to get started.

Starting the Registry Server
-----------------------------

**Development quick start**

The simplest way to start the server with in-memory Qdrant (no persistence):

.. code-block:: bash

    agentconnect serve registry

The server starts on ``http://localhost:8000``. Interactive API docs are at ``/docs``. All registered agents are lost when the server restarts. See `Vector Search Deployment Mode`_ below to add persistence.

**CLI flags**

Three flags are accepted as convenience overrides. All other configuration goes through environment variables:

.. code-block:: bash

    agentconnect serve registry --host 0.0.0.0 --port 9000 --reload

.. list-table::
   :header-rows: 1
   :widths: 20 50 30

   * - Flag
     - Effect
     - Default
   * - ``--host``
     - Server bind address. Use ``0.0.0.0`` to accept connections from outside the local machine (required for Docker and cloud).
     - ``localhost``
   * - ``--port``
     - TCP port to listen on.
     - ``8000``
   * - ``--reload``
     - Enable Uvicorn auto-reload on code changes. Development only.
     - off

**Verify health**

.. code-block:: bash

    agentconnect registry ping

Or using curl:

.. code-block:: bash

    curl http://localhost:8000/health

A healthy server returns ``{"status":"healthy","registry_status":"initialized_and_ready"}``. The ``ping`` command exits with code 0 on healthy, non-zero otherwise, making it composable in scripts and health-check hooks.

You can also target a non-default URL:

.. code-block:: bash

    agentconnect registry ping --base-url http://my-registry:9000

Server Configuration
---------------------

The Registry API Server is configured **exclusively via environment variables**. No ``agentconnect.yaml`` is read by the server. That file is for SDK clients only.

All server variables carry the prefix ``AGENTCONNECT_REGISTRY_``. Nested fields use double-underscore separators (``__``).

**Core server settings**

The variables you will touch most often:

.. list-table::
   :header-rows: 1
   :widths: 48 20 32

   * - Variable
     - Default
     - Notes
   * - ``AGENTCONNECT_REGISTRY_HOST``
     - ``localhost``
     - Set to ``0.0.0.0`` for Docker or any cloud deployment.
   * - ``AGENTCONNECT_REGISTRY_PORT``
     - ``8000``
     - TCP port to listen on.
   * - ``AGENTCONNECT_REGISTRY_LOG_LEVEL``
     - ``INFO``
     - ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, or ``CRITICAL``.
   * - ``AGENTCONNECT_REGISTRY_ALLOWED_ORIGINS``
     - ``["http://localhost:5173", "http://localhost:3000"]``
     - CORS origins. Pass a JSON array (preferred) or a comma-separated string.
   * - ``AGENTCONNECT_REGISTRY_RELOAD``
     - ``false``
     - Uvicorn auto-reload on code changes. Development only.

**Deriving any env variable from the API reference**

Every field in :class:`RegistryAPISettings <agentconnect.servers.config.RegistryAPISettings>` maps to an env variable by the same rule:

- prefix with ``AGENTCONNECT_REGISTRY_``
- replace ``.`` (dot path separators) with ``__`` (double underscore)
- uppercase the result

Open the API reference, navigate the ``vector_search`` → :class:`VectorSearchSettings <agentconnect.config.models.VectorSearchSettings>` → ``advanced`` → :class:`VectorSearchAdvancedSettings <agentconnect.config.models.VectorSearchAdvancedSettings>` chain, and apply the rule to any field you want to tune. For example:

.. list-table::
   :header-rows: 1
   :widths: 42 58

   * - ``RegistryAPISettings`` field path
     - Environment variable
   * - ``host``
     - ``AGENTCONNECT_REGISTRY_HOST``
   * - ``vector_search.advanced.timeout``
     - ``AGENTCONNECT_REGISTRY_VECTOR_SEARCH__ADVANCED__TIMEOUT``
   * - ``vector_search.advanced.prefer_grpc``
     - ``AGENTCONNECT_REGISTRY_VECTOR_SEARCH__ADVANCED__PREFER_GRPC``
   * - ``vector_search.advanced.use_quantization``
     - ``AGENTCONNECT_REGISTRY_VECTOR_SEARCH__ADVANCED__USE_QUANTIZATION``

.. _vector-search-deployment-mode:

Vector Search Deployment Mode
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__TYPE`` variable selects where the embedding vectors are stored. Choose one of the four modes below.

.. admonition:: Registration records vs. embedding vectors
   :class: important

   Agent registration records (name, profile, capabilities) live in the server process's memory in all three storage modes. Restarting the server drops all registrations. The deployment mode controls **only** where the embedding vectors are stored. With ``local_file`` or ``remote``, the vector index persists across restarts and does not rebuild; with ``in_memory``, vectors rebuild on each startup.

   For a fully persistent registry, store registrations externally (database, file) and re-register on startup, or use the SDK's re-registration pattern in your agent's startup code. A persistent registration backend is on the roadmap.

In-Memory
~~~~~~~~~

Default. No configuration needed. Vectors are rebuilt from scratch on every restart. Use for ephemeral development or tests.

.. code-block:: bash

    # no env vars needed; in_memory is the default

Local File
~~~~~~~~~~

Vectors persist to disk between restarts. Registration records are still held in process memory and must be re-registered after a restart; only the embedding index survives.

.. code-block:: bash

    AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__TYPE=local_file
    AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__PATH=./qdrant_storage

Remote Qdrant
~~~~~~~~~~~~~

Recommended for production. Delegates vector storage to a Qdrant instance. The embedding index persists independently of the server process.

.. code-block:: bash

    AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__TYPE=remote
    AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__URL=http://localhost:6333
    QDRANT_API_KEY=your-api-key   # for Qdrant Cloud; omit for self-hosted without auth

JSON Override
~~~~~~~~~~~~~

For environments where nested double-underscore variables are awkward (CI secrets, some orchestrators), set the entire ``vector_search`` block as a single JSON string. This takes precedence over all nested ``__`` keys:

.. code-block:: bash

    AGENTCONNECT_REGISTRY_VECTOR_SEARCH_JSON='{"deployment":{"type":"remote","url":"http://localhost:6333"},"advanced":{"timeout":60,"use_quantization":true}}'

Using .env Files
^^^^^^^^^^^^^^^^

The server auto-loads a ``.env`` file from the working directory. For local development, create one:

.. code-block:: bash

    # .env
    AGENTCONNECT_REGISTRY_HOST=localhost
    AGENTCONNECT_REGISTRY_PORT=8000
    AGENTCONNECT_REGISTRY_LOG_LEVEL=DEBUG
    AGENTCONNECT_REGISTRY_ALLOWED_ORIGINS='["http://localhost:5173","http://localhost:3000"]'

    AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__TYPE=remote
    AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__URL=http://localhost:6333
    QDRANT_API_KEY=your-qdrant-api-key

Then run:

.. code-block:: bash

    agentconnect serve registry

The same ``.env`` file works for Docker (``--env-file .env``), Docker Compose (``env_file: .env``), and as a source for Kubernetes ConfigMaps. See `Deployment`_ for complete examples.

Client Configuration
---------------------

SDK clients read from ``agentconnect.yaml``, not from server environment variables. The only field you must set is ``base_url`` when the server is not at the default address:

.. code-block:: yaml

    clients:
      registry:
        base_url: "http://my-registry:8000"   # required if not localhost:8000

The section also accepts timeout, retry, and connection pool fields. All have sensible defaults and rarely need changing for development. See :class:`RegistryClientSettings <agentconnect.config.models.RegistryClientSettings>` in the API reference for the full field list, or :doc:`../../configuration/sdk_configuration` for YAML placement and precedence rules.

.. admonition:: Config CLI shortcut
   :class: tip

   Run ``agentconnect config init`` to generate a starter ``agentconnect.yaml``, then edit the ``clients.registry.base_url`` field.

Using RegistryAPIClient
------------------------

The :class:`RegistryAPIClient <agentconnect.clients.RegistryAPIClient>` provides the same interface as the local ``AgentRegistry``. Use it as an async context manager or manage its lifetime explicitly.

**Context manager (recommended)**

.. code-block:: python

    from agentconnect.clients import RegistryAPIClient

    async with RegistryAPIClient() as client:
        # client is open for the duration of the block
        agents = await client.get_all_agents()

**Explicit lifetime**

.. code-block:: python

    client = RegistryAPIClient(base_url="http://my-registry:9000")
    try:
        agents = await client.get_all_agents()
    finally:
        await client.close()

Pass ``base_url`` explicitly when the target server differs from ``agentconnect.yaml``. All other constructor arguments mirror the ``clients.registry`` YAML fields and override the file when provided.

Registering Agents
^^^^^^^^^^^^^^^^^^

Pass a fully constructed :class:`AgentRegistration <agentconnect.core.registry.registration.AgentRegistration>` to ``client.register()``:

.. code-block:: python

    import asyncio
    from agentconnect.clients import RegistryAPIClient
    from agentconnect.core.registry import AgentRegistration
    from agentconnect.core.types import (
        AgentIdentity,
        AgentType,
        Capability,
        InteractionMode,
        Skill,
    )

    async def main():
        async with RegistryAPIClient() as client:
            registration = AgentRegistration(
                agent_id="sql-agent-001",
                agent_type=AgentType.AI,
                interaction_modes=[InteractionMode.AGENT_TO_AGENT],
                identity=AgentIdentity.create_key_based(),
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
                default_output_modes=["text", "application/json"],
            )

            success = await client.register(registration)
            print(f"Registered: {success}")

    asyncio.run(main())

To remove an agent:

.. code-block:: python

    success = await client.unregister("sql-agent-001")

.. admonition:: Prefer hub.register for most application flows
   :class: note

   You rarely need to build an :class:`AgentRegistration <agentconnect.core.registry.registration.AgentRegistration>` by hand. Passing a ``RegistryAPIClient`` to :class:`CommunicationHub <agentconnect.communication.CommunicationHub>` and calling ``hub.register_agent(agent)`` reads the agent's profile and identity automatically. See `Using with CommunicationHub`_ below.

Finding Agents
^^^^^^^^^^^^^^

By Capability Name
~~~~~~~~~~~~~~~~~~~

Exact match against registered capability names. Falls back to semantic search automatically if no exact match exists:

.. code-block:: python

    agents = await client.get_by_capability("natural_language_to_sql")
    for agent in agents:
        print(f"{agent.name}: {agent.summary}")

Full parameter reference: :meth:`RegistryAPIClient.get_by_capability <agentconnect.clients.RegistryAPIClient.get_by_capability>`.

By Description (Semantic Search)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pass any natural language description. The registry encodes it as an embedding and returns ranked matches from the vector index:

.. code-block:: python

    results = await client.get_by_capability_semantic(
        capability_description="convert natural language questions to database queries",
        limit=5,
        similarity_threshold=0.3,
    )

    for agent_reg, score in results:
        print(f"{agent_reg.name} ({score:.3f}): {agent_reg.summary}")

**Narrowing results with filters**

Add a ``filters`` dict to restrict the candidate set before semantic scoring. All filter values are exact matches:

.. code-block:: python

    results = await client.get_by_capability_semantic(
        capability_description="data transformation and reporting",
        limit=5,
        similarity_threshold=0.2,
        filters={
            "tags": ["data", "etl"],
        },
    )

The ``filters`` parameter on the client currently supports ``tags``. For broader filter support, use the HTTP API directly (see `HTTP API Reference`_ below).

Full parameter reference: :meth:`RegistryAPIClient.get_by_capability_semantic <agentconnect.clients.RegistryAPIClient.get_by_capability_semantic>`.

.. admonition:: Semantic search returns no results
   :class: tip

   Lower ``similarity_threshold`` toward ``0.05``. A threshold above ``0.3`` filters out most results when query and capability description phrasing differ. Rich, sentence-length capability descriptions match far more reliably than single-word names.

Other Lookups
~~~~~~~~~~~~~~

Use these when you already know a structural attribute and don't need semantic matching:

.. code-block:: python

    from agentconnect.core.types import InteractionMode

    # All agents in an organization
    org_agents = await client.get_by_organization("acme-corp")

    # All agents supporting a specific interaction mode
    a2a_agents = await client.get_by_interaction_mode(InteractionMode.AGENT_TO_AGENT)

    # All agents whose identity passed verification
    verified = await client.get_verified_agents()

    # Every registered agent
    all_agents = await client.get_all_agents()

    # All unique capability names currently registered
    capability_names = await client.get_all_capabilities()

    # Single agent by id
    reg = await client.get_registration("sql-agent-001")

    # Agents registered by a specific developer
    dev_agents = await client.get_by_owner("developer-id-123")

Updating Registrations
^^^^^^^^^^^^^^^^^^^^^^^

Pass a dict of fields to update. Only the supplied fields change; everything else stays as registered:

.. code-block:: python

    updated = await client.update_registration(
        "sql-agent-001",
        {
            "tags": ["sql", "database", "postgresql", "analytics"],
            "version": "1.1.0",
            "summary": "Converts natural language questions into SQL for PostgreSQL and Redshift.",
        },
    )

Using with CommunicationHub
----------------------------

:class:`CommunicationHub <agentconnect.communication.CommunicationHub>` accepts either ``AgentRegistry`` (local) or ``RegistryAPIClient`` (remote). Swap the registry backend without touching any agent or hub logic:

.. code-block:: python

    import asyncio
    import os
    from dotenv import load_dotenv

    from agentconnect.agents import AIAgent
    from agentconnect.clients import RegistryAPIClient
    from agentconnect.communication import CommunicationHub
    from agentconnect.core.types import (
        AgentIdentity,
        AgentProfile,
        AgentType,
        Capability,
        ModelName,
        ModelProvider,
    )

    async def main():
        load_dotenv()

        # Drop-in replacement: swap AgentRegistry() for RegistryAPIClient()
        client = RegistryAPIClient()
        hub = CommunicationHub(client)

        profile = AgentProfile(
            agent_id="sql-agent-001",
            agent_type=AgentType.AI,
            name="SQL Query Agent",
            summary="Converts natural language questions into SQL SELECT queries for PostgreSQL.",
            capabilities=[
                Capability(
                    name="natural_language_to_sql",
                    description="Converts a natural language question into a SQL SELECT query.",
                ),
            ],
            tags=["sql", "database", "postgresql"],
        )

        agent = AIAgent(
            agent_id=profile.agent_id,
            identity=AgentIdentity.create_key_based(),
            profile=profile,
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O,
            api_key=os.getenv("OPENAI_API_KEY"),
        )

        # hub.register_agent builds and sends the AgentRegistration automatically
        await hub.register_agent(agent)
        print(f"Registered {agent.agent_id} with remote registry")

    asyncio.run(main())

.. note::

   ``AgentRegistry`` and ``RegistryAPIClient`` share the same interface. Switching between local and remote discovery requires changing one constructor call; no agent or hub code changes.

.. admonition:: Remote A2A communication is coming
   :class: note

   Today, the ``CommunicationHub`` routes messages locally within a single process even when the registry is remote. Distributed message delivery (remote A2A), letting agents in different processes send messages directly through the shared registry, is planned for a future release.

HTTP API Reference
------------------

When the server is running, open ``http://localhost:8000/docs`` for interactive API documentation with live request execution. The complete endpoint list, request/response schemas, and error codes are all there.

The endpoint you'll use directly most often is the semantic search:

.. code-block:: bash

    curl -X POST http://localhost:8000/agents/search/semantic \
      -H "Content-Type: application/json" \
      -d '{
        "query": "convert natural language questions to database queries",
        "top_k": 5,
        "strictness": 0.3,
        "include_tags": ["sql"],
        "output_detail": "summary"
      }'

The request schema is :class:`AgentSearchInput <agentconnect.core.registry.search.AgentSearchInput>` and the response is :class:`AgentSearchOutput <agentconnect.core.registry.search.AgentSearchOutput>`. The ``output_detail`` field accepts ``"minimal"``, ``"summary"``, ``"capabilities"``, or ``"full"``.

Programmatic Server Usage
--------------------------

For testing or custom deployments, construct the FastAPI app directly instead of using the CLI:

.. code-block:: python

    from agentconnect.servers.config import RegistryAPISettings
    from agentconnect.servers.registry_api_server import create_registry_api_app

    settings = RegistryAPISettings(
        host="0.0.0.0",
        port=8000,
        log_level="INFO",
    )

    app = create_registry_api_app(settings)

    if __name__ == "__main__":
        import uvicorn
        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port,
            log_level=settings.log_level.lower(),
        )

When ``create_registry_api_app`` is called with no arguments, it reads ``RegistryAPISettings`` from environment variables, so both patterns respect the same env-based configuration.

Deployment
----------

.. note::

   Official Docker images and a PyPI release are on the roadmap. Until then, the only fully supported deployment path is running from source using Poetry.

Clone the repository on your target machine, install dependencies, and copy the server ``.env`` template:

.. code-block:: bash

    git clone https://github.com/AKKI0511/AgentConnect.git
    cd AgentConnect
    poetry install
    cp agentconnect/servers/.env.example .env

Edit ``.env``. Set ``AGENTCONNECT_REGISTRY_HOST=0.0.0.0`` so the server accepts connections from outside localhost, and configure the Qdrant variables for your chosen deployment mode (see `Vector Search Deployment Mode`_ above).

Start the server:

.. code-block:: bash

    poetry run agentconnect serve registry

For persistent deployments, wrap this command in a process manager such as systemd or supervisord so the server restarts automatically on failure.

Advanced Usage
--------------

Distributed Agent Discovery
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. note::

   A dedicated guide for building and operating distributed networks of agents across multiple processes and teams is on the roadmap. This section covers discovery specifically. Full distributed orchestration patterns will be covered there.

Any :class:`BaseAgent <agentconnect.core.agent.BaseAgent>` subclass can register with a hub backed by ``RegistryAPIClient``. Every registered agent, regardless of its type or which process it runs in, is indexed in the same shared registry.

In the **private team model**, each process runs a self-contained group of independent agents collaborating inside their own hub. Agents across processes share nothing, yet every team's agents are visible in the shared registry. Teams scale independently without any coupling between them.

.. grid:: 1 1 2 2
   :gutter: 2

   .. grid-item-card:: Process 1  ·  Research Team
      :class-header: sd-bg-primary sd-text-white

      - Data Analyst ``AIAgent``
      - ML Forecaster ``AIAgent``
      - DB Query ``BaseAgent``

      +++
      ``CommunicationHub`` + ``RegistryAPIClient``

   .. grid-item-card:: Process 2  ·  Delivery Team
      :class-header: sd-bg-primary sd-text-white

      - Report Writer ``AIAgent``
      - Telegram Bot ``TelegramAgent``

      +++
      ``CommunicationHub`` + ``RegistryAPIClient``

.. grid:: 1

   .. grid-item-card:: Registry Server
      :class-header: sd-bg-secondary sd-text-white
      :text-align: center

      All agents from all processes are indexed here.
      Any search client queries this single shared space.

.. grid:: 1 1 2 2
   :gutter: 2

   .. grid-item-card:: MCP clients
      :class-header: sd-bg-success sd-text-white

      Connect Cursor, Claude Desktop, Google ADK, LangGraph, or any MCP-compatible client. No SDK imports required on the client side.

   .. grid-item-card:: AIAgent coordinator
      :class-header: sd-bg-success sd-text-white

      Any ``AIAgent`` registered to the same server can call ``search_for_agents`` to discover agents running in any other process.

Neither team imports code from the other. Discovery is the only connection.

**Path 1. Discovery MCP (recommended starting point)**

Most AI frameworks ship with native MCP support. Start the Discovery MCP server once and every framework's agents get capability search across all teams for free, with no custom tool code, no ``RegistryAPIClient`` imports, and no framework coupling:

.. code-block:: bash

    agentconnect mcp start agent-discovery

Any MCP-compatible client (Cursor, Claude Desktop, Google ADK, LangGraph, the OpenAI Agents SDK) can now search all five agents from both teams with a natural language query. See :doc:`../../integrations/mcp/discovery_mcp` for client configuration.

**Path 2. Built-in ``search_for_agents`` (AIAgent teams)**

``AIAgent`` exposes a built-in ``search_for_agents`` tool that the LLM calls automatically during reasoning. Register each team's agents to the shared registry; any ``AIAgent`` coordinator in any process can then search across all of them.

.. admonition:: Discovery boundary
   :class: important

   **Discovery across processes**: fully supported for all ``BaseAgent`` types.

   **Direct messaging across processes**: not yet available. ``send_collaboration_request`` only reaches agents in the **same** hub (same process). Co-locate collaborating agents in one hub for task delegation today.

.. dropdown:: Example: two teams, one coordinator
   :color: primary
   :icon: code

   Each team follows the same pattern: hub backed by ``RegistryAPIClient``, agent profiles, register, run. The structure is identical. Only the profiles differ. Here is Team A in full; Team B is the same file with different profiles.

   **team_research.py (Research Team)**

   .. code-block:: python

       import asyncio
       import os
       from dotenv import load_dotenv

       from agentconnect.agents import AIAgent
       from agentconnect.clients import RegistryAPIClient
       from agentconnect.communication import CommunicationHub
       from agentconnect.core.types import (
           AgentIdentity, AgentProfile, AgentType,
           Capability, ModelName, ModelProvider, Skill,
       )

       PROFILES = [
           AgentProfile(
               agent_id="data-analyst-001",
               agent_type=AgentType.AI,
               name="Data Analyst",
               summary="Analyzes structured datasets and produces statistical summaries, trend reports, and visualisation specs.",
               capabilities=[
                   Capability(name="statistical_analysis", description="Computes descriptive statistics, correlations, and distributions from tabular data."),
                   Capability(name="trend_detection", description="Identifies upward, downward, and seasonal trends in time-series data."),
               ],
               skills=[Skill(name="Pandas", description="Python data analysis with Pandas and NumPy")],
               tags=["data", "analysis", "statistics"],
           ),
           AgentProfile(
               agent_id="ml-forecaster-001",
               agent_type=AgentType.AI,
               name="ML Forecaster",
               summary="Builds and evaluates time-series forecasting models using scikit-learn and statsmodels.",
               capabilities=[
                   Capability(name="demand_forecasting", description="Predicts future demand from historical time-series using ARIMA, Prophet, or gradient boosting."),
               ],
               tags=["ml", "forecasting", "time-series"],
           ),
       ]

       async def main():
           load_dotenv()
           hub = CommunicationHub(RegistryAPIClient())
           agents = [
               AIAgent(
                   agent_id=p.agent_id,
                   identity=AgentIdentity.create_key_based(),
                   profile=p,
                   provider_type=ModelProvider.OPENAI,
                   model_name=ModelName.GPT4O,
                   api_key=os.getenv("OPENAI_API_KEY"),
               )
               for p in PROFILES
           ]
           for agent in agents:
               await hub.register_agent(agent)
           print(f"Research team online: {[p.agent_id for p in PROFILES]}")
           await asyncio.gather(*[a.run() for a in agents])

       if __name__ == "__main__":
           asyncio.run(main())

   Team B (``team_delivery.py``) is the same file. Swap in its profiles (Report Writer, Telegram Bot) and set the correct ``ModelProvider`` for each agent.

   **What the coordinator actually discovers**

   The coordinator registers with the same remote registry. When its LLM calls ``search_for_agents("data analysis statistics")``, the tool injects this JSON into the LLM's context (agents from Team A, found with zero imports from ``team_research.py``):

   .. code-block:: json

       {
         "message": "Found 2 agents matching 'data analysis statistics'.",
         "results": [
           {
             "agent_id": "data-analyst-001",
             "name": "Data Analyst",
             "summary": "Analyzes structured datasets and produces statistical summaries, trend reports, and visualisation specs.",
             "similarity_score": 0.91,
             "capabilities": ["statistical_analysis", "trend_detection"],
             "tags": ["data", "analysis", "statistics"]
           },
           {
             "agent_id": "ml-forecaster-001",
             "name": "ML Forecaster",
             "summary": "Builds and evaluates time-series forecasting models using scikit-learn and statsmodels.",
             "similarity_score": 0.74,
             "capabilities": ["demand_forecasting"],
             "tags": ["ml", "forecasting", "time-series"]
           }
         ]
       }

   The LLM now knows exactly which specialists exist and what each one does. It can respond: *"I'll send the sales data to* ``data-analyst-001`` *for statistical analysis, then pass the findings to* ``report-writer-001`` *from Team B for the executive report."*

   **Coordinator (``coordinator.py``)**

   Run this after both team scripts are up. Type any task and the coordinator will search across all registered agents, including the ones running in separate processes.

   .. code-block:: python

       import asyncio
       import os
       from dotenv import load_dotenv

       from agentconnect.agents import AIAgent
       from agentconnect.clients import RegistryAPIClient
       from agentconnect.communication import CommunicationHub
       from agentconnect.core.types import (
           AgentIdentity, AgentProfile, AgentType,
           Capability, ModelName, ModelProvider,
       )

       COORDINATOR_PROMPT = """
       You are a project coordinator with access to a distributed network of specialist agents.
       Before planning any multi-step task, call search_for_agents to discover which specialists
       are available and what each one does. Name specific agent IDs in your plan.
       """

       async def main():
           load_dotenv()

           hub = CommunicationHub(RegistryAPIClient())
           profile = AgentProfile(
               agent_id="coordinator-001",
               agent_type=AgentType.AI,
               name="Project Coordinator",
               summary="Discovers specialist agents and orchestrates multi-step workflows.",
               capabilities=[
                   Capability(
                       name="workflow_orchestration",
                       description="Plans and routes tasks to registered specialist agents.",
                   ),
               ],
               tags=["coordinator", "orchestration"],
           )
           agent = AIAgent(
               agent_id=profile.agent_id,
               identity=AgentIdentity.create_key_based(),
               profile=profile,
               provider_type=ModelProvider.OPENAI,
               model_name=ModelName.GPT4O,
               api_key=os.getenv("OPENAI_API_KEY"),
               system_prompt=COORDINATOR_PROMPT,
           )

           # Registering wires search_for_agents to the live remote registry.
           # chat() reuses this workflow, so discovery works from the terminal.
           await hub.register_agent(agent)

           print("Coordinator ready. Ask it to find agents or plan a task.")
           print("Type 'quit' to exit.\n")
           while True:
               user_input = input("You: ").strip()
               if user_input.lower() in ("quit", "exit", "q"):
                   break
               if not user_input:
                   continue
               response = await agent.chat(user_input)
               print(f"\nCoordinator: {response}\n")

       if __name__ == "__main__":
           asyncio.run(main())

Federated Search Across Multiple Registries
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each ``RegistryAPIClient`` instance is independent. If your system spans multiple isolated registry deployments (one per data-center region or tenant), you can query all of them concurrently and merge results in a single call:

.. code-block:: python

    import asyncio
    from agentconnect.clients import RegistryAPIClient


    async def federated_search(
        query: str,
        registries: list[str],
        limit: int = 5,
    ):
        """Query multiple registries concurrently and return deduplicated results."""

        async def search_one(url: str):
            async with RegistryAPIClient(base_url=url) as client:
                return await client.get_by_capability_semantic(
                    capability_description=query,
                    limit=limit,
                )

        all_results = await asyncio.gather(*[search_one(url) for url in registries])

        # Flatten, deduplicate by agent_id, keep highest score per agent
        seen: dict[str, tuple] = {}
        for results in all_results:
            for reg, score in results:
                if reg.agent_id not in seen or score > seen[reg.agent_id][1]:
                    seen[reg.agent_id] = (reg, score)

        return sorted(seen.values(), key=lambda x: x[1], reverse=True)[:limit]


    # Usage
    results = await federated_search(
        query="natural language to SQL",
        registries=[
            "http://registry-us-east:8000",
            "http://registry-eu-west:8000",
        ],
    )

Troubleshooting
---------------

**Server won't start**

- Confirm nested environment variables use ``__`` (double underscore), not a single underscore. Use ``AGENTCONNECT_REGISTRY_VECTOR_SEARCH__DEPLOYMENT__TYPE``, not ``AGENTCONNECT_REGISTRY_VECTOR_SEARCH_DEPLOYMENT_TYPE``.
- For complex ``vector_search`` config, prefer the single JSON override: ``AGENTCONNECT_REGISTRY_VECTOR_SEARCH_JSON`` (see `JSON Override`_ above).
- If using remote Qdrant, verify the Qdrant server is reachable before starting the registry server.

**Agent registration silently lost after restart**

Registration records live in the server's process memory. If the server restarts, all registrations are gone. Agents must re-register on their next startup. A persistent registration backend is on the roadmap; until then, add a retry loop around your agent's startup registration code.

**Semantic search is slow on first query**

The sentence-transformer embedding model loads lazily on the first search request. Subsequent queries are fast. If latency spikes recur on later queries, check remote Qdrant server load. For remote Qdrant, enabling gRPC can cut round-trip time significantly: ``AGENTCONNECT_REGISTRY_VECTOR_SEARCH__ADVANCED__PREFER_GRPC=true``.

Next Steps
----------

- :doc:`../../integrations/mcp/discovery_mcp` — expose the shared registry to Cursor, Claude Desktop, or any MCP client; the simplest path for distributed discovery today
- :doc:`../../systems/agent_toolbox` — enable agents to discover and delegate work using the built-in search and collaboration tools
- :doc:`../../systems/agent_network_setup` — build a complete multi-service system using remote discovery
- :doc:`../../configuration/sdk_configuration` — full ``agentconnect.yaml`` reference and client settings
- :doc:`discovery_registry_local` — compare with in-process local discovery
- `Servers README <https://github.com/AKKI0511/AgentConnect/blob/main/agentconnect/servers/README.md>`_ — complete server environment variable reference
- :class:`RegistryAPISettings <agentconnect.servers.config.RegistryAPISettings>` / :class:`RegistryClientSettings <agentconnect.config.models.RegistryClientSettings>` — full configuration field reference in the API docs
