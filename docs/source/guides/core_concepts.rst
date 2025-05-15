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

The framework is built around the :class:`BaseAgent <agentconnect.core.agent.BaseAgent>` abstract class, which provides the foundation for all agents in the system. This base class defines common functionality such as identity management, message handling, and capability declaration, while leaving implementation details to specific agent types like :class:`AIAgent <agentconnect.agents.AIAgent>` or :class:`HumanAgent <agentconnect.agents.HumanAgent>`.

Communication Hub
----------------

The Communication Hub (:class:`CommunicationHub <agentconnect.communication.CommunicationHub>`) is the central message router that facilitates agent-to-agent communication. It's important to understand that while the hub routes messages, it doesn't control agent behavior.

Key responsibilities of the Communication Hub:

1. **Message Routing**: Delivers messages between registered agents
2. **Agent Lookup**: Uses the Agent Registry to locate message recipients
3. **Protocol Management**: Ensures consistent communication patterns
4. **Message History**: Tracks interactions for auditing and debugging

The Hub provides a standardized communication channel while preserving agent autonomy - each agent decides independently how to respond to received messages.

Agent Registry
-------------

The Agent Registry (:class:`AgentRegistry <agentconnect.core.registry.AgentRegistry>`) serves as the dynamic directory or "phone book" where agents register themselves by providing a comprehensive **Agent Profile**. This profile details their identity, capabilities, skills, and other metadata. The registry enables other agents to discover potential collaborators by searching these rich profiles.

Key functions of the Agent Registry:

1. **Agent Registration**: Manages the registration of agents with verification
2. **Agent Profile Indexing**: Maintains searchable indexes of agent profiles
3. **Identity Verification**: Ensures agent identities are cryptographically verified
4. **Discovery**: Allows agents to find other agents based on various criteria

The registry doesn't impose or manage agent behavior - it simply provides the discovery mechanism that enables agents to find each other.

.. admonition:: Advanced Registry Configuration (Coming Soon)
   :class: note

   The ``AgentRegistry`` is highly configurable, especially its semantic search capabilities powered by Qdrant. You can customize aspects like the embedding model, Qdrant connection parameters (in-memory, local, or cloud), and other performance-tuning settings for the vector store.

   While a dedicated guide for these advanced configurations is planned for the `Advanced Guides <advanced/index.html>`_
   section, you can currently find detailed information and examples in the following README files within the AgentConnect repository:

   - `AgentConnect Registry README <https://github.com/AKKI0511/AgentConnect/blob/main/agentconnect/core/registry/README.md>`_
   - `Capability Discovery Implementation README <https://github.com/AKKI0511/AgentConnect/blob/main/agentconnect/core/registry/capability_discovery_impl/README.md>`_

   These documents provide the necessary details for developers looking to fine-tune the registry's vector search behavior for specific needs.

Agent Profile
-------------

The Agent Profile (:class:`AgentProfile <agentconnect.core.types.AgentProfile>`) is a comprehensive, structured description of an agent. Think of it as an agent's detailed resume or business card. It's crucial for how agents are understood, discovered, and interacted with within the AgentConnect framework.

Instead of just declaring isolated functions, an `AgentProfile` provides a richer picture, typically including:

*   **Basic Identity**: Who the agent is (ID, name, type like AI or Human).
*   **Purpose**: A summary and detailed description of what the agent does.
*   **Capabilities**: Specific services or tasks the agent can perform, each with its own description.
*   **Skills**: Broader areas of expertise.
*   **Interaction Details**: How to communicate with the agent (e.g., expected input/output types, endpoint URL).
*   **Tags & Examples**: Keywords for filtering and illustrative use cases.

By providing this rich, centralized profile, agents can be discovered more effectively. For example, another agent can search for "an agent that can translate documents and has experience with legal text" not just by a single capability name. This allows for more nuanced and semantic discovery, making it easier for agents to find the best collaborator for a given task.

When an agent registers, its entire profile is made available to the Agent Registry, enabling sophisticated search and matching.

Agent Identity
-------------

Every agent in the system has a unique, cryptographically verifiable identity (:class:`AgentIdentity <agentconnect.core.types.AgentIdentity>`). This identity includes:

1. **Decentralized Identifier (DID)**: A globally unique identifier
2. **Public Key**: Used to verify message signatures
3. **Private Key** (optional): Used to sign messages (stored only on the agent itself)
4. **Verification Status**: Indicates whether the identity has been cryptographically verified

The identity system ensures secure communications by enabling agents to verify that messages truly come from their claimed senders, protecting against impersonation and tampering.

Messages
-------

All inter-agent communication happens through standardized :class:`Message <agentconnect.core.message.Message>` objects. Each message contains:

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

1. Agents register with the Agent Registry, declaring their identity and comprehensive `AgentProfile`.
2. An agent needs to use a service or capability provided by another agent.
3. The agent queries the Registry to find agents whose profiles indicate they offer that service or capability.
4. The agent creates a signed Message and sends it via the Communication Hub
5. The Hub looks up the recipient agent and delivers the message
6. The receiving agent verifies the message signature and processes the request
7. If a response is needed, the process repeats in reverse

This architecture allows for flexible, secure communication between autonomous agents while maintaining a decentralized approach - no central authority dictates what agents must do or how they must respond.

Next Steps
----------

Now that you understand the core concepts of AgentConnect, proceed to the :doc:`first_agent` guide to create and run your first AI agent. You may also want to explore how to integrate human agents using :doc:`human_in_the_loop`. 