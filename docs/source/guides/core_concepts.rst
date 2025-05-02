Core Concepts
============

.. _core_concepts:

Welcome to the core concepts guide for AgentConnect. This guide introduces the foundational components that make up the AgentConnect framework, providing you with a solid understanding of how independent agents discover and communicate with each other.

.. image:: ../_static/architecture_flow.png
   :width: 70%
   :align: center
   :alt: AgentConnect Architecture

*The AgentConnect architecture enables decentralized agent discovery and communication.*

Overall Vision: Independent Agents
----------------------------------

At its heart, AgentConnect is designed to create a network of independent, potentially heterogeneous agents that can discover and communicate with each other securely. Unlike traditional centralized systems, AgentConnect promotes agent autonomy - each agent makes its own decisions about when, how, and with whom to interact.

The framework is built around the ``BaseAgent`` abstract class (``agentconnect/core/agent.py``), which provides the foundation for all agents in the system. This base class defines common functionality such as identity management, message handling, and capability declaration, while leaving implementation details to specific agent types like ``AIAgent`` or ``HumanAgent``.

Communication Hub
----------------

The Communication Hub (``CommunicationHub`` in ``agentconnect/communication/hub.py``) is the central message router that facilitates agent-to-agent communication. It's important to understand that while the hub routes messages, it doesn't control agent behavior.

Key responsibilities of the Communication Hub:

1. **Message Routing**: Delivers messages between registered agents
2. **Agent Lookup**: Uses the Agent Registry to locate message recipients
3. **Protocol Management**: Ensures consistent communication patterns
4. **Message History**: Tracks interactions for auditing and debugging

The Hub provides a standardized communication channel while preserving agent autonomy - each agent decides independently how to respond to received messages.

Agent Registry
-------------

The Agent Registry (``AgentRegistry`` in ``agentconnect/core/registry/registry_base.py``) serves as the dynamic directory or "phone book" where agents register themselves and their capabilities. It enables other agents to discover potential collaborators based on the capabilities they offer.

Key functions of the Agent Registry:

1. **Agent Registration**: Manages the registration of agents with verification
2. **Capability Indexing**: Maintains searchable indexes of agent capabilities
3. **Identity Verification**: Ensures agent identities are cryptographically verified
4. **Discovery**: Allows agents to find other agents based on various criteria

The registry doesn't impose or manage agent behavior - it simply provides the discovery mechanism that enables agents to find each other.

Capabilities
-----------

Capabilities (``Capability`` class in ``agentconnect/core/types.py``) are standardized declarations of what an agent can do. Each capability has a name, description, and defined input/output schemas that allow other agents to understand how to interact with it.

The capability system enables semantic discovery - agents can locate other agents based on the functionality they need rather than knowing specific identifiers in advance.

A typical capability definition looks like:

.. code-block:: python

    Capability(
        name="conversation",
        description="General conversation and assistance",
        input_schema={"query": "string"},
        output_schema={"response": "string"},
    )

When an agent registers with the system, its capabilities become discoverable by other agents who may need those services.

Agent Identity
-------------

Every agent in the system has a unique, cryptographically verifiable identity (``AgentIdentity`` in ``agentconnect/core/types.py``). This identity includes:

1. **Decentralized Identifier (DID)**: A globally unique identifier
2. **Public Key**: Used to verify message signatures
3. **Private Key** (optional): Used to sign messages (stored only on the agent itself)
4. **Verification Status**: Indicates whether the identity has been cryptographically verified

The identity system ensures secure communications by enabling agents to verify that messages truly come from their claimed senders, protecting against impersonation and tampering.

Messages
-------

All inter-agent communication happens through standardized ``Message`` objects (``agentconnect/core/message.py``). Each message contains:

1. **Unique ID**: For tracking and referencing
2. **Sender/Receiver IDs**: Who sent the message and who should receive it
3. **Content**: The actual message payload
4. **Message Type**: Indicating the purpose or nature of the message (e.g., TEXT, COMMAND)
5. **Timestamp**: When the message was created
6. **Signature**: Cryptographic signature for verification
7. **Metadata**: Additional contextual information

Messages are signed using the sender's private key and can be verified using the sender's public key, ensuring both authenticity and integrity.

How These Components Work Together
---------------------------------

The flow of agent interaction typically follows this pattern:

1. Agents register with the Agent Registry, declaring their identity and capabilities
2. An agent needs to use a capability provided by another agent
3. The agent queries the Registry to find agents offering that capability
4. The agent creates a signed Message and sends it via the Communication Hub
5. The Hub looks up the recipient agent and delivers the message
6. The receiving agent verifies the message signature and processes the request
7. If a response is needed, the process repeats in reverse

This architecture allows for flexible, secure communication between autonomous agents while maintaining a decentralized approach - no central authority dictates what agents must do or how they must respond.

Next Steps
----------

Now that you understand the core concepts of AgentConnect, proceed to the :doc:`first_agent` guide to create and run your first AI agent. You may also want to explore how to integrate human agents using :doc:`human_in_the_loop`. 