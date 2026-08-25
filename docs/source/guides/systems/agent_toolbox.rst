Agent Toolbox: Discover, Delegate, Track
=========================================

.. _agent_toolbox:

Any agent that joins a network needs three coordination tools. These tools let an agent
find who can help, hand off work to that peer, and retrieve the result. Everything else
a team of agents does flows from these three primitives.

.. grid:: 1 1 3 3
   :gutter: 3

   .. grid-item-card:: search_for_agents
      :shadow: sm

      Find a peer by describing what you need. Semantic search across full agent
      profiles returns a ranked list with IDs ready for delegation.

   .. grid-item-card:: send_collaboration_request
      :shadow: sm

      Send a task to a specific agent and wait for the reply. Message routing,
      signing, and response tracking are handled automatically.

   .. grid-item-card:: check_collaboration_result
      :shadow: sm

      Retrieve a result that arrived after the initial timeout. The target may
      still respond; this tool checks the late-reply buffer.

**How to connect these tools to your agent**

``AIAgent`` includes all three automatically on hub registration. For agents built with
other frameworks, the Discovery MCP server already exposes ``search_for_agents``; see
:doc:`../integrations/mcp/discovery_mcp`. The Communication MCP with
``send_collaboration_request`` and ``check_collaboration_result`` is planned for a
near-term release.

See :doc:`agent_network_setup` for wiring the hub and registry these tools depend on.


``search_for_agents``
----------------------

Runs a semantic search against every registered agent's full
:class:`AgentProfile <agentconnect.core.types.AgentProfile>`. The index
covers name, summary, description, capabilities, skills, tags, and examples. Vector
embeddings handle the matching, so natural language queries find relevant agents without
exact keyword matches.

.. admonition:: What gets searched
   :class: note

   The search runs against the full profile, not just capability names. A query like
   *"expert in Python data pipelines"* can match an agent whose summary describes data
   processing workflows, even without a capability literally named that.

The tool automatically excludes the calling agent, agents in active conversations with
the caller, agents with recent timeouts, and human agents. Results show only agents
available for new work.

**Parameters**

.. list-table::
   :header-rows: 1
   :widths: 22 13 65

   * - Parameter
     - Default
     - Description
   * - ``query``
     - *(required)*
     - Natural language description of the capability or expertise you need.
   * - ``top_k``
     - ``5``
     - Maximum number of results to return.
   * - ``strictness``
     - ``0.2``
     - Similarity threshold from 0.0 to 1.0. Higher values require closer matches.
   * - ``output_detail``
     - ``"summary"``
     - Controls how much profile data is returned per result. See detail levels below.
   * - ``include_tags``
     - ``None``
     - Optional tag list. Restricts results to agents carrying at least one of these
       exact tags. Useful when semantic search alone is too broad for a domain.

**Output detail levels**

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Level
     - Fields returned per result
   * - ``"minimal"``
     - ``agent_id``, name, URL, payment address
   * - ``"summary"`` *(default)*
     - Minimal + summary + tags
   * - ``"capabilities"``
     - Summary + capabilities and skills lists
   * - ``"full"``
     - Complete profile: description, examples, version, and all other fields

**Output**

Returns :class:`AgentSearchOutput <agentconnect.team.directory.search.schemas.AgentSearchOutput>`
with a ``message`` string and a ``results`` list. Each item is an
:class:`AgentSearchResultItem <agentconnect.team.directory.search.schemas.AgentSearchResultItem>`
carrying ``agent_id``, ``similarity_score``, and the profile fields for the requested
detail level. Pass ``agent_id`` directly to ``send_collaboration_request``.


``send_collaboration_request``
-------------------------------

Sends a message through the hub to a specific agent and waits for the reply. The hub
signs and routes the message, assigns a unique ``request_id``, and handles response
correlation.

**Parameters**

.. list-table::
   :header-rows: 1
   :widths: 22 13 65

   * - Parameter
     - Default
     - Description
   * - ``target_agent_id``
     - *(required)*
     - The ``agent_id`` from a ``search_for_agents`` result.
   * - ``task``
     - *(required)*
     - Complete task description. Include all context the receiving agent needs; it
       has no other access to the original request.
   * - ``timeout``
     - ``120``
     - Seconds to wait for a reply, capped at 300. The hub may use a shorter estimate
       based on task description length.

**Three possible outcomes**

.. tab-set::

   .. tab-item:: Success

      **Returns:** ``success=True``, ``response`` set.

      The reply arrived within the timeout. Use ``response`` directly and continue.

   .. tab-item:: Timeout

      **Returns:** ``success=False``, ``error="timeout"``, ``request_id`` set.

      No reply arrived within the timeout. The target is still running. Store the
      ``request_id`` and use ``check_collaboration_result`` to retrieve the result
      when it arrives.

   .. tab-item:: Error

      **Returns:** ``success=False``, ``error`` field names the cause.

      Validation failure. Common causes:

      - Target agent not active or not found
      - Request directed at self or at a human agent
      - Collaboration loop detected
      - Chain exceeded five hops

**Loop prevention**

Each request carries a ``collaboration_chain`` that records every agent in the hop path.
The tool blocks requests that would reach an agent already in the chain, and rejects
chains longer than five hops. This stops circular delegation where agents keep forwarding
a task without resolving it.


``check_collaboration_result``
-------------------------------

Polls the hub's late-response buffer for a result that arrived after a previous timeout.
Call this with the ``request_id`` from a timed-out ``send_collaboration_request``.

**Input**

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Parameter
     - Description
   * - ``request_id``
     - The ID returned by the timed-out ``send_collaboration_request`` call.

**Possible statuses**

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Status
     - Meaning
   * - ``completed``
     - Result retrieved from a response that finished within the original timeout.
   * - ``completed_late``
     - Late reply retrieved from the hub's buffer. The target did respond, just
       after the original timeout.
   * - ``pending``
     - Still processing. Call again later.
   * - ``pending_after_timeout``
     - Previously timed out; no late reply yet.
   * - ``not_found``
     - ID not tracked. Already consumed, cleared from memory, or incorrect.
   * - ``error``
     - Exception during retrieval. The ``response`` field contains the cause.

.. admonition:: Late replies are consumed on retrieval
   :class: warning

   A successful call removes the result from the buffer. A second call with the same
   ``request_id`` returns ``not_found``.


End-to-End Flow
----------------

.. code-block:: text

   Task arrives the agent cannot handle alone
           │
           ▼
   search_for_agents("I need someone who can ...")
           │
           └── results: ranked list with agent_ids and similarity scores
                           │
                           │  pick best match
                           ▼
               send_collaboration_request(agent_id, task)
                           │
                           ├── success=True ──────────► use response, continue
                           │
                           └── error="timeout", request_id set
                                       │
                                       │  do other work, then...
                                       ▼
                               check_collaboration_result(request_id)
                                       │
                                       ├── completed_late ──► use response, continue
                                       └── pending ─────────► check again later

Each agent in a network decides on its own when to search, when to delegate, and when to
follow up. No agent directs another. Coordination emerges from individual decisions made
by peers using a shared set of tools.

Profile Quality and Discovery
------------------------------

``search_for_agents`` can only find what is written in each agent's
:class:`AgentProfile <agentconnect.core.types.AgentProfile>`. A
sparse profile with only a name produces weak results. Profiles with detailed summaries,
capability and skill descriptions, worked examples, and accurate tags surface reliably in
the right queries.

See :doc:`../core/agent_profile_and_capabilities` for the full field reference and
guidance on writing profiles that discovery finds.

.. admonition:: On the horizon: Communication MCP
   :class: note

   The Discovery MCP server (available now) already exposes ``search_for_agents`` to any
   MCP-compatible agent or client. The Communication MCP, which will expose
   ``send_collaboration_request`` and ``check_collaboration_result`` over the same
   standard interface, is planned for a near-term release. When it ships, any agent
   using any framework can connect all three tools without depending on AgentConnect
   internals.

See Also
---------

- :doc:`agent_network_setup` — wire up the hub, registry, and run loops
- :doc:`../core/agent_profile_and_capabilities` — write profiles that search finds reliably
- :doc:`../integrations/mcp/discovery_mcp` — connect ``search_for_agents`` via MCP today
- :doc:`../payments/agent_payment` — payment-gated A2A workflows
- :doc:`../monitoring/event_monitoring` — trace and observe collaboration flows
