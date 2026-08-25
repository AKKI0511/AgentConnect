Communication Hub (Local)
=========================

.. _local_hub:

Prerequisites
-------------

Complete :doc:`../../../installation` before starting. Read :doc:`../../core_concepts` for the mental model and
:doc:`../discovery/discovery_registry_local` to understand registration before messaging.

.. admonition:: API stability notice
   :class: warning

   The ``CommunicationHub`` public API is actively evolving and will ship breaking changes without a
   deprecation period:

   - ``hub.register_agent(agent)`` / ``hub.unregister_agent(id)`` are being replaced by
     ``agent.register(hub)`` / ``agent.unregister()``.
   - ``hub.send_collaboration_request`` and ``hub.send_message_and_wait_response`` are being replaced
     by a single ``hub.request(...)`` method.
   - The ``CommunicationHub`` constructor will accept additional required arguments (queue service,
     transport, response tracker).
   - ``agent_id`` is being replaced by a DID (Decentralized Identifier) as the canonical agent
     identifier everywhere — registration, routing, and message fields.
   - ``Message`` fields ``request_id`` / ``response_to`` in metadata are being replaced by first-class
     ``correlation_id`` and ``conversation_id`` fields.

   Pin your dependency to a specific version if you need a stable surface while these land.

What Is the Communication Hub
------------------------------

``CommunicationHub`` is the message router for your agent system. Register your agents with it, and they
can send and receive messages by ID. The hub handles identity verification, message signing, and
request/response correlation so your agents do not have to.

.. admonition:: At a glance
   :class: tip

   - **One constructor argument**: ``CommunicationHub(registry)`` — local or remote registry, same API.
   - **Register once**: ``hub.register_agent(agent)`` makes the agent addressable immediately.
   - **Correlated requests**: ``hub.send_collaboration_request`` sends a task and waits for the result.
   - **Observable**: attach async handlers per-agent or globally to observe messages as they flow.
   - **No external dependencies**: fully in-process, no network, no broker required.

When To Use It
--------------

The local hub covers any scenario where your agents run in the same process:

- Building and testing a multi-agent workflow before adding infrastructure
- Running a complete agent system in a single application (web service, CLI tool, notebook)
- Prototyping collaboration patterns without deploying a registry server
- Integrating AgentConnect agents into an existing framework (LangGraph, Google ADK, CrewAI)

For agents across separate processes or machines, pair the hub with a remote registry
(:doc:`../discovery/discovery_registry_remote`) — routing stays local, discovery becomes shared.
Full remote messaging (``/inbox``, distributed queues) is on the roadmap.

Quickstart
----------

The minimum to get two agents talking:

.. code-block:: python

    import asyncio
    import os
    from dotenv import load_dotenv

    from agentconnect.prebuilt import AIAgent
    from agentconnect.team import CommunicationHub
    from agentconnect.team.directory import AgentRegistry
    from agentconnect.core.types import AgentIdentity, ModelName, ModelProvider

    async def main():
        load_dotenv()

        registry = AgentRegistry()
        hub = CommunicationHub(registry)

        agent_a = AIAgent(
            agent_id="agent-a",
            name="Agent A",
            identity=AgentIdentity.create_key_based(),
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O_MINI,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
        agent_b = AIAgent(
            agent_id="agent-b",
            name="Agent B",
            identity=AgentIdentity.create_key_based(),
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O_MINI,
            api_key=os.getenv("OPENAI_API_KEY"),
        )

        await hub.register_agent(agent_a)
        await hub.register_agent(agent_b)

        result = await hub.send_collaboration_request(
            sender_id="agent-a",
            receiver_id="agent-b",
            task_description="Summarise the benefits of async Python in two sentences.",
        )
        print(result)

    asyncio.run(main())

With the Full Ecosystem
------------------------

Registering an agent through the hub writes its profile to the registry and makes it both discoverable
and reachable in one step. Each ``AIAgent`` then gains three collaboration tools in its reasoning loop
automatically:

- **search_for_agents** — finds agents by capability using the registry
- **send_collaboration_request** — delegates a task and waits for the result
- **check_collaboration_result** — polls for a late reply from a previous request

This lets agents discover and delegate to each other autonomously. See
:doc:`../../systems/agent_toolbox` for end-to-end patterns.

Registering and Unregistering
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Returns True on success, False if the registry rejects (e.g. duplicate agent_id)
    success = await hub.register_agent(agent)

    # Cleans up handlers, removes from routing, unregisters from the registry
    await hub.unregister_agent("agent-a")

Sending Collaboration Requests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``send_collaboration_request`` returns a plain string — the receiver's reply, ready to pass back to an
LLM or surface directly to a user. It is the right call inside an agent tool, where the result feeds
into the next reasoning step:

.. code-block:: python

    result = await hub.send_collaboration_request(
        sender_id="coordinator",
        receiver_id="writer",
        task_description="Draft a 150-word product announcement for our new search feature.",
        timeout=120,    # seconds; optional — defaults to 60s, scales with task length, caps at 300s
    )
    # result is always a string — pass it straight to your LLM context or tool output
    return result

On timeout, the method still returns a useful string (containing the ``request_id``) rather than raising, so
tool wrappers never need to handle exceptions from it. If the receiver replies after the deadline, the
hub stores the message in ``hub.late_responses[request_id]`` for up to 60 seconds:

.. code-block:: python

    late = hub.late_responses.get(request_id)
    if late:
        print("Late response:", late.content)

Waiting for a Response in Application Code
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When you need the full ``Message`` object — to inspect metadata, check the message type, or branch on
the response programmatically — use ``send_message_and_wait_response``:

.. code-block:: python

    from agentconnect.core.types import MessageKind

    response = await hub.send_message_and_wait_response(
        sender_id="coordinator",
        receiver_id="analyst",
        content="Run the Q4 revenue report.",
        kind=MessageKind.REQUEST,
        metadata={"priority": "high", "quarter": "Q4-2025"},
        timeout=180,
    )
    if response:
        # response is a Message — inspect fields, route based on type, log structured data
        print(response.content, response.metadata)

With Custom Agents
-------------------

Any ``BaseAgent`` subclass registers and communicates the same way as ``AIAgent``:

.. code-block:: python

    from agentconnect.agent.base import BaseAgent
    from agentconnect.core.message import Message
    from agentconnect.core.types import AgentIdentity, AgentType, InteractionMode, MessageKind

    class SummarizerAgent(BaseAgent):

        def __init__(self):
            super().__init__(
                agent_id="summarizer",
                identity=AgentIdentity.create_key_based(),
                agent_type=AgentType.AI,
                interaction_modes=[InteractionMode.AGENT_TO_AGENT],
            )

        async def process_message(self, message: Message) -> None:
            await self.send_message(
                receiver_id=message.sender_id,
                content=f"Summary: {message.content[:100]}...",
                kind=MessageKind.RESPONSE,
                metadata={"response_to": message.metadata.get("request_id")},
            )

    await hub.register_agent(SummarizerAgent())

See :doc:`../agents/base_agent` for more information on how to build custom agents that communicate through the hub.

Observability
--------------

Per-Agent Handlers
^^^^^^^^^^^^^^^^^^^

Called for every message addressed to a specific agent:

.. code-block:: python

    async def on_writer_message(message: Message) -> None:
        print(f"[{message.kind.value}] → writer | {message.content[:80]}")

    hub.add_message_handler("writer", on_writer_message)
    hub.remove_message_handler("writer", on_writer_message)

Global Handlers
^^^^^^^^^^^^^^^^

Called for every message that passes through the hub:

.. code-block:: python

    async def audit(message: Message) -> None:
        audit_log.append({
            "id": message.id,
            "from": message.sender_id,
            "to": message.receiver_id,
            "type": message.kind.value,
            "ts": message.timestamp.isoformat(),
        })

    hub.add_global_handler(audit)
    hub.remove_global_handler(audit)

.. admonition:: Failing handlers are removed automatically
   :class: important

   If a handler raises an unhandled exception, the hub logs the error and drops that handler — it
   will not fire again. Wrap handler bodies in ``try/except`` if you need guaranteed recovery.

Message History
^^^^^^^^^^^^^^^^

.. code-block:: python

    history = hub.get_message_history()
    for msg in history:
        print(f"{msg.timestamp} | {msg.sender_id} → {msg.receiver_id}: {msg.content[:60]}")

Enabled by default. Disable for high-throughput or memory-constrained deployments via ``agentconnect.yaml``
— see `Configuration`_ below.

Inspecting the Hub
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    agents = await hub.get_all_agents()
    agent  = await hub.get_agent("writer")

    if await hub.is_agent_active("writer"):
        ...

    print(list(hub.active_agents.keys()))

Configuration
-------------

.. note::

   ``agentconnect.yaml`` is read once at process startup. See :doc:`../../configuration/sdk_configuration`
   for the file format and precedence rules.

.. code-block:: yaml

    communication:
      enable_message_history: true   # set false to reduce memory use in long-running systems

Advanced
--------

Hub with a Remote Registry
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Swap the local registry for a ``RegistryAPIClient`` and agents on this hub appear in a shared,
cross-process registry. Routing stays local:

.. code-block:: python

    from agentconnect.index.client import RegistryAPIClient

    registry = RegistryAPIClient(base_url="http://registry.internal:8000")
    hub = CommunicationHub(registry)

Driving the Hub from an External Orchestrator
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The hub is a plain async Python object with no background threads. Pass it into any orchestration
structure and call its methods directly:

.. code-block:: python

    class WorkflowRunner:
        def __init__(self, hub: CommunicationHub):
            self.hub = hub

        async def run_step(self, from_id: str, to_id: str, task: str, timeout: int = 60) -> str:
            return await self.hub.send_collaboration_request(
                sender_id=from_id,
                receiver_id=to_id,
                task_description=task,
                timeout=timeout,
            )

Watching the Collaboration Chain
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Every ``REQUEST_COLLABORATION`` message carries a ``collaboration_chain`` list in metadata. Use a
global handler to trace multi-hop delegations:

.. code-block:: python

    async def trace_chain(message: Message) -> None:
        if message.kind == MessageKind.REQUEST:
            chain = message.metadata.get("collaboration_chain", [])
            print(" → ".join(chain + [message.receiver_id]))

    hub.add_global_handler(trace_chain)

Troubleshooting
---------------

**``register_agent`` returns ``False``**

The most common cause is a duplicate ``agent_id``. Call ``await hub.unregister_agent("agent-id")``
first, or use a unique ID.

**Collaboration request times out every time**

The receiver must be actively consuming its message queue. For ``AIAgent`` this is ``await agent.run()``;
for ``BaseAgent`` subclasses, it is whatever loop calls ``process_message``.

**Agent not found during routing**

Use ``await hub.is_agent_active("agent-id")`` to confirm both sender and receiver are registered before
sending.

**Handler stops firing**

Handlers that raise unhandled exceptions are silently removed. Check logs for ``handler error`` from
``agentconnect.team.runtime``.

**Message history is always empty**

Confirm ``communication.enable_message_history`` is not ``false`` in ``agentconnect.yaml``.

Next Steps
----------

- :doc:`../../systems/agent_toolbox` — end-to-end multi-agent patterns built on the hub
- :doc:`../../systems/agent_network_setup` — bootstrap a complete system with registry + hub + agents
- :doc:`../discovery/discovery_registry_local` — search registered agents by capability before routing
- :doc:`../message_identity/message` — the ``Message`` model, types, and signing
- :doc:`../agents/base_agent` — build custom agents that communicate through the hub
- :doc:`../../configuration/sdk_configuration` — full ``agentconnect.yaml`` reference
