LangSmith Tracing
====================

.. _event_monitoring:

Point `LangSmith <https://smith.langchain.com/>`_ at your ``AIAgent`` with four
environment variables, and every LLM call, tool call, and reasoning step traces
automatically. No code changes.

.. admonition:: At a glance
   :class: tip

   - Environment variables only. No SDK code changes.
   - Traces every tool call, including collaboration tools, payment tools, and any
     ``custom_tools`` you added.
   - Complements, not replaces, console-based tracing. See
     :doc:`logging_events` for that without a LangSmith account.

Setup
--------

Add these to your ``.env`` file:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Variable
     - Value
   * - ``LANGSMITH_TRACING``
     - ``true``
   * - ``LANGSMITH_API_KEY``
     - Your LangSmith API key. See the `LangSmith docs
       <https://docs.smith.langchain.com/>`_ for how to create one.
   * - ``LANGSMITH_PROJECT``
     - Any project name, created automatically on first trace.
   * - ``LANGSMITH_ENDPOINT``
     - ``https://api.smith.langchain.com``

.. code-block:: text

    LANGSMITH_TRACING=true
    LANGSMITH_API_KEY=your_langsmith_api_key
    LANGSMITH_PROJECT=AgentConnect
    LANGSMITH_ENDPOINT=https://api.smith.langchain.com

Set these before starting your process. Changing them after agents are already running
has no effect.

What You'll See
-------------------

Every trace shows the complete path a request took, one agent run, expandable into
every LLM and tool call inside it:

.. image:: /_static/langsmith_project_overview.png
   :width: 96%
   :align: center
   :alt: LangSmith project dashboard showing multiple AgentConnect traces

*Project view: every agent run, listed as a trace.*

Open a trace to see the step-by-step breakdown, LLM calls, tool executions, and the
decisions in between:

.. image:: /_static/langsmith_trace_detail.png
   :width: 96%
   :align: center
   :alt: Detailed view of a single trace showing the sequence of LLM calls and tool executions

*Trace detail: the full sequence behind one response.*

Every tool call is logged with its inputs and outputs, built-in collaboration tools
(``search_for_agents``, ``send_collaboration_request``), payment tools
(``native_transfer``, ``erc20_transfer``), and anything passed via ``custom_tools``:

.. image:: /_static/langsmith_tool_call.png
   :width: 96%
   :align: center
   :alt: Detail of a tool call within a trace showing input arguments and the returned result

*Tool call detail: exact inputs and outputs.*

Failures are marked at the step where they happened, with the error message attached:

.. image:: /_static/langsmith_error_trace.png
   :width: 96%
   :align: center
   :alt: A LangSmith trace highlighting a failed step and the associated error message

*A failed step, isolated in the trace.*

Token counts and latency are tracked automatically on every LLM call and trace, useful
for cost and performance tuning without adding any instrumentation yourself.

Troubleshooting
-------------------

**Nothing shows up in LangSmith**

Confirm ``LANGSMITH_TRACING=true`` was set before the process started, and that
``LANGSMITH_API_KEY`` is valid for the project named in ``LANGSMITH_PROJECT``.

**Traces are incomplete or missing tool calls**

Custom tools need clear names and docstrings to show up meaningfully in a trace; see
:doc:`../core/agents/ai_agent` for tool-writing guidance. A trace reflects exactly what
ran, if a tool was never called, it won't appear.

Next Steps
-------------

- :doc:`logging_events` — console-based logging and callbacks, no LangSmith account
  needed
- :doc:`../core/agents/ai_agent` — ``custom_tools`` and other ``AIAgent`` parameters
