BaseAgent
=========

.. _base_agent:

.. admonition:: Status: Beta (core evolving)
   :class: warning

   BaseAgent is evolving. Expect refinements that improve agent-to-agent communication and discovery while keeping your subclassing model stable.

Prerequisites
-------------

Before you start, complete the :doc:`../../../installation` setup. If you're new to the framework, skim :doc:`../../core_concepts` for the mental model.

What Is BaseAgent
-----------------

:class:`BaseAgent <agentconnect.core.agent.BaseAgent>` is the abstract foundation for all agents in AgentConnect. It defines the core functionality every agent must implement: identity management, message handling, lifecycle control, and secure communication.

All agents—whether AI-powered (:class:`AIAgent <agentconnect.agents.AIAgent>`), human-driven (:class:`HumanAgent <agentconnect.agents.HumanAgent>`), or custom implementations—inherit from ``BaseAgent`` and override its abstract methods to provide specialized behavior.

.. admonition:: At a glance
   :class: tip

   You implement one method:
   
   - Override ``process_message(message) -> Message | None``.
   - Return a ``Message`` to respond; return ``None`` if you already sent messages or chose to ignore.
   - Use ``send_message(...)`` for proactive or multi-part replies or to contact other agents before replying.

When To Use It
--------------

Use ``BaseAgent`` directly (via subclassing) when:

- You need a custom agent type that doesn't fit the ``AIAgent`` or ``HumanAgent`` models
- You're integrating an existing framework (AutoGen, CrewAI, google ADK), wrapping provider SDKs directly (OpenAI, Anthropic), or implementing custom orchestration logic
- You want full control over message processing and workflow logic
- You're building specialized agents (e.g., database agents, API gateways, monitoring agents)

Use ``AIAgent`` or ``HumanAgent`` when:

- You need a standard AI agent powered by an LLM (OpenAI, Anthropic, etc.)
- You need human-in-the-loop approval or input capabilities

.. _core_apis:

Core APIs
---------

Implement
^^^^^^^^^

- ``process_message(message) -> Message | None``: Define how your agent reacts to incoming messages.

  - Best practice: call ``base_response = await super().process_message(message)`` first to let the base class handle verification, cooldown, and built-ins; if it returns a message, return that immediately.
  - If you return a ``Message``, it will be sent back to the sender (except ``MessageType.IGNORE``, which is not sent). If you return ``None``, the framework assumes you already handled messaging (or intentionally ignored).

Use
^^^

- ``await send_message(receiver_id, content, message_type=..., metadata=...)``: Send messages to other agents at any time (inside or outside ``process_message``) for multi-step or proactive workflows.

.. admonition:: Sending is currently fire-and-forget
   :class: important

   ``send_message(...)`` does not automatically wait for a reply today. Request/response ergonomics and correlation will become first-class in the upcoming message model update.

.. admonition:: Correlation essentials
   :class: tip

   - If inbound has ``metadata.request_id``, ``BaseAgent`` tracks it and your first reply gets ``metadata.response_to`` automatically.
   - For multi-message replies, include ``metadata={"response_to": request_id}`` on subsequent sends.
   - See :ref:`correlation_patterns` for patterns.

.. _super_vs_manual_handling:

Super vs manual handling
^^^^^^^^^^^^^^^^^^^^^^^^

You have two choices for inbound handling inside ``process_message``:

1) Use the base handling (recommended)

   - Call ``base = await super().process_message(message)`` first.
   - If it returns a message, return it immediately. This intercepts and answers common cases for you:

     * Signature verification failures → ``ERROR`` or ``COLLABORATION_RESPONSE``
     * Cooldown or cannot-receive → ``COOLDOWN`` / ``ERROR`` (or ``COLLABORATION_RESPONSE`` when appropriate)
     * Max-turns/STOP or explicit STOP → graceful end (``STOP`` or ``IGNORE``)
     * Tracks ``request_id`` so your first reply gets ``metadata.response_to`` automatically
   - Only messages not handled above fall through to your custom logic.

2) Handle everything yourself (advanced)

   - Skip calling super and implement the full set of responsibilities so the hub ecosystem continues to work:

     * Verify inbound message signatures and decide what to do on failure
     * Enforce cooldown and return ``COOLDOWN`` with ``metadata.cooldown_remaining`` when applicable
     * Respect STOP and max-turns (clean up state and respond with ``STOP`` / ``IGNORE``)
     * Correlate replies: if inbound had ``metadata.request_id``, include ``metadata.response_to`` on your first reply
     * Map collaboration requests to ``COLLABORATION_RESPONSE`` when replying to ``REQUEST_COLLABORATION``
   - This path gives you maximum control but requires carefully reproducing the base guarantees so other agents and the hub behave as expected.

How To Use It
-------------

Step 1: Create Your Agent Class
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Subclass ``BaseAgent`` and implement the ``process_message()`` method:

.. code-block:: python

    from agentconnect.core.agent import BaseAgent
    from agentconnect.core.message import Message
    from agentconnect.core.types import (
        AgentIdentity,
        AgentProfile,
        AgentType,
        Capability,
        InteractionMode,
        MessageType,
    )
    
    class EchoAgent(BaseAgent):
        """A simple agent that echoes messages back."""
        
        def __init__(self, agent_id: str, identity: AgentIdentity, name: str):
            # Create the agent profile
            profile = AgentProfile(
                agent_id=agent_id,
                agent_type=AgentType.AI,
                name=name,
                summary="Echoes messages back to sender",
                capabilities=[
                    Capability(
                        name="echo",
                        description="Repeats the message content",
                    )
                ],
            )
            
            # Initialize base agent
            super().__init__(
                agent_id=agent_id,
                identity=identity,
                interaction_modes=[InteractionMode.AGENT_TO_AGENT],
                profile=profile,
            )
        
        async def process_message(self, message: Message) -> Message | None:
            """Process incoming message and echo it back."""
            # Call base class validation first
            base_response = await super().process_message(message)
            if base_response:
                return base_response
            
            # Echo the message content back
            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=f"Echo: {message.content}",
                sender_identity=self.identity,
                message_type=MessageType.TEXT,
            )

Step 2: Register and Run
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    import asyncio
    from agentconnect.communication import CommunicationHub
    from agentconnect.core.registry import AgentRegistry
    from agentconnect.core.types import AgentIdentity
    
    async def main():
        # Initialize infrastructure
        registry = AgentRegistry()
        hub = CommunicationHub(registry)
        
        # Create identity and agent
        identity = AgentIdentity.create_key_based()
        echo = EchoAgent(agent_id="echo1", identity=identity, name="EchoBot")
        
        # Register and run
        await hub.register_agent(echo)
        agent_task = asyncio.create_task(echo.run())
        
        # ... interact with the agent ...
        
        # Cleanup
        await echo.stop()
        await hub.unregister_agent(echo.agent_id)
    
    if __name__ == "__main__":
        asyncio.run(main())

Parameters & Configuration
--------------------------

Required Parameters
^^^^^^^^^^^^^^^^^^^

- **agent_id** (*str*): Unique identifier for the agent
- **identity** (:class:`AgentIdentity`): Cryptographic identity for signing/verification
- **interaction_modes** (List[:class:`InteractionMode`]): Supported interaction patterns
- **profile** (:class:`AgentProfile`): Comprehensive agent profile for discovery

Optional Parameters
^^^^^^^^^^^^^^^^^^^

- **enable_payments** (*bool*, default: False): Enable blockchain payment capabilities (requires Coinbase AgentKit)
- **wallet_data_dir** (*str | Path*): Custom directory for wallet storage

AgentProfile Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``profile`` parameter defines how your agent is discovered. Key fields:

- **agent_id**: Must match the agent's ID
- **agent_type**: ``AgentType.AI`` or ``AgentType.HUMAN``
- **name**: Human-readable name
- **summary**: Brief one-line description
- **description**: Detailed explanation of purpose
- **capabilities**: List of :class:`Capability` objects (name, description)
- **skills**: List of :class:`Skill` objects for broader expertise areas
- **tags**: Keywords for filtering

For complete configuration details, see :doc:`../agent_profile_and_capabilities`.

Agent Lifecycle
---------------

Core Responsibilities
^^^^^^^^^^^^^^^^^^^^^

BaseAgent manages:

1. **Identity & Security**: Maintains cryptographic identity, signs outgoing messages, verifies incoming messages
2. **Message Handling**: Queues incoming messages, processes them via ``process_message()``, tracks message history
3. **Lifecycle Control**: ``run()`` starts the processing loop, ``stop()`` shuts down gracefully
4. **Communication**: ``send_message()`` routes messages through the hub, ``receive_message()`` queues messages
5. **Discovery**: Stores profile with capabilities for registry-based discovery

Typical Lifecycle
^^^^^^^^^^^^^^^^^

1. **Initialize**: Create agent with ``agent_id``, ``identity``, ``profile``, ``interaction_modes``
2. **Process**: Override ``process_message()`` to define behavior
3. **Register**: Call ``await hub.register_agent(agent)`` to join the network
4. **Run**: Start processing with ``asyncio.create_task(agent.run())``
5. **Stop**: Call ``await agent.stop()`` to clean up resources
6. **Unregister**: Remove from hub with ``await hub.unregister_agent(agent.agent_id)``

.. admonition:: Coming soon: Hub-managed queues and agent-initiated registration
   :class: note

   In upcoming releases, agents will register themselves to a hub (``agent.register(hub)``) and pull work from hub-managed queues instead of running their own event loops. The current ``run()`` model will be replaced with a worker-pull pattern for better scalability and backpressure control.

Roadmap (high-level)
--------------------

The following enhancements are planned for future releases:

- **Hub-managed queues** for per-agent scaling and backpressure
- **Agent-initiated register/unregister** to hubs; dynamic multi-hub capable
- **Message model improvements** for correlation and conversation threading
- **Standardized MCP tools** available to BaseAgent with A2A MCP
- **Composite runtime** that hosts hub endpoints together

Advanced Usage
--------------

Stateless vs Stateful Agents
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Stateless agents process each message independently:

.. code-block:: python

    async def process_message(self, message: Message) -> Message | None:
        base_response = await super().process_message(message)
        if base_response:
            return base_response
        
        # Stateless processing - no memory of past messages
        result = self.compute_response(message.content)
        return Message.create(
            sender_id=self.agent_id,
            receiver_id=message.sender_id,
            content=result,
            sender_identity=self.identity,
            message_type=MessageType.TEXT,
        )

Stateful agents track conversation history:

.. code-block:: python

    def __init__(self, ...):
        super().__init__(...)
        self.conversation_state = {}  # Store state per sender
    
    async def process_message(self, message: Message) -> Message | None:
        base_response = await super().process_message(message)
        if base_response:
            return base_response
        
        # Retrieve or initialize state for this sender
        sender_id = message.sender_id
        if sender_id not in self.conversation_state:
            self.conversation_state[sender_id] = []
        
        # Add message to history
        self.conversation_state[sender_id].append(message.content)
        
        # Generate contextual response
        context = "\n".join(self.conversation_state[sender_id])
        result = self.compute_contextual_response(context)
        
        return Message.create(
            sender_id=self.agent_id,
            receiver_id=sender_id,
            content=result,
            sender_identity=self.identity,
            message_type=MessageType.TEXT,
        )

Sending Multiple Messages
^^^^^^^^^^^^^^^^^^^^^^^^^

For tasks requiring multiple responses, send messages directly:

.. code-block:: python

    async def process_message(self, message: Message) -> Message | None:
        base_response = await super().process_message(message)
        if base_response:
            return base_response
        
        # Send acknowledgment
        await self.send_message(
            receiver_id=message.sender_id,
            content="Processing your request...",
            message_type=MessageType.TEXT,
        )
        
        # Perform work
        result = await self.perform_task(message.content)
        
        # Send final result
        await self.send_message(
            receiver_id=message.sender_id,
            content=result,
            message_type=MessageType.TEXT,
        )
        
        # Return None since we already sent messages
        return None

.. admonition:: Current Limitation: Multiple Messages
   :class: warning

   When you send multiple messages (like an acknowledgment followed by a result), each is treated as a separate message. If the requesting agent is waiting for a response (e.g., via a tool call), it will only receive the first message. The upcoming Message v2 release will add correlation IDs and conversation threading to properly handle multi-message exchanges and request/response patterns.

.. _correlation_patterns:

Message Types and Correlation (Today)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. admonition:: Note on base handling
   :class: note

   If you call ``base_response = await super().process_message(message)`` and it returns a ``Message``, return it immediately. In that case signature verification failures, cooldown responses, STOP/max-turns handling, and collaboration mapping are already handled by ``BaseAgent`` and will not reach your custom logic.

Message types (today)
"""""""""""""""""""""

- ``TEXT``: free-form message
- ``RESPONSE``: standard reply to a prior request
- ``ERROR``: error notification
- ``IGNORE``: graceful no-op/end
- ``STOP``: terminate a conversation
- ``COOLDOWN``: sender is in cooldown (see BaseAgent cooldown handling)
- ``REQUEST_COLLABORATION``: ask another agent to perform a task
- ``COLLABORATION_RESPONSE``: response to collaboration request

See the full field semantics in :doc:`../message_identity/message`.

Request/response correlation
""""""""""""""""""""""""""""

- On receive: if ``message.metadata.request_id`` exists, ``BaseAgent`` stores it internally as a pending request for that sender.
- On first send to that sender: ``send_message(...)`` will automatically include ``metadata.response_to`` set to the pending request ID, then clear the pending entry.
- If you send multiple messages (ack + final), only the first send gets the automatic ``response_to``. For subsequent sends, pass ``metadata={"response_to": request_id}`` yourself to preserve correlation.
- Returning a ``Message`` from ``process_message`` vs calling ``send_message`` both work; returning a message is a one-shot reply shortcut.

.. admonition:: Temporary correlation (will improve)
   :class: note

   In 0.4.x, correlation uses ``request_id`` (on the inbound request) and ``response_to`` (on your reply). The hub resolves the first response for a given request; additional responses are ignored unless the request has already timed out, in which case a late response may be recorded. A future message model will provide first-class correlation and conversation threading while keeping these handler patterns valid.

Collaboration request/response pattern
""""""""""""""""""""""""""""""""""""""

- When handling ``REQUEST_COLLABORATION``, reply with ``COLLABORATION_RESPONSE`` and include ``metadata.response_to`` with the original ``request_id``.
- BaseAgent already maps certain errors/limits to ``COLLABORATION_RESPONSE`` automatically when appropriate (e.g., verification failures, cooldown, max turns) so collaborators receive a structured outcome.

Pattern A — one-shot reply with correlation:

.. code-block:: python

    async def process_message(self, message: Message) -> Message | None:
        base = await super().process_message(message)
        if base:
            return base

        request_id = (message.metadata or {}).get("request_id")
        content = f"Processed: {message.content}"
        # Returning a Message triggers BaseAgent to send it; if a pending request was tracked,
        # BaseAgent will set metadata.response_to automatically on this first reply.
        return Message.create(
            sender_id=self.agent_id,
            receiver_id=message.sender_id,
            content=content,
            sender_identity=self.identity,
            message_type=MessageType.RESPONSE,
            metadata={"response_to": request_id} if request_id else None,
        )

Pattern B — ack then final (manual response_to on second send):

.. code-block:: python

    async def process_message(self, message: Message) -> Message | None:
        base = await super().process_message(message)
        if base:
            return base

        request_id = (message.metadata or {}).get("request_id")

        # 1) Acknowledge immediately (first send will auto-add response_to if tracked)
        await self.send_message(
            receiver_id=message.sender_id,
            content="Working on it...",
            message_type=MessageType.TEXT,
        )

        # ... perform work ...
        result = await self.perform_task(message.content)

        # 2) Send final result; include response_to explicitly to preserve correlation
        await self.send_message(
            receiver_id=message.sender_id,
            content=result,
            message_type=MessageType.RESPONSE,
            metadata={"response_to": request_id} if request_id else None,
        )

        return None

Pattern C — collaboration request handling:

.. code-block:: python

    async def process_message(self, message: Message) -> Message | None:
        base = await super().process_message(message)
        if base:
            return base

        if message.message_type == MessageType.REQUEST_COLLABORATION:
            # ... perform collaboration task ...
            reply = do_collaboration_logic(message.content)
            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=reply,
                sender_identity=self.identity,
                message_type=MessageType.COLLABORATION_RESPONSE,
                metadata={"response_to": (message.metadata or {}).get("request_id")},
            )
        return None


Conversation threads (multi-exchange)
"""""""""""""""""""""""""""""""""""""

Use a stable thread id to group multiple request/response messages with the same peer. Derive it once and reuse it:

.. code-block:: python

    def __init__(self, ...):
        super().__init__(...)
        self.thread_state = {}  # per-sender state

    async def process_message(self, message: Message) -> Message | None:
        base = await super().process_message(message)
        if base:
            return base

        # Derive a stable thread id for this peer
        thread_id = self._get_conversation_id(message.sender_id)
        state = self.thread_state.setdefault(
            message.sender_id, {"thread_id": thread_id, "turns": 0}
        )
        state["turns"] += 1

        # When sending messages, include thread_id in metadata for your own tracking/UI
        await self.send_message(
            receiver_id=message.sender_id,
            content="Noted. Continuing in this thread.",
            message_type=MessageType.TEXT,
            metadata={"thread_id": thread_id},  # app-level; hub ignores for now
        )
        return None

Handling incoming message types (what to do)
""""""""""""""""""""""""""""""""""""""""""""

- TEXT: free-form; route to your normal logic
- RESPONSE / COLLABORATION_RESPONSE: consume result and continue workflow
- ERROR: inspect ``metadata.error_type``, fallback or notify a human, consider retry/backoff
- COOLDOWN: read ``metadata.cooldown_remaining``; schedule a retry after that delay
- IGNORE: graceful end; close or switch strategy
- STOP: terminate the conversation and cleanup state

Example branch:

.. code-block:: python

    async def process_message(self, message: Message) -> Message | None:
        base = await super().process_message(message)
        if base:
            return base

        if message.message_type == MessageType.COOLDOWN:
            delay = int((message.metadata or {}).get("cooldown_remaining", 5))
            # schedule a retry in your own task logic
            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=f"Okay, I will retry after {delay}s.",
                sender_identity=self.identity,
                message_type=MessageType.IGNORE,
            )

        if message.message_type == MessageType.ERROR:
            # decide a fallback; example: inform a human or pick another collaborator
            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content="Acknowledged error. I'll adjust and try a different approach.",
                sender_identity=self.identity,
                message_type=MessageType.IGNORE,
            )

        if message.message_type == MessageType.IGNORE:
            # peer chose to ignore; end thread gracefully
            self.end_conversation(message.sender_id)
            return None

        # RESPONSE / COLLABORATION_RESPONSE / TEXT → continue normal handling
        return None

See also
""""""""

- :doc:`../message_identity/message`
- :doc:`../../systems/agent_toolbox`
- :doc:`ai_agent` (reference implementation using these patterns)

Where To Use BaseAgent
----------------------

In the AgentConnect Ecosystem
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- **With CommunicationHub**: All agents register with the hub for message routing
- **With AgentRegistry**: Agents are discoverable via their profiles and capabilities
- **With System Tools**: AI agents can discover and send messages to your custom agents
- **In Multi-Agent Systems**: Custom agents participate alongside AIAgents and HumanAgents

Integration Patterns
^^^^^^^^^^^^^^^^^^^^

- **Framework Integration**: Wrap LangGraph, AutoGen, or custom frameworks
- **Service Agents**: Create database agents, API gateways, monitoring agents
- **Protocol Bridges**: Connect external systems to AgentConnect
- **Custom Workflows**: Implement specialized business logic

Next Steps
----------

Now that you understand ``BaseAgent``, explore:

- :doc:`ai_agent` - See how ``AIAgent`` extends ``BaseAgent`` with LLM capabilities
- :doc:`human_agent` - Learn about human-in-the-loop integration
- :doc:`../../systems/agent_network_setup` - Build multi-agent systems
- :doc:`../../systems/agent_toolbox` - Enable agent-to-agent collaboration tools
- :doc:`../../../examples/index` - Explore runnable examples and patterns
