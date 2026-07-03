Communication
=============

The ``CommunicationHub`` is the message backbone of every AgentConnect system. Register your agents once and the hub handles delivery, security verification, and collaboration patterns automatically.

.. admonition:: Why This Is Powerful
   :class: important

   **Zero-wiring delivery**: Register an agent and it becomes reachable immediately. The hub resolves receivers by ID, verifies identities, and delivers. No explicit connections or per-agent plumbing required.

   **Security built into the routing layer**: Every non-system message passes through identity verification, signature checking, and interaction-mode compatibility before it reaches the receiver. Trust is enforced at the infrastructure level, not left to each agent to implement.

   **Request/response without the boilerplate**: The hub manages correlation, timeouts, and collaboration chains. Send a request and await the result; late arrivals are tracked and resolved cleanly without any custom coordination code.

   See :doc:`../../systems/agent_toolbox` for end-to-end examples of agents requesting work from each other through the hub.

I want to...
------------

* **Route messages, request collaboration, monitor the hub, or understand the security pipeline** → :doc:`local_hub`

All pages
---------

.. grid:: 1 1 2 2
   :gutter: 3

   .. grid-item-card:: Communication Hub (Local)
      :link: local_hub
      :link-type: doc

      In-process ``CommunicationHub`` for routing signed messages between locally registered agents. Covers the full delivery and security pipeline, request/response patterns, and observability hooks.

.. admonition:: How the pieces fit
   :class: tip

   - **Describe**: define an agent's profile, capabilities, and skills → :doc:`../agent_profile_and_capabilities`
   - **Discover**: register agents and search by capability or semantics → :doc:`../discovery/index`
   - **Talk**: route signed messages via the hub → this section

.. note::

   **On the horizon**: the hub is expanding beyond local, in-process messaging. Remote agent-to-agent communication across processes and hosts is planned for a future release.

See also
--------

- :doc:`../../core_concepts`
- :doc:`../../systems/agent_network_setup`
- :doc:`../../systems/agent_toolbox`
- :doc:`../../../examples/index`

.. toctree::
   :maxdepth: 1
   :hidden:

   local_hub
