Guides
======

Welcome to the AgentConnect Guides! These practical, step-by-step tutorials will help you harness the power of AgentConnect to build, connect, and deploy independent AI agents for complex tasks.

.. admonition:: Who are these guides for?
   :class: note

   These guides are designed for developers looking to:
   
   - Build applications with single or multiple collaborating AI agents.
   - Integrate AgentConnect into existing systems.
   - Create autonomous workflows involving payments and external tools.
   - Understand best practices for deploying and managing AgentConnect applications.

Core Concepts & Getting Started
-----------------------------------
Build a solid foundation by understanding the core components (Registry, Hub, Capabilities, Identity) and setting up your first agent.

*   `Core Concepts <core_concepts.html>`_: Key concepts like the Agent Registry, Communication Hub, Capabilities, and Agent Identity.
*   `Your First Agent <first_agent.html>`_: Create and run a simple AI agent, configure its provider, and interact with it.
*   `Human-in-the-Loop <human_in_the_loop.html>`_: Integrate a `HumanAgent` for interactive sessions or approvals.

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Core Concepts & Getting Started

   core_concepts
   first_agent
   human_in_the_loop

Building Multi-Agent Systems
-------------------------------
Learn how to orchestrate multiple agents that discover each other dynamically and collaborate by defining capabilities and designing interaction workflows.

*   `Multi-Agent Setup <multi_agent_setup.html>`_: Registering multiple agents (AI, Human, etc.) and defining their capabilities.
*   `Collaborative Workflows <collaborative_workflows.html>`_: Design patterns for common multi-agent tasks like information gathering, task delegation, and parallel processing.

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Building Multi-Agent Systems

   multi_agent_setup
   collaborative_workflows

Advanced Agent Configuration & Security
------------------------------------------
Customize the behavior of provided agents (like `AIAgent`) and understand the framework's security mechanisms like message signing.

*   `AI Agent Deep Dive <agent_configuration.html>`_: Advanced configuration options for the `AIAgent`, including personality, interaction modes, resource limits, and error handling.
*   `Secure Agent Communication <secure_communication.html>`_: Understanding message signing and verification for secure interactions.

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Advanced Agent Configuration & Security

   agent_configuration
   secure_communication

Specialized Use Cases & Integrations
-----------------------------------------
Explore specific applications like agent payments, Telegram integration, and connecting agents to external tools via capabilities.

*   `Agent Payments <agent_payment.html>`_: Enabling and managing agent-to-agent payments.
*   `Telegram Integration <telegram_integration.html>`_: Building AI assistants accessible via Telegram.
*   `External Tools <external_tools.html>`_: Equipping agents with the ability to use external tools.

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Specialized Use Cases & Integrations

   agent_payment
   telegram_integration
   external_tools

Monitoring
------------
Observe, debug, and trace your AgentConnect applications using tools like LangSmith and custom logging.

*   `Monitoring with LangSmith <event_monitoring.html>`_: Tracing agent interactions, debugging, and analyzing performance with LangSmith.
*   `Logging & Event Handling <logging_events.html>`_: Implementing custom logging and reacting to agent events.

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Monitoring

   event_monitoring
   logging_events

Extending AgentConnect
-------------------------
Dive deeper and extend the framework by building **Custom Agents** using the `BaseAgent` abstraction (integrating frameworks like CrewAI, etc.) or adding new AI provider integrations.

*   `Advanced Guides (Coming Soon) <advanced/index.html>`_: Guides on creating custom agents, providers, and more advanced configurations.

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Extending AgentConnect

   advanced/index


.. note::
   These guides focus on practical implementation. For detailed class and method descriptions, refer to the :doc:`../api/index`. For runnable code examples, see the :doc:`../examples/index`.