Examples
========

.. attention::
   **Important Notice**: The examples in this documentation have not been recently refactored to reflect several significant changes in the AgentConnect framework. For the most up-to-date examples and references, please follow the guides in the :doc:`../guides/index` section and refer to the `examples section of our GitHub repository <https://github.com/AKKI0511/AgentConnect/tree/main/examples>`_. These examples will be refactored soon to align with the latest framework changes.

This section contains examples demonstrating how to use the AgentConnect framework.

.. note::
   The example code is available in the ``examples/`` directory of the repository.
   You can run these examples directly after installing AgentConnect with the demo dependencies:
   ``poetry install --with demo``

The examples cover a range of use cases from basic to advanced scenarios:

- **Basic Example**: Start here to learn how to create simple agents and send messages
- **Custom Agent Example**: Learn how to extend the base agent classes
- **Custom Provider Example**: Connect custom AI providers to the framework
- **Multi-Agent Example**: Set up decentralized communication between multiple agents
- **Advanced Agent Example**: Build sophisticated agents with custom tools, workflows, and LangChain/LangGraph integration
- **Telegram Agent Example**: Create a Telegram AI Agent with multi-agent capabilities for natural language interactions

.. toctree::
   :maxdepth: 2
   :caption: Examples:

   basic_example
   custom_agent_example
   custom_provider_example
   multi_agent_example
   advanced_agent_example
   telegram_example
