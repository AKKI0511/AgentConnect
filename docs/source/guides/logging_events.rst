.. _logging_events:

Application Logging & Event Handling
====================================

Introduction
-----------

AgentConnect provides multiple approaches to monitor your applications:

1. **Python Logging**: For application status and component messages
2. **Callback Handlers**: For reacting to agent lifecycle events
3. **LangSmith Tracing**: For comprehensive workflow visualization (covered in :doc:`event_monitoring`)

Using AgentConnect's Logging Configuration
-----------------------------------------

AgentConnect includes a built-in logging configuration module:

.. code-block:: python

    from agentconnect.utils.logging_config import setup_logging, LogLevel

    # Quick setup with default INFO level
    setup_logging()
    
    # More granular control
    setup_logging(
        level=LogLevel.DEBUG,  # Global level
        module_levels={  # Component-specific levels
            "agentconnect.agents": LogLevel.DEBUG,
            "agentconnect.core": LogLevel.INFO,
            "langchain": LogLevel.WARNING,
        }
    )

This automatically configures colorized console output and proper formatting.

For development environments, use recommended debug levels:

.. code-block:: python

    from agentconnect.utils.logging_config import setup_logging, get_module_levels_for_development
    
    # Set up development-friendly logging levels
    setup_logging(
        level=LogLevel.INFO,
        module_levels=get_module_levels_for_development()
    )

Adding Logging to Your Components
--------------------------------

After configuring logging, use standard Python logging in your code:

.. code-block:: python

    import logging
    
    # Create a logger for your module
    logger = logging.getLogger(__name__)
    
    def my_function():
        logger.debug("Starting function")
        # Function logic here
        logger.info("Operation completed")

Using Environment Variables
-------------------------

Configure logging levels via environment variables:

.. code-block:: python
    
    # .env file
    LOG_LEVEL=DEBUG
    
    # In your code
    import os
    from agentconnect.utils.logging_config import setup_logging, LogLevel

    # Map string to enum
    level_map = {
        "DEBUG": LogLevel.DEBUG,
        "INFO": LogLevel.INFO,
        "WARNING": LogLevel.WARNING,
        "ERROR": LogLevel.ERROR,
    }
    
    log_level = level_map.get(os.getenv("LOG_LEVEL", "INFO").upper(), LogLevel.INFO)
    setup_logging(level=log_level)

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