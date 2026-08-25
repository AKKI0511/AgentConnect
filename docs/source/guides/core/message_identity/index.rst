Message & Identity
==================

Every agent starts with a cryptographic identity and every message it sends carries a signature. The hub enforces both before any delivery happens—security is infrastructure, not something each agent has to implement.

.. admonition:: Why This Is Powerful
   :class: important

   **Security is infrastructure**: Identity verification and message signature checking happen at the hub layer on every send. No per-agent security code required.

   **Self-sovereign agents**: Each agent generates its own cryptographic identity locally—no central authority assigns or validates it.

   See :doc:`../communication/local_hub` for how the hub enforces this during delivery.

I want to...
------------

* **Understand how messages are structured and sent** → :doc:`message`
* **Understand how agent identity and DIDs work** → :doc:`identity`

All pages
---------

.. grid:: 1 1 2 2
   :gutter: 3

   .. grid-item-card:: Messages
      :link: message
      :link-type: doc

      ``Message`` structure, ``MessageKind`` enum, signing, and metadata conventions. Covers how messages are created, what each type signals, and how to pass context via metadata.

   .. grid-item-card:: Agent Identity
      :link: identity
      :link-type: doc

      ``AgentIdentity`` and DID generation. Covers key pair creation, verification status lifecycle, and how identity integrates with agents and the hub's security pipeline.

.. admonition:: How the pieces fit
   :class: tip

   - **Describe**: define an agent's profile, capabilities, and skills → :doc:`../agent_profile_and_capabilities`
   - **Discover**: register and search by capability → :doc:`../discovery/index`
   - **Talk**: route signed messages through the hub → :doc:`../communication/index`
   - **Secure**: identity and signatures are enforced at the hub layer → this section

.. note::

   **On the horizon**: identity verification is evolving beyond key-based proofs. The registry is planned to take on a stronger role as a trust authority—verifying ownership and issuing grants before agents become discoverable or reachable. Message integrity guarantees are also being hardened as part of a new delivery model.

See also
--------

- :doc:`../../core_concepts`
- :doc:`../communication/local_hub`
- :doc:`../../../examples/index`

.. toctree::
   :maxdepth: 1
   :hidden:

   message
   identity
