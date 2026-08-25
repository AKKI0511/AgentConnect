Messages
========

.. _message:

.. admonition:: Actively evolving interface
   :class: warning

   The ``Message`` model and ``MessageKind`` vocabulary are being redesigned as part of a planned v1 architecture. Several things will change before the API locks:

   - **Fewer, clearer message types.** The current 13-type set is being consolidated into a smaller, more intuitive vocabulary. Types that map to protocol internals will be removed from the developer surface.
   - **First-class correlation.** Request/response tracking currently relies on ``metadata["request_id"]`` / ``metadata["response_to"]`` conventions. These are moving to dedicated, typed fields on ``Message`` itself.
   - **Typed payloads.** ``content`` (a raw string) is evolving into a structured payload that can carry strings, dicts, or lists natively.
   - **DID-based addressing.** ``sender_id`` and ``receiver_id`` are moving from plain agent IDs to Decentralized Identifiers (DIDs) as the canonical address form.
   - **Ergonomic reply helpers.** The API will gain convenience methods (e.g., ``message.reply(...)``) so agents can construct responses without manually mirroring routing fields.

   Current patterns remain usable but expect a migration when the new model ships. See :doc:`identity` for the parallel identity changes.

:class:`Message <agentconnect.core.message.Message>` is the single envelope for all agent communication in AgentConnect - text, task delegation, errors, and control signals all travel as a ``Message``. It carries the payload, routing addresses, a type that tells the hub and agents how to handle it, and a signature the hub verifies before delivery.

You rarely construct a ``Message`` directly. Inside a ``BaseAgent`` subclass, ``send_message()`` handles creation and signing. When building a custom response, use ``Message.create()``.

Creating a Message
------------------

The most common pattern is constructing a reply inside ``process_message()``:

.. code-block:: python

    from agentconnect.core.message import Message
    from agentconnect.core.types import MessageKind

    async def process_message(self, message: Message) -> Message | None:
        base = await super().process_message(message)
        if base:
            return base

        return Message.create(
            sender_id=self.agent_id,
            receiver_id=message.sender_id,
            content="Task complete.",
            sender_identity=self.identity,
            kind=MessageKind.RESPONSE,
            metadata={"response_to": message.metadata.get("request_id")},
        )

For fire-and-forget or multi-step sends, use ``send_message()``. It calls ``Message.create()`` internally using ``self.identity``:

.. code-block:: python

    await self.send_message(
        receiver_id="analyst",
        content="Run Q4 revenue analysis.",
        kind=MessageKind.REQUEST,
        metadata={"priority": "high"},
    )

See :doc:`../agents/base_agent` for the full set of patterns including multi-message replies and correlation.

.. admonition:: Signing is automatic
   :class: tip

   Every ``Message`` is signed at creation. The hub verifies the signature before delivery. No per-agent security code required. See :doc:`identity` for how agent keys work.

MessageKind Reference
---------------------

The type controls how the hub routes the message and what the receiving agent is expected to do.
Branch on ``message.kind`` inside ``process_message()``.

.. rubric:: Normal Flow

.. list-table::
   :header-rows: 1
   :widths: 22 39 39

   * - Type
     - When sending
     - When receiving
   * - ``TEXT``
     - Free-form exchange. The default. Use for conversational messages or status updates that do not need request/response tracking.
     - Process ``message.content`` normally. Reply with ``TEXT`` or ``RESPONSE``.
   * - ``COMMAND``
     - Imperative instruction. Semantic signal only — no built-in enforcement.
     - Execute the instruction from ``message.content``; reply with ``RESPONSE`` or acknowledge with ``TEXT``.
   * - ``RESPONSE``
     - Reply to a prior ``TEXT`` or ``COMMAND``. Include ``metadata["response_to"]`` pointing to the original ``request_id``.
     - Consume the result. Match to your pending request via ``message.metadata.get("response_to")``.

.. rubric:: Collaboration

.. list-table::
   :header-rows: 1
   :widths: 22 39 39

   * - Type
     - When sending
     - When receiving
   * - ``REQUEST_COLLABORATION``
     - Delegate a task to another agent. The hub auto-appends sender to ``metadata["collaboration_chain"]`` and sets ``metadata["original_sender"]`` on the first hop.
     - Execute the task. Reply with ``COLLABORATION_RESPONSE`` and set ``metadata={"response_to": message.metadata.get("request_id")}`` so the hub can resolve the result.
   * - ``COLLABORATION_RESPONSE``
     - Reply to a delegation. Always include ``metadata["response_to"]``. This is also what ``BaseAgent`` automatically produces when an error, cooldown, or limit occurs mid-collaboration.
     - Result is in ``message.content``. If ``metadata.get("original_message_type")`` is set (``"ERROR"``, ``"COOLDOWN"``, ``"STOP"``), the collaboration hit a limit — handle accordingly.
   * - ``COLLABORATION_ERROR``
     - Delegation failed completely. Include a description in ``content`` and details in ``metadata``.
     - Log the failure. Retry with a different agent, fall back, or escalate.

.. rubric:: Control Signals

.. list-table::
   :header-rows: 1
   :widths: 22 39 39

   * - Type
     - When sending
     - When receiving
   * - ``STOP``
     - End a conversation cleanly. Also triggered when the sender includes ``__EXIT__`` anywhere in ``content``.
     - ``BaseAgent`` handles automatically: calls ``end_conversation()`` and returns ``IGNORE``. Manual override: clean up state, do not reply.
   * - ``IGNORE``
     - Return from ``process_message()`` to silently end a thread. ``BaseAgent`` discards it before routing — no message reaches the sender.
     - Not receivable from a well-behaved agent; consumed before delivery.
   * - ``COOLDOWN``
     - Auto-produced by ``BaseAgent`` when the agent's token budget is exhausted. Set ``metadata["cooldown_remaining"]`` to the seconds remaining.
     - Back off. Read ``message.metadata.get("cooldown_remaining")`` and retry after that many seconds.
   * - ``SYSTEM``
     - **Do not send from application code.** Hub-internal only. Bypasses identity verification and signature checking.
     - May appear in ``hub.get_message_history()`` for debugging — ignore.

.. note::

   ``VERIFICATION``, ``CAPABILITY``, and ``PROTOCOL`` are reserved for internal framework handshaking. Do not send them from application code; they may appear in message history.

Related Types
-------------

These types from :mod:`agentconnect.core.types` directly influence how messages are routed and delivered.

InteractionMode
^^^^^^^^^^^^^^^

Set on each agent during initialization. The hub checks mode compatibility on every delivery — if sender and receiver share no common mode, routing fails before the message reaches the receiver.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Value
     - Meaning
   * - ``HUMAN_TO_AGENT``
     - Used for human ↔ agent exchanges. Set on both ``HumanAgent`` and any ``AIAgent`` that should accept human input.
   * - ``AGENT_TO_AGENT``
     - Used for autonomous agent ↔ agent exchanges. Required on both sides for collaboration flows (``REQUEST_COLLABORATION`` / ``COLLABORATION_RESPONSE``).

Most agents declare both modes so they can participate in either type of exchange:

.. code-block:: python

    from agentconnect.core.types import InteractionMode

    interaction_modes=[InteractionMode.HUMAN_TO_AGENT, InteractionMode.AGENT_TO_AGENT]

VerificationStatus
^^^^^^^^^^^^^^^^^^

Tracks the state of an agent's cryptographic identity. The hub checks this on both the sender and receiver before verifying the message signature. A message from or to an agent that is not ``VERIFIED`` is rejected before delivery.

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Value
     - Meaning
   * - ``PENDING``
     - Default state after identity creation. Messages involving this agent will fail hub routing until verification succeeds.
   * - ``VERIFIED``
     - Identity confirmed. Full message delivery and signature verification work normally. ``AgentIdentity.create_key_based()`` sets this automatically.
   * - ``FAILED``
     - Verification failed. The agent cannot send or receive until its identity is recreated.

In practice you never set this manually — ``AgentIdentity.create_key_based()`` produces a ``VERIFIED`` identity out of the box. See :doc:`identity` for details.

Metadata Conventions
--------------------

``message.metadata`` is an open ``dict``. The framework reads and writes specific keys; anything else is passed through untouched.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Set by / meaning
   * - ``request_id``
     - Hub — identifies an outbound request for correlation
   * - ``response_to``
     - Agent — points to the ``request_id`` this message is answering
   * - ``collaboration_chain``
     - Hub — ordered list of agent IDs that have handled this request across hops
   * - ``original_sender``
     - Hub — first agent that initiated the chain; preserved across hops
   * - ``cooldown_remaining``
     - BaseAgent — seconds until the rate-limited agent is available again
   * - ``error_type``
     - BaseAgent — ``"verification_failed"`` or ``"cannot_receive"`` on error messages
   * - ``original_message_type``
     - BaseAgent — the true type (``"ERROR"``, ``"COOLDOWN"``, ``"STOP"``) when wrapped inside a ``COLLABORATION_RESPONSE``

Any other keys you add are your own — use them for priority flags, thread IDs, payment context, or application-specific data.

Next Steps
----------

- :doc:`identity` — how agent keys and DIDs power the signing behind every message
- :doc:`../communication/local_hub` — how the hub uses ``MessageKind`` and metadata during routing and delivery
- :doc:`../agents/base_agent` — full guide to building agents that send and receive messages
- :doc:`../../systems/agent_toolbox` — end-to-end A2A patterns built on ``REQUEST_COLLABORATION``
