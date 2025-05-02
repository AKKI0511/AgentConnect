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

These tools abstract the complexity of registry lookups and message exchanges, making it easier to build dynamic, capability-driven workflows. Typically, these tools are created and provided to agents via the ``PromptTools`` class, which handles their initialization with appropriate dependencies.

Finding Collaborators: ``search_for_agents``
----------------------------------------

The first step in dynamic collaboration is finding other agents that can provide needed capabilities.

Purpose
~~~~~~~

The ``search_for_agents`` tool allows an agent to search the registry for other agents offering specific capabilities. It performs semantic search on capability descriptions, making it more flexible than exact name matching.

Inputs
~~~~~~

- ``capability_name`` (required): The name or description of the capability needed
- ``limit`` (optional): Maximum number of agents to return
- ``similarity_threshold`` (optional): Minimum similarity score for matching

Outputs
~~~~~~~

The tool returns a structured result containing matching agent IDs, their capabilities, and payment addresses (if available). This makes it easy for the agent to decide which collaborator to work with based on their specific requirements.

Automatic Filtering
~~~~~~~~~~~~~~~~~~

The tool automatically excludes the calling agent itself, agents already in active conversations, agents with recent interaction timeouts, and human agents by default.

Internal Mechanism
~~~~~~~~~~~~~~~~

This tool leverages the ``AgentRegistry``'s semantic search capabilities to find agents based on capability descriptions. It applies additional filtering logic to exclude inappropriate agents and provides results in a format that's easy for agents to process.

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