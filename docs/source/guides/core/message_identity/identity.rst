Agent Identity
==============

.. _identity:

.. admonition:: Actively evolving interface
   :class: warning

   The identity model is being redesigned as a foundational layer for the v1 architecture. Several things will change before the API locks:

   - **DID as canonical agent identifier.** Today each agent carries both an ``agent_id`` and an ``identity.did``. In v1 the DID becomes the sole identifier — used for registration, routing, and all message fields.
   - **Strict public/private boundary.** Only the public side of an identity (DID + public key) will cross process boundaries to the hub or registry. Private keys will be explicitly scoped to the agent process and never transmitted.
   - **Registry as trust authority.** Registration is currently self-declared. In v1 the registry will verify DID ownership before an agent becomes discoverable or reachable — raising the trust bar across the network.
   - **Richer identity API.** New methods for DID-based JWT issuance and async signing are planned, enabling more secure agent-to-agent and agent-to-hub handshakes.

   Current usage (``create_key_based()`` and passing identity to agents) will remain the entry point. The migration will be a breaking change but the mental model stays the same.

:class:`AgentIdentity <agentconnect.core.types.AgentIdentity>` is the cryptographic identity for an agent. It contains a Decentralized Identifier (DID), an RSA key pair, and a verification status. Every agent owns exactly one identity from creation to shutdown. It is used to sign every outbound message and is checked by the hub before any delivery is made.

Creating an Identity
--------------------

``AgentIdentity.create_key_based()`` is the only method you need. It generates a fresh RSA 2048-bit key pair, derives a ``did:key:`` identifier from the public key fingerprint, and returns an identity with ``VerificationStatus.VERIFIED`` set automatically:

.. code-block:: python

    from agentconnect.core.types import AgentIdentity

    identity = AgentIdentity.create_key_based()

    print(identity.did)                   # "did:key:MIIBIjANBgk..."
    print(identity.verification_status)   # VerificationStatus.VERIFIED

Call this once per agent. There is no re-use across agents. Each agent should have its own identity so their signatures and DIDs are distinct.

How It Integrates
-----------------

**Agents**: identity is a required constructor argument for every agent type. Internally, the agent stores it as ``self.identity`` and uses it when signing every outbound message via ``send_message()``.

.. code-block:: python

    from agentconnect.agents import AIAgent
    from agentconnect.core.types import AgentIdentity, ModelProvider, ModelName

    agent = AIAgent(
        agent_id="analyst",
        identity=AgentIdentity.create_key_based(),  # one identity per agent
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O_MINI,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

**Messages**: ``Message.create()`` takes ``sender_identity`` to sign the message at creation. This happens automatically inside ``send_message()``. You never sign manually.

**Hub**: before routing any non-system message, the hub verifies that both the sender's and receiver's identities have ``VerificationStatus.VERIFIED``. If either is not yet verified, the hub attempts verification in-place. If that fails, the message is rejected and the sender receives an error. See :doc:`../communication/local_hub` for the full pipeline.

Public vs Private Key Boundary
-------------------------------

``AgentIdentity`` holds both the private and public key, but only the public side is safe to share. ``to_dict()`` deliberately excludes the private key. It is the canonical "public view" of an identity:

.. code-block:: python

    public_view = identity.to_dict()
    # Contains: did, public_key, verification_status, created_at, metadata
    # Does NOT contain: private_key

``from_dict()`` reconstructs the public view (no private key). Use this when you need to persist or transmit identity metadata to other systems.

The private key is only needed for signing. Keep it in the agent process and do not store it in shared services (hub, registry, databases).

VerificationStatus
------------------

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Status
     - Meaning
   * - ``PENDING``
     - Default when manually constructing an identity. The hub will attempt in-place verification on first message. Messages will be rejected until this resolves to ``VERIFIED``.
   * - ``VERIFIED``
     - Identity confirmed. Full message delivery and signature verification work normally. ``create_key_based()`` sets this automatically. In practice you never see ``PENDING``.
   * - ``FAILED``
     - Verification attempt failed. Messages cannot be sent or received until the identity is recreated.

In practice you never set or read this field directly. ``create_key_based()`` produces ``VERIFIED`` out of the box. The hub manages transitions internally.

Next Steps
----------

- :doc:`message` — how identity powers signing on every message
- :doc:`../communication/local_hub` — where the hub enforces identity checks during delivery
