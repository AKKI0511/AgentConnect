Logging & Observability
=========================

.. _logging_events:

AgentConnect gives you three layers of visibility, each firing at a different point in
the system: Python logging for library internals, hub event handlers for message flow,
and LangChain callbacks for an ``AIAgent``'s reasoning loop.

.. admonition:: At a glance
   :class: tip

   - **Python logging**: library and application diagnostics. Always available, any
     agent type.
   - **Hub event handlers**: every message the hub routes, in real time. Any agent type.
   - **LangChain callbacks**: tool calls and reasoning steps inside ``AIAgent`` only.
   - Need a hosted dashboard instead of console output? See :doc:`event_monitoring`.

Python Logging
-----------------

AgentConnect is a library and never configures logging for you. Your application
(server, CLI, MCP host) owns logging configuration; the SDK just calls
``logging.getLogger(__name__)`` and lets your handlers decide where output goes.

.. code-block:: python

    import logging
    logger = logging.getLogger(__name__)

    def my_function():
        logger.debug("Starting function")
        logger.info("Operation completed")

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Context
     - Where logging comes from
   * - Servers (``agentconnect serve ...``)
     - Uvicorn's logging configuration. Registry logs use a hierarchical logger that
       flows through Uvicorn's handlers.
   * - MCP servers
     - The host application owns logging. MCP tools log through ``ctx.info``,
       ``ctx.debug``, ``ctx.error`` on the MCP ``Context``, not Python's logging module.
   * - Your application code
     - Whatever handlers you attach. The SDK never adds its own.

Hub Event Handlers
----------------------

Attach a handler to the ``CommunicationHub`` and see every message that moves through
your system, regardless of agent type:

.. code-block:: python

    async def log_flow(message: Message) -> None:
        print(f"{message.sender_id} -> {message.receiver_id} [{message.message_type.value}]")

    hub.add_global_handler(log_flow)          # every message through the hub
    hub.add_message_handler("writer", log_flow)  # only messages addressed to "writer"

Handlers that raise an unhandled exception are logged and removed automatically; they
will not fire again for that hub. The hub also keeps an in-memory ``get_message_history()``
you can inspect directly. Full reference, including how to disable history for
high-throughput workloads: :doc:`../core/communication/local_hub` (Observability
section).

LangChain Callbacks
-----------------------

For visibility inside an ``AIAgent``'s reasoning loop, tool calls and LLM steps, pass
LangChain callback handlers via ``external_callbacks``.

**Built-in console tracer**

:class:`ToolTracerCallbackHandler <agentconnect.utils.callbacks.ToolTracerCallbackHandler>`
prints colorized, real-time tool activity and reasoning steps to the console:

.. code-block:: python

    from agentconnect.utils.callbacks import ToolTracerCallbackHandler

    tracer = ToolTracerCallbackHandler(
        agent_id="my_agent",
        print_tool_activity=True,     # tool start/end/error
        print_reasoning_steps=True,   # the LLM's thought text before each tool call
    )

    agent = AIAgent(
        agent_id="my_agent",
        external_callbacks=[tracer],
        # ... other parameters ...
    )

**Writing your own handler**

Any :class:`BaseCallbackHandler <langchain_core.callbacks.BaseCallbackHandler>`
subclass works. Useful for custom metrics rather than console output:

.. code-block:: python

    from langchain_core.callbacks import BaseCallbackHandler

    class ToolUsageTracker(BaseCallbackHandler):
        def __init__(self):
            super().__init__()
            self.tool_counts: dict[str, int] = {}

        def on_tool_start(self, serialized, input_str, **kwargs):
            name = serialized.get("name", "unknown")
            self.tool_counts[name] = self.tool_counts.get(name, 0) + 1

    tracker = ToolUsageTracker()
    agent = AIAgent(agent_id="my_agent", external_callbacks=[tracker], ...)
    # later: tracker.tool_counts

For a hosted dashboard with full trace visualization instead of console output or custom
counters, see :doc:`event_monitoring`.

Choosing an Approach
------------------------

.. list-table::
   :header-rows: 1
   :widths: 25 35 40

   * - Layer
     - Scope
     - Use when
   * - Python logging
     - Library and application internals
     - Debugging startup, config, or errors outside agent reasoning
   * - Hub event handlers
     - Every message the hub routes
     - Tracing message flow across any agent type, including custom ``BaseAgent``
   * - LangChain callbacks
     - One ``AIAgent``'s tool calls and reasoning
     - Console tracing or custom metrics scoped to a single agent's LLM loop
   * - LangSmith (:doc:`event_monitoring`)
     - Full trace visualization, hosted
     - Debugging complex multi-step or multi-agent workflows visually

Most applications combine Python logging with one of the other three, rather than all
four at once.

Next Steps
-------------

- :doc:`event_monitoring` — hosted trace visualization with LangSmith
- :doc:`../core/communication/local_hub` — full hub observability reference
- :doc:`../core/agents/ai_agent` — ``external_callbacks`` and other ``AIAgent`` parameters
