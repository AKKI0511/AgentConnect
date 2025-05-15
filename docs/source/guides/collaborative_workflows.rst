Collaborative Workflows with Tools
=================================

.. _collaborative_workflows:

This guide explains how dynamic collaboration patterns work in AgentConnect, where agents discover and interact with each other based on capabilities rather than hardcoded identifiers.

Introduction
-----------

In the :doc:`multi_agent_setup` guide, you learned how to set up multiple agents with different capabilities. But how do agents actually find and collaborate with each other dynamically? 

The true power of AgentConnect's multi-agent systems comes from enabling agents to:

1. **Discover** other agents based on needed capabilities
2. **Delegate** tasks to the most appropriate agent
3. **Process** responses asynchronously

AgentConnect provides built-in collaboration tools that help agents perform these operations without requiring you to manually implement registry lookups and message handling. These tools are designed to be used by the agents themselves as part of their reasoning and execution flow.

Introducing Collaboration Tools
------------------------------

AgentConnect includes a set of tools specifically designed for agent-to-agent collaboration:

1. ``search_for_agents``: Finds agents based on capability requirements
2. ``send_collaboration_request``: Sends tasks to other agents and awaits responses
3. ``check_collaboration_result``: Polls for results of requests that previously timed out

These tools abstract the complexity of registry lookups and message exchanges, making it easier to build dynamic, capability-driven workflows. Typically, these tools are created and provided to agents via the :class:`PromptTools <agentconnect.prompts.PromptTools>` class, which handles their initialization with appropriate dependencies.

Finding Collaborators: ``search_for_agents``
----------------------------------------

The first step in dynamic collaboration is finding other agents that can provide needed capabilities.

Purpose
~~~~~~~

The ``search_for_agents`` tool allows an agent to find other agents by performing a **semantic search** across their comprehensive ``AgentProfile``'s. This includes fields like name, summary, description, capabilities, skills, tags, and examples. This approach is much more powerful than just matching capability names, as it can understand the semantics and context of what an agent is looking for.

Inputs
~~~~~~

- ``query: str`` (required): A natural language query describing the desired agent function, capability, skill, or general purpose. For example, "an agent that can analyze financial data" or "a creative writer for blog posts." This is used for semantic search against agent profiles.

- ``top_k: int`` (default: 5): Maximum number of agent results to return. This can be adjusted based on whether you want more options (higher value) or just the best matches (lower value).

- ``strictness: float`` (default: 0.2): Similarity threshold (0.0 to 1.0) for the semantic search. Higher values mean stricter matching. Results below this score are typically excluded.

- ``output_detail: str`` (default: "summary"): Controls the level of detail in the returned agent information:

  - ``'minimal'``: Returns basic identifiers (agent_id, name, URL, payment_address)
  - ``'summary'``: Includes minimal fields plus summary and tags
  - ``'capabilities'``: Includes summary fields plus capabilities and skills lists
  - ``'full'``: Returns all available information from the agent's profile (description, examples, version, etc.)

  The details returned for each agent depend on this parameter and the completeness of the found agent's ``AgentProfile``.

- ``include_tags: Optional[List[str]]`` (default: None): Allows filtering for agents that have at least one of the specified exact tags, in addition to the semantic query. For example, ["finance", "data-analysis"] would only return agents that have at least one of these tags.

Outputs
~~~~~~

The tool returns an ``AgentSearchOutput`` structure containing:

- ``message: str``: A summary message about the search operation (e.g., "Successfully found X agents matching your criteria" or error details).

- ``results: List[AgentSearchResultItem]``: A list of found agents. Each ``AgentSearchResultItem`` includes:

  - ``agent_id: str``: Unique identifier for the agent
  - ``similarity_score: float``: Relevance score of the agent to the query (higher is better)
  - Various fields from the agent's ``AgentProfile`` depending on the ``output_detail`` level requested, such as:

    - Basic identification: ``agent_id``, ``name``, ``url``, ``payment_address``
    - Summary information: ``summary``, ``tags``
    - Capability details: ``capabilities``, ``skills``
    - Full profile details: ``description``, ``examples``, ``version``, ``organization``, etc.

Example Usage of ``search_for_agents``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here are some examples of how an agent might use this tool:

1. **Searching for a general capability**:

   .. code-block:: json

       // Agent needs someone to write articles
       {
           "query": "an agent that can write blog posts about technology",
       }

2. **Searching with specific skills and tags**:

   .. code-block:: json

       // Agent needs a Python expert for financial data analysis  
       {
           "query": "expert in Python for financial data analysis", 
           "include_tags": ["finance", "data-analysis"]
       }
       // Agent can check if any results have a high similarity_score

3. **Requesting full details**:

   .. code-block:: json

       // Agent wants all details for top matches
       {
           "query": "image generation service", 
           "top_k": 2, 
           "output_detail": "full"
       }
       // Agent could examine capabilities, examples, and other details to choose the best match

After receiving search results, an agent would typically:

1. Check the similarity scores to ensure good matches
2. Review the capabilities and summaries of top results
3. Select one or more collaborators based on their specific needs
4. Use the ``agent_id`` to send a collaboration request/s

Importance of Rich ``AgentProfile``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The effectiveness and richness of search results heavily depend on how well other agents have defined their ``AgentProfile``'s. A detailed and descriptive profile with comprehensive capabilities, skills, examples, and appropriate tags leads to better discoverability. When creating agents for your system:

- Provide clear, descriptive summaries and descriptions
- Define capabilities with detailed descriptions
- Add relevant skills and examples
- Use appropriate tags for categorization
- Fill in as many profile fields as applicable to your agent's purpose

The more information provided in an agent's profile, the easier it will be for other agents to find it through semantic search when they need its services.

Automatic Filtering
~~~~~~~~~~~~~~~~~~

The tool automatically excludes:

- The calling agent itself
- Agents already in active conversations with the caller
- Agents with recent interaction timeouts
- Human agents by default

This filtering ensures that search results are relevant and only include agents that are appropriate for collaboration.

Internal Mechanism
~~~~~~~~~~~~~~~~

This tool leverages the ``AgentRegistry``'s semantic search capabilities (using vector embeddings) on the full ``AgentProfile``'s of registered agents. It performs deep semantic matching beyond simple keyword matching, understanding the intent and context of the search query. The tool also applies additional filtering logic to exclude inappropriate agents and provides results in a format that's easy for agents to process.

Delegating Tasks: ``send_collaboration_request``
--------------------------------------------

Once an agent has found a suitable collaborator, it can delegate a task using the ``send_collaboration_request`` tool.

Purpose
~~~~~~~

This tool sends a task description to a specific agent and waits for a response, handling the complexities of message routing and response tracking.

Inputs
~~~~~~

- ``target_agent_id`` (required): ID of the agent to collaborate with
- ``task`` (required): Description of the task to perform
- ``timeout`` (optional): Maximum wait time in seconds

Outputs
~~~~~~~

The tool returns whether the collaboration was successful, the response content (if received), a unique request ID for tracking, and any error messages. This gives the agent everything it needs to process the result or handle timeouts.

Possible Outcomes
~~~~~~~~~~~~~~~

1. **Success**: The collaborator responds within the timeout period
2. **Timeout**: The collaborator doesn't respond within the timeout
3. **Error**: Other failures during sending/processing

Internal Mechanism
~~~~~~~~~~~~~~~~

Behind the scenes, this tool uses the ``CommunicationHub``'s message routing system to deliver the request to the target agent and track responses. It handles message formatting, delivery confirmation, and timeout management automatically.

Handling Timeouts: ``check_collaboration_result``
---------------------------------------------

For long-running tasks that exceed the timeout, the system includes a ``check_collaboration_result`` mechanism to poll for late responses.

Purpose
~~~~~~~

This tool checks if a response has arrived for a request that previously timed out, allowing agents to handle asynchronous collaboration.

Inputs
~~~~~~

- ``request_id`` (required): The request ID from a timed-out collaboration

Outputs
~~~~~~~

The tool returns whether a result is available, the current status of the request, and the response content if completed. This allows agents to efficiently manage and track long-running collaborations.

Internal Mechanism
~~~~~~~~~~~~~~~~

This tool works with the ``CommunicationHub``'s tracking system to check the status of pending and completed requests. The hub maintains these records across interactions, enabling agents to reconnect with previously initiated collaborations even after timeouts.

Typical Collaboration Workflow
----------------------------

A typical capability-based collaboration follows this pattern:

1. **Identify Need**: An agent determines it needs a capability it doesn't have
2. **Search**: The agent uses ``search_for_agents`` to find other agents with the required capability
3. **Select**: The agent selects a collaborator from the search results
4. **Delegate**: The agent uses ``send_collaboration_request`` to send the task
5. **Process Response**:

   - If successful, the agent uses the response
   - If timeout, the agent stores the ``request_id`` for later checking
   - If error, the agent handles it appropriately (retry, fallback, etc.)
6. **Optional Late Check**: If there was a timeout, the agent can periodically check using ``check_collaboration_result``

Advanced Topics
-------------

**Payment Integration**

AgentConnect supports payment integration for agent-to-agent services. For details on implementing payment workflows, see the :doc:`agent_payment` guide.

**Parallel Collaborations**

For complex tasks, AgentConnect allows sending requests to multiple agents simultaneously. This pattern is particularly useful for tasks requiring diverse expertise or redundancy.

Seeing Tools in Action
--------------------

The collaboration tools described in this guide enable agents to discover and work with each other dynamically based on capabilities rather than hardcoded connections. This capability-driven approach is what makes AgentConnect particularly powerful for building flexible multi-agent systems.

To see these dynamic, capability-based collaboration patterns in action, explore these examples:

- `Research Assistant Example <https://github.com/AKKI0511/AgentConnect/blob/main/examples/research_assistant.py>`_: Shows how distinct agents (Core, Research, Markdown) with specific capabilities collaborate on research tasks. This example highlights capability definition, agent discovery, and task delegation through the collaboration tools.

- `Multi-Agent System Example <https://github.com/AKKI0511/AgentConnect/blob/main/examples/multi_agent/multi_agent_system.py>`_: Demonstrates a modular system where specialized agents (Telegram, Research, Content Processing, Data Analysis) form a collaborative network. This example showcases registry-based discovery and how the communication hub facilitates dynamic collaboration.

These examples demonstrate how the framework manages capability definition, agent discovery, and task delegation automatically in real-world scenarios.

Customizing Collaboration Mechanisms
----------------------------------

If you need to customize how agents collaborate, you can reference these key files:

- :doc:`Tools API <../api/agentconnect.prompts.tools>`: Defines the tool implementations and initialization logic
- :doc:`Registry API <../api/agentconnect.core.registry.registry_base>`: Implements the agent registry and semantic search functionality
- :doc:`Communication Hub API <../api/agentconnect.communication.hub>`: Handles message routing and collaboration request processing

These files contain the implementation details for the collaboration tools described in this guide.

Next Steps
---------

To build on your understanding of agent collaboration:

- Learn about integrating external tools in :doc:`external_tools`
- Explore payment options in :doc:`agent_payment`
- Understand monitoring options in :doc:`event_monitoring` 