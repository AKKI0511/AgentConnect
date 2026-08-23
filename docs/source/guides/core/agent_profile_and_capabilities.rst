Agent Profile & Capabilities
=============================

.. _agent_profile_capabilities:

Prerequisites
-------------

Complete the :doc:`../../installation` setup before starting. Skim :doc:`../core_concepts` for the mental model if you haven't already. If you're new to agents, check out :doc:`agents/index` first.

What Is AgentProfile
--------------------

:class:`AgentProfile <agentconnect.core.types.AgentProfile>` is the structured description an agent publishes about itself so the ecosystem can discover and understand it.

Think of it as a calling card that another AI agent checks before deciding whether to contact yours. When an agent needs help, it searches the registry semantically and receives ranked matches. Depending on how much detail it asks for, it may check just the name and summary, or inspect the full capabilities list. Your profile is what it reads.

.. admonition:: Write for agents, not humans
   :class: important

   ``AgentProfile`` is consumed by AI agents during discovery, not by human developers browsing a catalog. Structure your ``name``, ``summary``, ``description``, ``capabilities``, and ``skills`` to be precise, truthful, and specific. Vague text like *"a powerful AI assistant"* signals nothing. Specific, domain-anchored text like *"translates natural language questions into SQL SELECT statements for PostgreSQL 14+"* is what discovery acts on.

.. admonition:: At a glance
   :class: tip

   - ``AgentProfile`` is the unit of semantic discovery.
   - ``Capability`` describes a discrete action your agent performs.
   - ``Skill`` describes a domain or area of expertise your agent has.
   - What you write in the profile directly determines who discovers you and how accurately.

When To Use It
--------------

Every agent that registers with a registry needs a profile. It is used by:

- The registry, which indexes it for semantic search.
- Other AI agents, which query and read matching profiles before initiating collaboration.
- The Discovery MCP server, which exposes profile fields to MCP-compatible clients (Cursor, Claude Desktop).

If your agent will never be discovered (e.g., a private utility agent), a profile still provides a clean contract for future use.

How It Works: Profile to Discovery
----------------------------------

.. code-block:: text

   You define AgentProfile
          |
   Agent registers with AgentRegistry (via hub.register)
          |
   Registry indexes the profile for semantic search
          |
   Another agent uses a tool to search (e.g. "find an agent that can do X")
          |
   Registry returns ranked matches with varying detail levels
          |
   Requesting agent reads what it needs, decides to collaborate

The richer and more precise your profile fields are, the better your agent surfaces for the right searches.

Core Data Structures
--------------------

AgentProfile
^^^^^^^^^^^^

:class:`AgentProfile <agentconnect.core.types.AgentProfile>`'s fields fall into two groups.

.. admonition:: Required fields
   :class: important

   ``agent_id`` and ``agent_type`` are the only required fields. All others are optional, but filling in the discovery fields below is strongly recommended for any agent that should be found by others.

**Discovery fields** - included in semantic search matching:

.. list-table::
   :header-rows: 1
   :widths: 22 15 63

   * - Field
     - Type
     - Purpose
   * - ``name``
     - ``str``
     - Short, human and agent-readable name for your agent.
   * - ``summary``
     - ``str``
     - One or two sentences capturing the core purpose. Often the most informative signal in a search result.
   * - ``description``
     - ``str``
     - Full explanation of what the agent does, its domain, constraints, and how to interact with it.
   * - ``capabilities``
     - ``List[Capability]``
     - Discrete actions the agent can perform. Each capability's name and description contribute to matching.
   * - ``skills``
     - ``List[Skill]``
     - Domain expertise areas. Each skill's name and description contribute to matching.
   * - ``examples``
     - ``List[str]``
     - Example inputs, queries, or use cases. Helps match natural-language searches.
   * - ``tags``
     - ``List[str]``
     - Short keywords for category filtering (e.g., ``["nlp", "sql", "database"]``).
   * - ``default_input_modes``
     - ``List[str]``
     - Input modalities the agent accepts (e.g., ``["text", "image"]``).
   * - ``default_output_modes``
     - ``List[str]``
     - Output modalities the agent produces (e.g., ``["text", "application/json"]``).
   * - ``auth_schemes``
     - ``List[str]``
     - Authentication methods the agent supports (e.g., ``["api_key", "oauth2"]``). Included in discovery and returned in detailed search results.

**Metadata fields** - stored and returned in results, but not included in semantic matching:

.. list-table::
   :header-rows: 1
   :widths: 22 15 63

   * - Field
     - Type
     - Purpose
   * - ``agent_id``
     - ``str``
     - **(Required)** Unique identifier for the agent.
   * - ``agent_type``
     - ``AgentType``
     - **(Required)** ``AgentType.AI`` or ``AgentType.HUMAN``.
   * - ``version``
     - ``str``
     - Semantic version of the agent (e.g., ``"1.0.0"``).
   * - ``organization``
     - ``str``
     - Organization providing the agent. A verifiable DID (e.g., ``"did:org:123"``) is recommended for future trust verification.
   * - ``developer``
     - ``str``
     - Developer or team. Also recommended as a verifiable ID when possible.
   * - ``url``
     - ``str``
     - Endpoint or homepage URL.
   * - ``documentation_url``
     - ``str``
     - Link to the agent's documentation.
   * - ``payment_address``
     - ``str``
     - Wallet address for receiving payments. When ``enable_payments=True``, this is **set automatically** by the framework from the initialized wallet. See `Payment Address`_ below.
   * - ``custom_metadata``
     - ``Dict[str, Any]``
     - Arbitrary key-value data. Not searched, but passed through in results.
   * - ``reputation_score``
     - ``float``
     - **(Ecosystem-assigned, read-only)** Intended to be populated by the registry or network based on observed behavior. Not set by the agent developer. Currently not populated in practice. See `Known Limitations & Future Evolution`_ below.

Capability
^^^^^^^^^^

:class:`Capability <agentconnect.core.types.Capability>` is a dataclass representing a discrete action your agent performs.

.. list-table::
   :header-rows: 1
   :widths: 22 15 63

   * - Field
     - Type
     - Purpose
   * - ``name``
     - ``str``
     - Short identifier for the capability (e.g., ``"sql_query_generation"``).
   * - ``description``
     - ``str``
     - Clear explanation of what the capability does and any constraints. This is the primary field for matching.
   * - ``version``
     - ``str``
     - Version of this capability. Defaults to ``"1.0"``.
   * - ``input_schema``
     - ``Optional[Dict[str, str]]``
     - **(Placeholder)** Not used by any discovery or runtime logic today. Leave as ``None``.
   * - ``output_schema``
     - ``Optional[Dict[str, str]]``
     - **(Placeholder)** Not used by any discovery or runtime logic today. Leave as ``None``.

.. admonition:: About input_schema and output_schema
   :class: note

   These fields exist as design placeholders for future structured contract enforcement. They are stored but neither validated nor used in any runtime path. The design will evolve in upcoming versions, either toward proper JSON Schema contracts or a different approach.

Skill
^^^^^

:class:`Skill <agentconnect.core.types.Skill>` represents a domain of expertise.

.. list-table::
   :header-rows: 1
   :widths: 22 15 63

   * - Field
     - Type
     - Purpose
   * - ``name``
     - ``str``
     - Short name for the skill area (e.g., ``"PostgreSQL"``, ``"financial_analysis"``).
   * - ``description``
     - ``str``
     - Optional elaboration. More detail improves matching.

Capability vs Skill: Avoiding Confusion
""""""""""""""""""""""""""""""""""""""""

These two look similar but serve different purposes:

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * -
     - Capability
     - Skill
   * - **What it is**
     - A discrete action your agent can perform
     - A domain or area of expertise your agent has
   * - **Think of it as**
     - A verb ("generate", "translate", "summarize")
     - A noun ("SQL", "NLP", "financial modeling")
   * - **Example**
     - ``"Converts a natural language question into a SQL SELECT query"``
     - ``"PostgreSQL 14+ dialect and internals"``
   * - **When to use**
     - When you want to say "my agent can DO this"
     - When you want to say "my agent KNOWS this domain"

A single agent typically has fewer capabilities than skills. Skills help broaden the semantic surface area without cluttering the capabilities list.

Creating a Profile
------------------

Minimal Profile
^^^^^^^^^^^^^^^

The two required fields are ``agent_id`` and ``agent_type``:

.. code-block:: python

    from agentconnect.core.types import AgentProfile, AgentType

    profile = AgentProfile(
        agent_id="my-agent-001",
        agent_type=AgentType.AI,
        name="My Agent",
    )

This works technically but will be nearly undiscoverable. Other agents searching semantically won't find it unless their query nearly matches "My Agent".

Production-Ready Profile
^^^^^^^^^^^^^^^^^^^^^^^^

For any agent that others should discover, fill in all discovery fields:

.. code-block:: python

    from agentconnect.core.types import (
        AgentProfile,
        AgentType,
        Capability,
        Skill,
    )

    profile = AgentProfile(
        agent_id="sql-agent-prod-001",
        agent_type=AgentType.AI,

        # Discovery: name, summary, description
        name="SQL Query Agent",
        summary=(
            "Translates natural language questions into SQL SELECT statements "
            "for PostgreSQL 14+ databases and explains query execution plans."
        ),
        description=(
            "Given a natural language question and an optional schema context, "
            "this agent generates syntactically correct, optimized SQL SELECT queries. "
            "It can also analyze EXPLAIN output and suggest index improvements. "
            "It does not execute queries directly — it returns the SQL string and, "
            "optionally, an explanation of the query logic."
        ),

        # Discovery: capabilities (what the agent can DO)
        capabilities=[
            Capability(
                name="natural_language_to_sql",
                description=(
                    "Converts a natural language question into a SQL SELECT query. "
                    "Requires the user to provide table names and optionally column names. "
                    "Supports JOINs, aggregations, subqueries, and CTEs."
                ),
            ),
            Capability(
                name="explain_query_plan",
                description=(
                    "Accepts a SQL query and a PostgreSQL EXPLAIN output, then returns "
                    "a plain-language explanation of what the query does and why it is "
                    "slow or fast, with specific index recommendations."
                ),
            ),
        ],

        # Discovery: skills (what the agent KNOWS)
        skills=[
            Skill(name="PostgreSQL", description="PostgreSQL 14+ dialect and internals"),
            Skill(name="SQL optimization", description="Query planning, index design, execution analysis"),
        ],

        # Discovery: examples (natural phrasing helps fuzzy searches)
        examples=[
            "How many orders were placed last month?",
            "Find all users who haven't logged in for 90 days",
            "Why is this query doing a sequential scan?",
        ],

        # Discovery: tags for category filtering
        tags=["sql", "database", "postgresql", "nlp", "query-generation"],

        # Discovery: input/output modalities
        default_input_modes=["text"],
        default_output_modes=["text", "application/json"],

        # Metadata
        version="1.2.0",
        organization="Acme Data Team",
        documentation_url="https://docs.acme.example/sql-agent",
    )

Using AgentProfile with AIAgent
--------------------------------

The recommended way to create an ``AIAgent`` is to build the profile first and pass it in:

.. code-block:: python

    import os
    from dotenv import load_dotenv

    from agentconnect.prebuilt import AIAgent
    from agentconnect.core.types import (
        AgentIdentity,
        AgentProfile,
        AgentType,
        Capability,
        ModelName,
        ModelProvider,
        Skill,
    )

    load_dotenv()

    identity = AgentIdentity.create_key_based()

    profile = AgentProfile(
        agent_id="sql-agent-001",
        agent_type=AgentType.AI,
        name="SQL Query Agent",
        summary="Converts natural language to SQL for PostgreSQL databases.",
        description=(
            "Generates optimized SQL SELECT queries from natural language questions. "
            "Provide table names and an optional schema; receive a SQL string plus explanation."
        ),
        capabilities=[
            Capability(
                name="natural_language_to_sql",
                description=(
                    "Converts natural language questions to SQL SELECT queries. "
                    "Handles JOINs, aggregations, CTEs, and window functions."
                ),
            ),
        ],
        skills=[
            Skill(name="PostgreSQL", description="PostgreSQL 14+ dialect"),
            Skill(name="SQL", description="Standard SQL query writing and optimization"),
        ],
        tags=["sql", "postgresql", "database", "query"],
        default_input_modes=["text"],
        default_output_modes=["text", "application/json"],
    )

    agent = AIAgent(
        agent_id="sql-agent-001",
        identity=identity,
        profile=profile,
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key=os.getenv("OPENAI_API_KEY"),
        personality="precise and concise; always explain your SQL choices",
    )

.. admonition:: personality vs profile
   :class: tip

   ``personality`` shapes how the agent behaves internally: tone, caution level, verbosity. The profile's ``description`` and ``summary`` shape how the agent appears to the discovery system. Keep them separate. Never put personality traits in the profile.

Registering and Being Discovered
--------------------------------

Register your agent with the hub so it is indexed for discovery:

.. code-block:: python

    from agentconnect.communication import CommunicationHub
    from agentconnect.core.registry import AgentRegistry

    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    await hub.register_agent(agent)

Once registered, two paths exist for discovering your agent:

**Via the built-in tool (AIAgent)**

``AIAgent`` automatically gets a ``search_for_agents`` tool when connected to a hub and registry. Any AI agent in the network can use it to find yours:

.. code-block:: text

   # The agent decides autonomously when to search. Example internal invocation:
   search_for_agents(
       query="I need an agent that can convert natural language to SQL",
       output_detail="summary",   # or "minimal", "capabilities", "full"
       top_k=3,
   )

The ``output_detail`` parameter controls how much of your profile the searching agent receives:

- ``"minimal"`` - agent_id, name, url, payment_address
- ``"summary"`` - adds summary, tags
- ``"capabilities"`` - adds capabilities, skills
- ``"full"`` - adds description, examples, version, organization, auth_schemes, input/output modes

**Via the registry API (programmatic)**

You can also search directly using the registry:

.. code-block:: python

    results = await registry.get_by_capability_semantic(
        capability_description="convert natural language to SQL",
        limit=3,
        similarity_threshold=0.3,
    )
    for registration, score in results:
        print(registration.name, score)

Writing Effective Profiles
---------------------------

The same principles that make good prompts make good profiles.

**Be specific, not impressive**

.. code-block:: python

    # Poor: vague and unactionable
    summary = "A powerful AI assistant that can help with many tasks"

    # Good: specific and machine-readable
    summary = (
        "Fetches live weather data and 7-day forecasts for any location using "
        "the OpenWeatherMap API and returns structured JSON."
    )

**Describe constraints and limits**

Telling other agents what your agent *cannot* do prevents bad matches:

.. code-block:: python

    description = (
        "Generates SQL SELECT queries only. No INSERT, UPDATE, DELETE, or DDL. "
        "Does not connect to any database directly. Requires table and column names as input. "
        "Supports PostgreSQL 14+ dialect; MySQL and SQLite syntax may differ."
    )

**Write capabilities as verb-phrases**

.. code-block:: python

    # Poor: a noun that says nothing
    Capability(name="sql", description="SQL")

    # Good: verb-phrase describing the action and scope
    Capability(
        name="natural_language_to_sql",
        description=(
            "Converts a natural language question into a SQL SELECT query for "
            "a user-supplied schema. Returns the query string and an optional "
            "plain-language explanation of the query logic."
        ),
    )

**Use examples as natural-language search bait**

Each example is embedded as-is. Write them the way a human or agent would actually phrase a search:

.. code-block:: python

    examples = [
        "How many users signed up in the last 30 days?",
        "Get top 10 products by revenue this quarter",
        "Find all orders with a status of pending older than 7 days",
    ]

**Use tags for hard filtering**

Include both specific and broad terms, lowercase and hyphen-separated:

.. code-block:: python

    tags = ["sql", "postgresql", "database", "query-generation", "nlp"]

**Use skills for domain breadth**

Add skills for every domain your agent is competent in, even if they overlap with capabilities. This broadens the semantic surface area:

.. code-block:: python

    skills = [
        Skill(name="SQL", description="SQL query writing for relational databases"),
        Skill(name="PostgreSQL", description="PostgreSQL-specific features: CTEs, window functions, JSONB"),
        Skill(name="query optimization", description="Reading EXPLAIN plans and recommending indexes"),
    ]

.. admonition:: Accuracy matters for trust
   :class: warning

   Agents in the network make decisions based on your profile. Overstating capabilities leads to failed collaborations and wasted tokens. If a capability has known limits, document them honestly.

Advanced Usage
--------------

Adding Custom Metadata
^^^^^^^^^^^^^^^^^^^^^^^

Use ``custom_metadata`` for structured data that does not fit other fields. It is stored and returned in search results but does not affect discovery ranking:

.. code-block:: python

    profile = AgentProfile(
        agent_id="sql-agent-001",
        agent_type=AgentType.AI,
        name="SQL Query Agent",
        summary="Converts natural language to SQL for PostgreSQL.",
        custom_metadata={
            "supported_databases": ["postgresql-14", "postgresql-15"],
            "max_schema_tables": 50,
            "rate_limit_rpm": 60,
            "contact_channel": "slack:#sql-agent-support",
        },
    )

Updating a Profile
^^^^^^^^^^^^^^^^^^

Profiles are indexed at registration time. Re-registration with the same ``agent_id`` is rejected. To update a profile, unregister first, then update and re-register:

.. code-block:: python

    # 1. Unregister
    await hub.unregister_agent(agent.agent_id)

    # 2. Update the profile
    # ...

    # 3. Re-register
    await hub.register_agent(agent)

.. admonition:: Note
   :class: note

   There is no targeted field-level update API today. Unregister-modify-re-register is the current pattern. A dedicated update mechanism may be added in future versions.

Verifiable Organization and Developer IDs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``organization`` and ``developer`` fields accept plain strings or decentralized identifiers. Using a DID is recommended for future trust verification:

.. code-block:: python

    profile = AgentProfile(
        agent_id="sql-agent-001",
        agent_type=AgentType.AI,
        name="SQL Query Agent",
        summary="Converts natural language to SQL for PostgreSQL.",
        organization="did:org:acme-data-team",
        developer="did:person:alice",
    )

Payment Address
^^^^^^^^^^^^^^^^

When ``enable_payments=True``, the framework initializes a Coinbase wallet and **automatically writes the wallet address** to ``agent.profile.payment_address``. You do not set it manually in the profile.

.. code-block:: python

    agent = AIAgent(
        agent_id="sql-agent-001",
        identity=identity,
        profile=profile,
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key=os.getenv("OPENAI_API_KEY"),
        enable_payments=True,   # wallet initializes and fills profile.payment_address
    )

    # After construction, profile.payment_address is set from the wallet
    print(agent.profile.payment_address)

If you want to set a specific address without enabling the full payment stack, you can assign it manually in the profile before passing it to the agent.

Known Limitations & Future Evolution
--------------------------------------

**reputation_score**

This field is intended to be assigned by the registry or network ecosystem based on observed agent behavior, interaction success rates, or peer signals. It is NOT set by the agent developer. It is also excluded from profile serialization, so it does not appear in registry data today. Currently nothing in the runtime populates it. The field is a design placeholder for a future reputation system.

**input_schema and output_schema in Capability**

These two fields are stored but not read or enforced anywhere in the current runtime. They are placeholders for future structured contract enforcement. Leave them as ``None``.

**Trust verification is in progress**

The ``organization`` and ``developer`` fields accept any string today. Registry-verified identity proofs (DID-based) are planned for a future release. Treat them as informational metadata for now.

**Remote discovery is expanding**

Search currently operates over locally registered agents or agents registered via the Registry API server. Remote multi-registry discovery and cross-network profile federation are planned for future versions.

Next Steps
----------

- :doc:`discovery/index` - Learn how the registry indexes profiles and how to search for agents.
- :doc:`discovery/discovery_registry_local` - Run a local registry, register agents, and test semantic search.
- :doc:`communication/index` - Connect registered agents and route messages between them.
- :doc:`agents/ai_agent` - Full reference for AIAgent parameters including profile-based initialization.
- :class:`AgentProfile API reference <agentconnect.core.types.AgentProfile>` - Full field listing with types.
