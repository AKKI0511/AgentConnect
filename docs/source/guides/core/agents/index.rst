Agents
======

Build interoperable agents that can be discovered by capabilities and communicate through the hub. This section helps you choose the right implementation and sends you to the deep-dive guides.

.. admonition:: Why This Is Powerful
   :class: important

   **Network Effect Without Wiring**: In AgentConnect, any agent can discover and communicate with any other agent—no manual connections required. Create 10, 100, or 1000+ specialist agents, register them with the hub, and they instantly form a peer-to-peer network where each agent has autonomous access to all others.
   
   **True Autonomy at Scale**: Agents decide when and how to collaborate based on their goals and the capabilities they discover. No central orchestrator dictates workflows—agents negotiate and coordinate directly.
   
   **Composable Multi-Agent Systems**: Build complex multi-agent workflows using frameworks like LangGraph or Google ADK, then register the entire system as a single agent. That composite agent becomes discoverable and usable by all other agents in the network, enabling hierarchical collaboration patterns.
   
   See :doc:`../../systems/agent_network_setup` and :doc:`../../systems/agent_toolbox` for architectural patterns and examples.

I want to...
------------

* **Build a custom agent** → :doc:`base_agent`
* **Use an out-of-the-box AI agent** → :doc:`ai_agent`
* **Add a human participant** → :doc:`human_agent`

What's in this section
----------------------

- **BaseAgent (core building block)**: Framework-agnostic and provider-agnostic. Extend it to define exactly how your agent processes messages, exposes capabilities, and talks to other agents via the hub.

- **AIAgent (batteries included)**: A ready-to-use agent with built-in collaboration tools for capability-driven workflows (search, request, check). It hides framework details so you can be productive immediately. See how collaboration tools behave in :doc:`../../systems/agent_toolbox`.

- **HumanAgent (human-in-the-loop)**: Let humans participate as first-class agents. Other agents can discover a human, initiate a conversation for review/approval, and integrate human decisions in the flow.

All pages
---------

.. grid:: 1 1 2 2
   :gutter: 3

   .. grid-item-card:: BaseAgent
      :link: base_agent
      :link-type: doc

      The core abstraction. Extend for full control over message processing and behavior.

   .. grid-item-card:: AIAgent
      :link: ai_agent
      :link-type: doc

      Out-of-the-box AI agent with collaboration tools for capability-driven workflows.

   .. grid-item-card:: HumanAgent
      :link: human_agent
      :link-type: doc

      Human-in-the-loop participation for approvals, reviews, and conversations.

.. admonition:: How agents interact
   :class: tip

   - Describe: Define an agent's profile (identity, capabilities, skills, tags) → :doc:`../agent_profile_and_capabilities`
   - Discover: Find agents by capability or semantics → :doc:`../discovery/index`
   - Talk: Route signed messages via the hub → :doc:`../communication/index`

See also
--------

- :doc:`../../core_concepts`
- :doc:`../../systems/agent_network_setup`
- :doc:`../../systems/agent_toolbox`
- :doc:`../../../examples/index`

.. toctree::
   :maxdepth: 1
   :hidden:

   base_agent
   ai_agent
   human_agent

