.. _logging_events:

Application Logging & Event Handling
====================================

Introduction
-----------

AgentConnect provides multiple approaches to monitor your applications:

1. **Python Logging**: For application status and component messages
2. **Callback Handlers**: For reacting to agent lifecycle events
3. **LangSmith Tracing**: For comprehensive workflow visualization (covered in :doc:`event_monitoring`)

Logging policy
--------------

AgentConnect is a library and never configures logging. Applications (servers, CLI, MCP hosts) own logging configuration. Use standard Python logging (``logging.getLogger(__name__)``) directly in your code.

Guidance:

- Servers: rely on Uvicorn's logging configuration and your process-level settings. Registry logs use a hierarchical logger that flows through Uvicorn handlers.
- MCP: hosts own logging; MCP tools use Context logging (``ctx.info``, ``ctx.debug``, ``ctx.error``).

Example
-------

.. code-block:: python

    import logging
    logger = logging.getLogger(__name__)
    
    def my_function():
        logger.debug("Starting function")
        # Function logic here
        logger.info("Operation completed")

Using Environment Variables (servers)
------------------------------------

Servers are configured via environment variables but logging is handled by Uvicorn or your process manager. The SDK does not provide or require server logging helpers.

Handling Agent Events with Callbacks
----------------------------------

Track and react to agent events using LangChain's callback system:

.. code-block:: python

    from typing import Dict, Any
    from langchain_core.callbacks import BaseCallbackHandler

    class ToolUsageTracker(BaseCallbackHandler):
        def __init__(self):
            super().__init__()
            self.tool_counts = {}
        
        def on_tool_start(self, serialized, input_str, **kwargs):
            tool_name = serialized.get("name", "unknown")
            self.tool_counts[tool_name] = self.tool_counts.get(tool_name, 0) + 1
            
        def get_usage_report(self):
            return self.tool_counts

To use with an agent:

.. code-block:: python

    from agentconnect.agents import AIAgent
    from agentconnect.core.types import ModelProvider, ModelName, AgentIdentity
    
    # Create tracker
    usage_tracker = ToolUsageTracker()
    
    # Add to agent
    agent = AIAgent(
        agent_id="my_agent",
        name="Agent with Tracking",
        provider_type=ModelProvider.ANTHROPIC,
        model_name=ModelName.CLAUDE_3_OPUS,
        api_key="your_api_key",
        identity=AgentIdentity.create_key_based(),
        external_callbacks=[usage_tracker]
    )
    
    # After running, check stats
    await agent.run()
    print(f"Tool usage: {usage_tracker.get_usage_report()}")

Built-in Tool Tracing
-------------------

AgentConnect includes a built-in `ToolTracerCallbackHandler` for colorized console output:

.. code-block:: python

    from agentconnect.utils.callbacks import ToolTracerCallbackHandler
    
    # Create with default settings
    tool_tracer = ToolTracerCallbackHandler(
        agent_id="my_agent",
        print_tool_activity=True,
        print_reasoning_steps=True
    )
    
    # Add to agent initialization
    agent = AIAgent(
        # ... other parameters ...
        agent_id="my_agent",
        external_callbacks=[tool_tracer]
    )

When to Use Each Approach
-----------------------

* **Standard Logging**: Application status, errors, and diagnostic information
* **Callbacks**: Tool usage tracking, custom metrics, and user interface updates
* **LangSmith**: Detailed workflow debugging and token usage analysis

For most applications, combining these approaches provides comprehensive visibility. 