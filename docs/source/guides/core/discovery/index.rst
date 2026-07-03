Discovery & Registry
====================

Once an agent has a profile, the registry makes it findable by capability, semantic description, or metadata. Locally or across a distributed network.

.. admonition:: Why This Is Powerful
   :class: important

   **Find by what agents do, not by name**: capability-name lookup and semantic search find collaborators from a plain text description, no identifiers required.

   **Same API, two scales**: ``CommunicationHub.register_agent()`` runs identically whether the registry is in-process or a remote HTTP server.

   **Identity-backed**: every agent's DID is verified before it becomes discoverable.

   See :doc:`../../systems/agent_network_setup` for how discovery fits multi-agent architectures.

I want to...
------------

* **Register agents and search by name or natural language** → :doc:`discovery_registry_local`
* **Deploy a shared registry for a distributed network** → :doc:`discovery_registry_remote`
* **Connect my agent code to a remote registry** → :doc:`discovery_registry_remote`

All pages
---------

.. grid:: 1 1 2 2
   :gutter: 3

   .. grid-item-card:: Agent Registry: Local
      :link: discovery_registry_local
      :link-type: doc

      In-process ``AgentRegistry`` via ``CommunicationHub``. Covers registration, exact and semantic capability search with filters, and vector store configuration.

   .. grid-item-card:: Agent Registry: Remote & CLI
      :link: discovery_registry_remote
      :link-type: doc

      HTTP registry server via ``agentconnect serve registry`` and ``RegistryAPIClient``. Includes CLI, deployment, and production configuration.

.. admonition:: How the pieces fit
   :class: tip

   - **Describe**: define an agent's profile, capabilities, and skills → :doc:`../agent_profile_and_capabilities`
   - **Discover**: register agents and search by capability or semantics → this section
   - **Talk**: route signed messages via the hub → :doc:`../communication/index`

.. note::

   **On the horizon**: the registry is evolving into the network's trust authority with stricter DID ownership verification, routing metadata storage per agent, and a managed hosted option.

See also
--------

- :doc:`../../core_concepts`
- :doc:`../agent_profile_and_capabilities`
- :doc:`../communication/index`
- :doc:`../../integrations/mcp/discovery_mcp`
- :doc:`../../../examples/index`

.. toctree::
   :maxdepth: 1
   :hidden:

   discovery_registry_local
   discovery_registry_remote
