.. AgentConnect documentation master file, created by
   sphinx-quickstart on Thu Mar 13 13:21:07 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. raw:: html

   <div align="center">   
   <h1>AgentConnect</h1>
   
   <p><em>A Decentralized Framework for Autonomous Agent Collaboration</em></p>
   
   <p><strong>Build and connect independent AI agents that discover, interact, and collaborate securely.</strong></p>
   
   <p>
   <a href="#installation">Installation</a> •
   <a href="#quick-start">Quick Start</a> •
   <a href="#examples">Examples</a> •
   <a href="#documentation">Documentation</a>
   </p>
   </div>

Overview
========

AgentConnect is a revolutionary framework for building and connecting *independent* AI agents. Unlike traditional multi-agent systems that operate within a single, centrally controlled environment, AgentConnect enables the creation of a *decentralized network* of autonomous agents that can:

* **Operate Independently:** Each agent is a self-contained system with its own internal logic
* **Discover Each Other Dynamically:** Agents find each other based on capabilities, not pre-defined connections
* **Communicate Securely:** Built-in message signing, verification, and standardized protocols
* **Collaborate on Complex Tasks:** Request services, exchange data, and work together to achieve goals
* **Scale Horizontally:** Support thousands of independent agents in a decentralized ecosystem

Why AgentConnect?
----------------

* **Beyond Hierarchies:** Break free from centrally controlled multi-agent systems
* **True Agent Autonomy:** Build agents that are independent and interact with any agent in the network
* **Dynamic Discovery:** The network adapts as agents join, leave, and update capabilities
* **Secure Interactions:** Cryptographic verification ensures trustworthy communication
* **Unprecedented Scalability:** Designed for thousands of interconnected agents
* **Extensible Architecture:** Easily integrate custom agents, capabilities, and protocols

Key Features
=============

.. raw:: html

   <div class="feature-grid">
     <div class="feature-card">
       <h3>🤖 Dynamic Agent Discovery</h3>
       <ul>
         <li>Capability-based matching</li>
         <li>Flexible agent network</li>
         <li>No pre-defined connections</li>
       </ul>
     </div>
     <div class="feature-card">
       <h3>⚡ Decentralized Communication</h3>
       <ul>
         <li>Secure message routing</li>
         <li>No central control</li>
         <li>Reliable message delivery</li>
       </ul>
     </div>
     <div class="feature-card">
       <h3>⚙️ Autonomous Agents</h3>
       <ul>
         <li>Independent operation</li>
         <li>Own processing loop</li>
         <li>Complex internal structure</li>
       </ul>
     </div>
   </div>
   
   <div class="feature-grid">
     <div class="feature-card">
       <h3>🔒 Secure Communication</h3>
       <ul>
         <li>Message signing</li>
         <li>Identity verification</li>
         <li>Standardized protocols</li>
       </ul>
     </div>
     <div class="feature-card">
       <h3>🔌 Multi-Provider Support</h3>
       <ul>
         <li>OpenAI</li>
         <li>Anthropic</li>
         <li>Groq</li>
         <li>Google AI</li>
       </ul>
     </div>
     <div class="feature-card">
       <h3>📊 Monitoring & Tracing</h3>
       <ul>
         <li>LangSmith integration</li>
         <li>Comprehensive tracing</li>
         <li>Performance analysis</li>
       </ul>
     </div>
   </div>

Architecture
=============

AgentConnect is built on three core pillars that enable decentralized agent collaboration:

.. raw:: html

   <div class="architecture">
     <div class="arch-component">
       <h3>1. Decentralized Agent Registry</h3>
       <p>A registry that allows agents to publish capabilities and discover other agents. This is <em>not</em> a central controller, but a directory service that agents can query to find collaborators that meet their needs.</p>
     </div>
     <div class="arch-component">
       <h3>2. Communication Hub</h3>
       <p>A message routing system that facilitates secure peer-to-peer communication. The hub ensures reliable message delivery but does <em>not</em> dictate agent behavior or control the network.</p>
     </div>
     <div class="arch-component">
       <h3>3. Independent Agent Systems</h3>
       <p>Each agent is a self-contained unit built using tools and frameworks of your choice. Agents interact through standardized protocols, while their internal operations remain independent.</p>
     </div>
   </div>

.. _installation:

Installation
==============

.. attention::
   AgentConnect is currently available from source only. Direct installation via pip will be available soon.

Prerequisites
------------

- Python 3.11 or higher
- Poetry (Python package manager)
- Redis server
- Node.js 18+ and npm (for frontend)

Development Installation
-----------------------

To install AgentConnect from source:

.. code-block:: bash

    # Clone the repository
    git clone https://github.com/AKKI0511/AgentConnect.git
    cd AgentConnect

    # Using Poetry (Recommended)
    # Install all dependencies (recommended)
    poetry install --with demo,dev

    # For production only
    poetry install --without dev

Environment Setup
---------------

.. code-block:: bash

    # Copy environment template
    copy example.env .env  # Windows
    cp example.env .env    # Linux/Mac

Configure API keys in the `.env` file:

.. code-block:: bash

    DEFAULT_PROVIDER=groq
    GROQ_API_KEY=your_groq_api_key

For monitoring and additional features, you can configure optional settings:

.. code-block:: bash

    # LangSmith for monitoring (recommended)
    LANGSMITH_TRACING=true
    LANGSMITH_API_KEY=your_langsmith_api_key
    LANGSMITH_PROJECT=AgentConnect

    # Additional providers
    OPENAI_API_KEY=your_openai_api_key
    ANTHROPIC_API_KEY=your_anthropic_api_key
    GOOGLE_API_KEY=your_google_api_key

For more detailed installation instructions, see the :doc:`installation` guide.

.. _quick-start:

Quick Start
=============

.. code-block:: python

    import asyncio
    from agentconnect.agents import AIAgent, HumanAgent
    from agentconnect.core.registry import AgentRegistry
    from agentconnect.communication import CommunicationHub
    from agentconnect.core.types import ModelProvider, ModelName, AgentIdentity, InteractionMode

    async def main():
        # Create registry and hub
        registry = AgentRegistry()
        hub = CommunicationHub(registry)
        
        # Create and register an AI agent
        ai_agent = AIAgent(
            agent_id="assistant",
            name="AI Assistant",
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O,
            api_key="your-openai-api-key",
            identity=AgentIdentity.create_key_based(),
            interaction_modes=[InteractionMode.HUMAN_TO_AGENT]
        )
        await hub.register_agent(ai_agent)
        
        # Create and register a human agent
        human = HumanAgent(
            agent_id="human-user",
            name="Human User",
            identity=AgentIdentity.create_key_based()
        )
        await hub.register_agent(human)
        
        # Start interaction between human and AI
        await human.start_interaction(ai_agent)

    if __name__ == "__main__":
        asyncio.run(main())

For more detailed examples, check out our :doc:`quickstart` guide.

.. _examples:

Documentation
=============

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart
   
.. toctree::
   :maxdepth: 2
   :caption: User Guides

   guides/index
   examples/index

.. toctree::
   :maxdepth: 2
   :caption: Reference

   api/index
   
.. toctree::
   :maxdepth: 2
   :caption: Development

   contributing
   code_of_conduct
   changelog

Monitoring with LangSmith
==========================

AgentConnect integrates with LangSmith for comprehensive monitoring:

1. **Set up LangSmith**
   
   * Create an account at `LangSmith <https://smith.langchain.com/>`_
   * Add your API key to `.env`:
   
   .. code-block:: bash
   
       LANGSMITH_TRACING=true
       LANGSMITH_API_KEY=your_langsmith_api_key
       LANGSMITH_PROJECT=AgentConnect

2. **Monitor agent workflows**

   * View detailed traces of agent interactions
   * Debug complex reasoning chains
   * Analyze token usage and performance

Roadmap
=======

- ✅ **MVP with basic agent-to-agent interactions**
- ✅ **Autonomous communication between agents**  
- ✅ **Capability-based agent discovery**
- ⬜ **Coinbase AgentKit Payment Integration**
- ⬜ **Agent Identity & Reputation System**
- ⬜ **Marketplace-Style Agent Discovery**
- ⬜ **MCP Integration**
- ⬜ **Structured Parameters SDK**
- ⬜ **Secure data exchange protocols**
- ⬜ **Additional AI provider integrations**
- ⬜ **Advanced memory systems (Redis, PostgreSQL)**
- ⬜ **Federated learning capabilities**
- ⬜ **Cross-chain communication support**


.. raw:: html

   <div align="center" style="margin-top: 30px; margin-bottom: 20px;">
     <p><a href="https://github.com/AKKI0511/AgentConnect" class="github-button">⭐ Star us on GitHub</a></p>
     <p style="color: var(--pst-color-text-base);"><sub>Built with ❤️ by the AgentConnect team</sub></p>
   </div>

.. Add custom CSS for the feature grid and other elements
.. raw:: html

    <style>
    .feature-grid {
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        margin-bottom: 20px;
    }
    
    .feature-card {
        flex: 0 0 32%;
        border: 1px solid var(--pst-color-border);
        border-radius: 6px;
        padding: 15px;
        margin-bottom: 15px;
        background-color: var(--pst-color-surface);
        box-shadow: 0 2px 5px var(--pst-color-shadow);
    }
    
    .feature-card h3 {
        margin-top: 0;
        margin-bottom: 10px;
        font-size: 1.2em;
        color: var(--pst-color-text-base);
    }
    
    .feature-card ul {
        padding-left: 20px;
        margin-bottom: 0;
        color: var(--pst-color-text-base);
    }
    
    .architecture {
        margin: 20px 0;
    }
    
    .arch-component {
        padding: 15px;
        margin-bottom: 15px;
        border-left: 4px solid var(--pst-color-primary);
        background-color: var(--pst-color-surface);
    }
    
    .arch-component h3 {
        margin-top: 0;
        color: var(--pst-color-primary);
    }
    
    .arch-component p {
        color: var(--pst-color-text-base);
    }
    
    @media (max-width: 768px) {
        .feature-card {
            flex: 0 0 100%;
        }
    }
    
    /* GitHub button styling */
    .github-button {
        background-color: var(--pst-color-primary);
        color: white !important;
        padding: 10px 20px;
        border-radius: 4px;
        text-decoration: none;
        display: inline-block;
        font-weight: bold;
        transition: background-color 0.3s ease;
    }
    
    .github-button:hover {
        background-color: var(--pst-color-primary-dark, var(--pst-color-primary));
        text-decoration: none;
    }
    </style>
