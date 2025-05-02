.. _event_monitoring:

Monitoring Agent Interactions with LangSmith
============================================

Introduction
-----------

Debugging and monitoring complex multi-agent systems presents unique challenges. When agents collaborate, execute tools, and make decisions autonomously, understanding the flow of information and pinpointing issues becomes critical for development and production monitoring.

AgentConnect integrates with `LangSmith <https://smith.langchain.com/>`_ to provide comprehensive observability into your agent ecosystem. LangSmith is a powerful platform designed specifically for tracing, monitoring, and debugging LLM applications.

Key benefits of using LangSmith with AgentConnect include:

* **End-to-End Workflow Visualization**: See the complete execution path of agent interactions, from initial user request through all intermediate steps to final response.

* **Tool Call Tracking**: Monitor all tool executions including collaboration tools (like ``search_for_agents``), payment tools (such as ``native_transfer``), and any custom tools you've added.

* **Error Identification**: Quickly identify where and why failures occur in complex agent workflows.

* **Resource Monitoring**: Track token usage, latency, and other performance metrics to optimize your application.

Setup and Configuration
----------------------

LangSmith integration is primarily enabled through environment variables. To enable LangSmith tracing for your AgentConnect application, add the following to your ``.env`` file:

.. code-block:: text

    # LangSmith Configuration
    LANGSMITH_TRACING=true
    LANGSMITH_API_KEY=your_langsmith_api_key
    LANGSMITH_PROJECT=AgentConnect
    LANGSMITH_ENDPOINT=https://api.smith.langchain.com

check out `LangSmith's documentation <https://docs.smith.langchain.com/administration/how_to_guides/organization_management/create_account_api_key>`_ for more information on how to create an API key

Automatic Integration
-------------------

Once you've set these environment variables, AgentConnect and LangChain will automatically capture traces of agent execution without requiring any additional code changes. AgentConnect's internal components are designed to work seamlessly with this automatic tracing system.

Every agent interaction, LLM call, and tool execution will be logged to your LangSmith project, creating a comprehensive record of your application's behavior.

What You Can See in LangSmith
----------------------------

**Trace Visualization**

LangSmith provides a visual representation of the entire interaction flow for each request or agent run, allowing you to see the big picture of how agents interact.

.. image:: /_static/langsmith_project_overview.png
   :width: 96%
   :align: center
   :alt: LangSmith project dashboard showing multiple AgentConnect traces

*Figure 1: LangSmith project dashboard showing multiple AgentConnect traces.*

**Step-by-Step Breakdown**

Each trace details the sequence of operations, including LLM calls, tool executions, and agent decision steps. This breakdown helps you understand exactly how your agent arrived at its responses or actions.

.. image:: /_static/langsmith_trace_detail.png
   :width: 96%
   :align: center
   :alt: Detailed view of a single trace showing the sequence of LLM calls and tool executions

*Figure 2: Detailed view of a single trace showing the sequence of LLM calls and tool executions.*

**Tool Usage Insights**

All tool calls are logged with their specific inputs and outputs, including:

* Built-in collaboration tools (``search_for_agents``, ``send_collaboration_request``)
* Payment tools (``native_transfer``, ``erc20_transfer``)
* Custom tools added via ``custom_tools``

This provides visibility into exactly what data is flowing between components of your system.

.. image:: /_static/langsmith_tool_call.png
   :width: 96%
   :align: center
   :alt: Detail of a tool call within a trace showing input arguments and the returned result

*Figure 3: Detail of a tool call within a trace showing input arguments and the returned result.*

**Error Debugging**

Errors within the workflow are clearly marked in the trace, showing the failing step and the error message. This makes it much easier to identify and fix issues in complex workflows.

.. image:: /_static/langsmith_error_trace.png
   :width: 96%
   :align: center
   :alt: A LangSmith trace highlighting a failed step and the associated error message

*Figure 4: A LangSmith trace highlighting a failed step and the associated error message.*

**Performance Monitoring**

LangSmith automatically tracks token counts and latency for LLM calls and overall traces. This data helps you optimize your application's performance and manage costs effectively.

Console-Based Monitoring
-----------------------

For real-time console monitoring during development, AgentConnect offers callback-based logging tools. See the :doc:`logging_events` guide for details on using the ``ToolTracerCallbackHandler`` and other logging approaches.

Summary
------

LangSmith offers powerful, largely automatic observability for AgentConnect applications when configured correctly via environment variables. This integration enables easier debugging and monitoring of complex agent behaviors, helping you develop more reliable and efficient multi-agent systems.

By combining LangSmith's comprehensive tracing with AgentConnect's flexible architecture, you gain deep insights into your agents' decision-making processes, tool usage, and collaboration patterns. This visibility is essential for both development and production monitoring of sophisticated agent-based applications. 