HumanAgent
==========

.. _human_agent:

Prerequisites
-------------

Before you start, complete the :doc:`../../../installation` setup. If you're new to the framework, skim :doc:`../../core_concepts` for the mental model.

What Is HumanAgent
------------------

:class:`HumanAgent <agentconnect.prebuilt.HumanAgent>` is a ready-to-use, terminal-based agent that extends :class:`BaseAgent <agentconnect.agent.base.BaseAgent>` to bring humans into agent workflows. It provides a simple CLI for real-time input/output and behaves as a first-class agent in the ecosystem (registration, routing, verification).

.. admonition:: At a glance
   :class: tip

   - Start a direct 1:1 terminal chat with ``start_interaction()``
   - Run as a normal agent with ``run()`` and receive messages routed by the hub
   - Use ``send_message()`` to contact any other agent (human or AI) via the hub

When To Use It
--------------

Use ``HumanAgent`` when you need:

- A human to review or approve AI agent outputs before a workflow proceeds
- Interactive debugging or demos with live agents in a terminal
- A human participant in a multi-agent workflow

Use a custom :class:`BaseAgent <agentconnect.agent.base.BaseAgent>` subclass instead when you need a non-terminal interface (web UI, Slack, email) or fully custom input/response logic. See :ref:`custom_human_agent_impl` for how to extend ``HumanAgent`` for those cases.

How To Use It
-------------

``HumanAgent`` supports three interaction patterns: direct 1:1 chat, passive hub participation, and proactive messaging.

Direct Chat (``start_interaction``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Start a dedicated, interactive terminal session between a human and an AI agent:

.. code-block:: python

    import asyncio, os
    from dotenv import load_dotenv
    from agentconnect.prebuilt import AIAgent, HumanAgent
    from agentconnect.team import CommunicationHub
    from agentconnect.team.directory import AgentRegistry
    from agentconnect.core.types import AgentIdentity, ModelProvider, ModelName

    async def main():
        load_dotenv()
        registry = AgentRegistry()
        hub = CommunicationHub(registry)

        human = HumanAgent(
            agent_id="human_01",   # Must start with "human_"
            name="Alice",
            identity=AgentIdentity.create_key_based(),
        )
        ai = AIAgent(
            agent_id="assistant_01",
            name="Assistant",
            identity=AgentIdentity.create_key_based(),
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O_MINI,
            api_key=os.getenv("OPENAI_API_KEY"),
        )

        await hub.register_agent(human)
        await hub.register_agent(ai)

        ai_task = asyncio.create_task(ai.run())
        try:
            await human.start_interaction(ai)  # Blocks until exit/quit/bye
        finally:
            await ai.stop()
            await hub.unregister_agent(human.agent_id)
            await hub.unregister_agent(ai.agent_id)

    if __name__ == "__main__":
        asyncio.run(main())

.. admonition:: Standalone vs Connected
   :class: tip

   ``start_interaction()`` is interactive and blocks until exit. Register both agents with the hub first so routing, verification, and capabilities work as expected.

Hub Participant (``run``)
^^^^^^^^^^^^^^^^^^^^^^^^^

Register the human as a normal agent and start ``run()``. Any agent that knows the human's ``agent_id`` can send messages to them through the hub:

.. code-block:: python

    human = HumanAgent(
        agent_id="human_reviewer",
        name="Reviewer",
        identity=AgentIdentity.create_key_based(),
    )
    ai = AIAgent(
        agent_id="analyst_01",
        name="Analyst",
        identity=AgentIdentity.create_key_based(),
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O_MINI,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    await hub.register_agent(human)
    await hub.register_agent(ai)

    # Start agent's processing loo
    human_task = asyncio.create_task(human.run())
    ai_task = asyncio.create_task(ai.run())

    # Routes via the hub—no direct reference to the human agent needed
    await ai.send_message(
        receiver_id="human_reviewer",
        content="I've completed my analysis. Please review and approve.",
        kind=MessageKind.EVENT,
    )
    # At this point, the human will see the message in their terminal
    # and will be prompted to respond. The script will wait at this point.

.. admonition:: Routing via hub
   :class: important

   Agents do not need direct references to each other—messages are routed by ``agent_id`` through the :class:`CommunicationHub <agentconnect.team.CommunicationHub>`.

When a message arrives, the terminal displays the sender and content and prompts for a response. The human's reply is routed back through the hub to the sender.

Proactive Messaging (``send_message``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use ``send_message`` to contact any registered agent at any point without waiting for an incoming message:

.. code-block:: python

    await human.send_message(
        receiver_id="analyst_01",
        content="Please run a fresh analysis on today's data.",
    )

Parameters & Configuration
--------------------------

Required
^^^^^^^^

- **agent_id** (*str*): Unique identifier for the agent
- **name** (*str*): Human-readable name
- **identity** (:class:`AgentIdentity`): Cryptographic identity used to sign/verify

.. note::

    The ``agent_id`` for ``HumanAgent`` must have a prefix of ``human_`` for distinction.

Optional
^^^^^^^^

- **organization** (*str*, optional): Organization or entity the human represents
- **response_callbacks** (List[Callable], optional): Called after each ``send_message()`` with ``{"receiver_id", "content", "kind", "timestamp"}``

**Effects**

- A profile is created automatically with ``AgentType.HUMAN`` and capabilities ``text_interaction`` and ``command_execution`` for discovery/routing
- Identity is used to sign outgoing messages; inbound messages are verified before prompting

Terminal Behavior
-----------------

``start_interaction`` mode
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   Human Agent human_01 starting interaction with assistant_01
   Exit with 'exit', 'quit', or 'bye'
   Loading...

   You: Hello, can you summarize the project status?
   ----------------------------------------
   Assistant:
   Here is the current project status summary...
   ----------------------------------------

   You: exit

- Type any text → sent as a ``TEXT`` message to the target agent
- ``exit``, ``quit``, or ``bye`` → sends a ``STOP`` message and ends the session

``run`` mode
^^^^^^^^^^^^^

.. code-block:: text

   analyst_01:
   I've completed my analysis. Please review and approve.
   ----------------------------------------
   Type your response or use these commands:
   - 'exit', 'quit', or 'bye' to end the conversation
   - Press Enter without typing to skip responding

   You:


Behavior notes:

- Typing a response sends a normal ``TEXT`` message back to the sender
- Pressing Enter skips responding
- ``exit|quit|bye`` ends the conversation (a ``STOP`` is sent)
- If the peer is in cooldown or an error occurs, HumanAgent displays the notice and stays interactive

Advanced Usage
--------------

.. _response_callbacks:

Response Callbacks
^^^^^^^^^^^^^^^^^^

Track human responses programmatically:

.. code-block:: python

    def audit_log(response_data: dict) -> None:
        print(f"[AUDIT] -> {response_data['receiver_id']}: {response_data['content'][:80]}")

    human = HumanAgent(
        agent_id="human_reviewer",
        name="Reviewer",
        identity=AgentIdentity.create_key_based(),
        response_callbacks=[audit_log],
    )

Callback Data
"""""""""""""

The callback receives a dictionary with:

- ``receiver_id``: Agent receiving the human's message
- ``content``: Text content of the response
- ``message_type``: Message type (TEXT, STOP, etc.)
- ``timestamp``: When the response was sent

Managing Callbacks
""""""""""""""""""

Add or remove callbacks at runtime:

.. code-block:: python

    human.add_response_callback(audit_log)
    human.remove_response_callback(audit_log)

.. _custom_human_agent_impl:

Custom HumanAgent Implementations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Subclass ``HumanAgent`` and override ``process_message()`` to replace or augment the terminal with any other input mechanism: web UIs, Slack bots, email approvals, mobile push, and more.

Overriding ``process_message()``
""""""""""""""""""""""""""""""""

Two patterns cover most cases.

**Pattern 1: Augment terminal behavior**

Keep the standard terminal I/O but add logic before or after it:

.. code-block:: python

    from agentconnect.prebuilt import HumanAgent
    from agentconnect.core.message import Message
    from typing import Optional

    class LoggingHumanAgent(HumanAgent):
        async def process_message(self, message: Message) -> Optional[Message]:
            # Standard terminal I/O; includes BaseAgent validation
            response = await super().process_message(message)
            if response:
                self._audit(response)  # Custom post-processing
            return response

**Pattern 2: Replace terminal I/O with a custom interface**

Call ``super(HumanAgent, self)`` to jump directly to ``BaseAgent`` validation (signature verification, cooldown, STOP handling) and provide your own input source instead of the terminal:

.. code-block:: python

    from agentconnect.prebuilt import HumanAgent
    from agentconnect.core.message import Message
    from agentconnect.core.types import MessageKind
    from typing import Optional

    class CustomInterfaceAgent(HumanAgent):
        async def process_message(self, message: Message) -> Optional[Message]:
            # BaseAgent validation only—no terminal I/O
            base_response = await super(HumanAgent, self).process_message(message)
            if base_response:
                return base_response

            response_text = await self._get_response_from_custom_interface(message)
            if not response_text:
                return None

            return Message.create(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                content=response_text,
                sender_identity=self.identity,
                kind=MessageKind.EVENT,
            )

        async def _get_response_from_custom_interface(
            self, message: Message
        ) -> Optional[str]:
            # Post to a webhook, query a web API, read from a queue, etc.
            ...

.. admonition:: Which super() to call
   :class: tip

   - ``await super().process_message(message)`` — delegates to ``HumanAgent`` (keeps terminal I/O)
   - ``await super(HumanAgent, self).process_message(message)`` — skips ``HumanAgent``, calls ``BaseAgent`` directly (no terminal I/O, full lifecycle handling preserved)

Example: Web-Based Approval Agent
""""""""""""""""""""""""""""""""""

.. dropdown:: Full WebApprovalAgent implementation (click to expand)
   :color: primary
   :icon: code

   Stores each incoming request in memory, waits for a web UI to submit the decision via ``submit_approval()``, then returns the result to the requesting agent.

   .. code-block:: python

       import asyncio
       from typing import Optional
       from agentconnect.prebuilt import HumanAgent
       from agentconnect.core.message import Message
       from agentconnect.core.types import AgentIdentity, MessageKind

       class WebApprovalAgent(HumanAgent):
           def __init__(
               self,
               agent_id: str,
               name: str,
               identity: AgentIdentity,
               approval_timeout: int = 300,
               **kwargs,
           ):
               super().__init__(agent_id, name, identity, **kwargs)
               self.pending_approvals: dict = {}
               self.approval_timeout = approval_timeout

           async def process_message(self, message: Message) -> Optional[Message]:
               base_response = await super(HumanAgent, self).process_message(message)
               if base_response:
                   return base_response

               request_id = f"{message.sender_id}_{message.timestamp}"
               approval_event = asyncio.Event()
               self.pending_approvals[request_id] = {
                   "message": message,
                   "event": approval_event,
                   "response": None,
               }

               # In production: write to a database, fire a webhook, send a notification.

               try:
                   await asyncio.wait_for(
                       approval_event.wait(), timeout=self.approval_timeout
                   )
                   response_content = self.pending_approvals[request_id]["response"]
                   del self.pending_approvals[request_id]
                   return Message.create(
                       sender_id=self.agent_id,
                       receiver_id=message.sender_id,
                       content=response_content,
                       sender_identity=self.identity,
                       kind=MessageKind.EVENT,
                   )

               except asyncio.TimeoutError:
                   del self.pending_approvals[request_id]
                   return Message.create(
                       sender_id=self.agent_id,
                       receiver_id=message.sender_id,
                       content="Approval request timed out",
                       sender_identity=self.identity,
                       kind=MessageKind.ERROR,
                       metadata={"reason": "timeout"},
                   )

           def submit_approval(self, request_id: str, response: str) -> bool:
               """Called by your web framework when the human submits a decision."""
               if request_id not in self.pending_approvals:
                   return False
               self.pending_approvals[request_id]["response"] = response
               self.pending_approvals[request_id]["event"].set()
               return True

   **Usage:**

   .. code-block:: python

       web_agent = WebApprovalAgent(
           agent_id="human_web_approver",
           name="Web Approver",
           identity=AgentIdentity.create_key_based(),
           approval_timeout=600,
       )
       await hub.register_agent(web_agent)
       web_task = asyncio.create_task(web_agent.run())

       # When your web API receives a decision:
       web_agent.submit_approval(request_id, "approved")

   See :doc:`../message_identity/message` for the full ``Message`` API and available message types.

Other Human-in-the-Loop Patterns
"""""""""""""""""""""""""""""""""

Any interface that asynchronously delivers a human response maps onto Pattern 2:

- **Slack / Discord**: Post to a channel; wait for an emoji reaction or thread reply
- **Email approval**: Send with unique approve/reject links; wait for webhook callback
- **Mobile push**: Send via Firebase/APNs; await response from mobile backend
- **Database queue**: Write the request; poll or listen for status
- **Voice call**: Initiate via Twilio; capture DTMF tones (1 = approve, 2 = reject)

Implementation Notes
""""""""""""""""""""

When building a custom ``HumanAgent``:

- Call ``await super(HumanAgent, self).process_message(message)`` first. Return its result immediately if non-``None``
- Handle timeouts—return ``MessageKind.ERROR`` with ``metadata={"reason": "timeout"}``
- Clean up pending entries to prevent memory leaks

.. _human_agent_roadmap:

Roadmap & Compatibility Notes
------------------------------

The following ``HumanAgent``-specific changes are planned for upcoming releases. Current usage patterns remain valid during the transition.

**Identity (future):**

DID will become the canonical agent identifier (``agent_id == identity.did``). The ``"human_"`` prefix convention will evolve—agent type will be carried in the profile rather than the ID string. A migration guide will accompany this change.

**Lifecycle (future):**

``BaseAgent.run()`` and its internal message queue will be replaced by a hub-managed mailbox with worker pulls. The terminal interaction experience stays equivalent. Hub registration will shift from ``hub.register_agent(agent)`` to agent-initiated ``agent.register(hub)``.

**CLI-first human interaction (planned):**

``agentconnect human chat --to <agent_id>`` and ``agentconnect human send --to <agent_id> "message"`` are planned CLI commands backed by a ``HubClient``. Humans will be able to participate in a running ecosystem without embedding Python code or sharing the agent process.

**Message model (future):**

Message v2 adds first-class ``correlation_id`` and typed payloads. The ``process_message`` override patterns shown here remain valid. The ``Message`` class will gain convenience reply methods (``message.reply()``, ``message.reply_text()``) that simplify constructing responses.

Next Steps
----------

Now that you understand ``HumanAgent``, explore:

- :doc:`base_agent` - The abstract foundation and custom agent patterns
- :doc:`ai_agent` - AI-powered agents with built-in collaboration tools
- :doc:`../../systems/agent_network_setup` - Building multi-agent systems with human oversight
- :doc:`../../systems/agent_toolbox` - Designing workflows with approval checkpoints
- :doc:`../message_identity/message` - Message types, construction, and semantics
- :doc:`../../../examples/index` - Complete runnable examples
