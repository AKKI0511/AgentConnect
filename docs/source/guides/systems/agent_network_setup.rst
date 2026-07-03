Setting Up an Agent Network
============================

.. _agent_network_setup:

.. admonition:: API stability notice
   :class: warning

   ``hub.register_agent(agent)`` and the per-agent ``agent.run()`` loop are the current
   registration and execution model. Both will change in an upcoming release. Agents will
   initiate registration themselves, and the hub will own per-agent queues. The concepts in
   this guide remain valid; the specific API calls will update.

This guide walks through connecting independent agents into a local peer network. It assumes
you have read the Core guides and have agents to wire together, whether native ``AIAgent``
instances or wrappers around existing frameworks.

Prerequisites
-------------

Complete :doc:`../../installation`, then read:

- :doc:`../core_concepts`
- :doc:`../core/agents/index`
- :doc:`../core/agent_profile_and_capabilities`
- :doc:`../core/discovery/index`
- :doc:`../core/communication/local_hub`

The Peer Network Model
-----------------------

Think of a local agent network as a private, trusted team. Five people sitting in the same
room, each with a defined specialty, able to ask colleagues for help without a manager routing
requests. A local AgentConnect network is exactly that: intentional, in-process, and closed
to the outside by design.

Every agent is a peer. No agent owns or orchestrates another. When Agent A asks Agent B to do
something, A sends a request and awaits a reply, using the same pattern in both directions.

Three shared components form the backbone:

- **AgentRegistry** is the directory. Every registered agent's profile is searchable by other
  agents using semantic queries.
- **CommunicationHub** is the router. It verifies identities, delivers signed messages, and
  tracks request/response correlation.
- **Agents** are the workers. Each runs its own processing loop and handles messages
  independently.

This differs from orchestrator patterns (LangGraph multi-agent, CrewAI, AutoGen) where a
top-level planner calls sub-agents as tools and owns the execution graph. In AgentConnect,
each agent decides at runtime whether to delegate further. Discovery and delegation happen
through the built-in collaboration tools described in :doc:`agent_toolbox`.

.. admonition:: One process, any mix of frameworks
   :class: tip

   All agents in a local network share one registry and one hub. Each agent's internal
   implementation can differ: an ``AIAgent`` using OpenAI, a ``BaseAgent`` subclass wrapping
   a LangGraph graph, a CrewAI crew, a raw API call, or any custom logic. The hub routes
   messages between them regardless of what runs inside each agent.

.. admonition:: On the horizon: connecting teams across the network
   :class: note

   The current model runs all agents in a single process with a shared in-memory hub. Remote
   agent-to-agent communication across separate processes and machines is planned for a future
   release. When it lands, we will publish a companion guide on connecting multiple local teams
   like this one across hosts, enabling cross-team collaboration at scale.

Connecting Your Agents: Five Steps
------------------------------------

Step 1: Create Identities
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each agent needs a cryptographic identity for message signing and verification:

.. code-block:: python

   from agentconnect.core.types import AgentIdentity

   planner_identity    = AgentIdentity.create_key_based()
   researcher_identity = AgentIdentity.create_key_based()
   writer_identity     = AgentIdentity.create_key_based()

Identities are ephemeral by default; a new set is generated each time the process starts. For
a local private team this is fine. See :doc:`../core/message_identity/identity` for the full
identity lifecycle.

Step 2: Define a Profile for Each Agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``AgentProfile`` is what an agent publishes to the registry. Other agents search profiles
semantically to decide who to delegate to, so a richer profile produces better discovery
results.

.. code-block:: python

   from agentconnect.core.types import AgentProfile, AgentType, Capability, Skill

   researcher_profile = AgentProfile(
       agent_id="researcher",
       agent_type=AgentType.AI,
       name="Research Specialist",
       summary="Searches the web and academic sources to retrieve factual information.",
       description=(
           "A research agent capable of answering factual questions by searching the web, "
           "querying academic databases, and synthesizing findings into structured reports."
       ),
       capabilities=[
           Capability(
               name="web_research",
               description="Search the web for up-to-date information on any topic.",
           )
       ],
       skills=[
           Skill(
               name="search_query_formulation",
               description="Generates effective search queries from natural language questions.",
           ),
           Skill(
               name="information_synthesis",
               description="Combines information from multiple sources into coherent summaries.",
           ),
       ],
       tags=["research", "web-search", "information-retrieval", "academic"],
   )

Every field feeds the semantic search index. See
:doc:`../core/agent_profile_and_capabilities` for a complete field reference and guidance on
writing effective profiles.

Step 3: Build the Agents
~~~~~~~~~~~~~~~~~~~~~~~~~~

AgentConnect agents come in two forms, depending on how much of your logic you're bringing.

Using AIAgent (LLM with tools)
""""""""""""""""""""""""""""""""

``AIAgent`` handles the LLM workflow, tool initialization, and the built-in A2A collaboration
tools automatically. Provide a profile and it's ready to join the network:

.. code-block:: python

   import os
   from agentconnect.agents import AIAgent
   from agentconnect.core.types import InteractionMode, ModelName, ModelProvider

   # Bring a Tavily search tool for the researcher
   from langchain_community.tools.tavily_search import TavilySearchResults

   researcher = AIAgent(
       agent_id="researcher",
       identity=researcher_identity,
       provider_type=ModelProvider.OPENAI,
       model_name=ModelName.GPT4O_MINI,
       api_key=os.getenv("OPENAI_API_KEY"),
       profile=researcher_profile,
       personality="I retrieve and synthesize factual information from the web.",
       interaction_modes=[InteractionMode.AGENT_TO_AGENT],
       custom_tools=[TavilySearchResults(max_results=3)],
   )

``interaction_modes`` controls who can reach this agent:

- ``[InteractionMode.AGENT_TO_AGENT]`` for background specialists reachable only by other
  agents.
- ``[InteractionMode.HUMAN_TO_AGENT, InteractionMode.AGENT_TO_AGENT]`` for entry-point
  agents that both humans and other agents can reach.

The built-in collaboration tools (``search_for_agents``, ``send_collaboration_request``,
``check_collaboration_result``) are ready as soon as the agent registers with the hub. No
extra setup is needed. See :doc:`agent_toolbox` for what these tools do.

Wrapping an Existing Agent
""""""""""""""""""""""""""""

If you have agents already built with LangGraph, Google ADK, CrewAI, raw API calls, or any
other framework, subclass ``BaseAgent`` and delegate to your existing logic inside
``process_message``:

.. code-block:: python

   from agentconnect.core.agent import BaseAgent
   from agentconnect.core.message import Message
   from agentconnect.core.types import MessageType

   class MyLangGraphAgent(BaseAgent):
       def __init__(self, agent_id, identity, profile, interaction_modes, graph):
           super().__init__(
               agent_id=agent_id,
               identity=identity,
               profile=profile,
               interaction_modes=interaction_modes,
           )
           self.graph = graph  # your compiled LangGraph, crew, client, etc.

       async def process_message(self, message: Message) -> Message | None:
           # Always call the base first. It handles security checks, cooldown
           # enforcement, STOP/IGNORE signals, and conversation-turn limits.
           # Return its response immediately if it is not None.
           base_response = await super().process_message(message)
           if base_response:
               return base_response

           # Delegate to your existing agent logic.
           result = await self.graph.ainvoke({"input": message.content})

           return Message.create(
               sender_id=self.agent_id,
               receiver_id=message.sender_id,
               content=str(result.get("output", result)),
               sender_identity=self.identity,
               message_type=MessageType.TEXT,
           )

The ``await super().process_message(message)`` call is mandatory and must come first. Skipping
it bypasses all guard conditions that the base class enforces.

For synchronous frameworks (for example, a blocking CrewAI kickoff), wrap the call in
``asyncio.to_thread``:

.. code-block:: python

   result = await asyncio.to_thread(self.crew.kickoff, {"topic": message.content})

See :doc:`../core/agents/base_agent` for the full ``BaseAgent`` API, stateful patterns,
multi-message replies, and request/response correlation.

Step 4: Register All Agents
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One registry and one hub serve all agents in the same process:

.. code-block:: python

   from agentconnect.core.registry import AgentRegistry
   from agentconnect.communication import CommunicationHub

   registry = AgentRegistry()
   hub = CommunicationHub(registry)

   await hub.register_agent(researcher)
   await hub.register_agent(writer)
   await hub.register_agent(planner)

After registration, each agent is discoverable by its peers and its collaboration tools are
active.

Step 5: Start the Run Loops
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each agent processes its incoming messages in a background task:

.. code-block:: python

   tasks = [
       asyncio.create_task(researcher.run()),
       asyncio.create_task(writer.run()),
       asyncio.create_task(planner.run()),
   ]

``run()`` polls the agent's internal queue. Messages arrive when another agent delegates to it
or when a human initiates a conversation.

``HumanAgent`` also inherits ``run()`` and can use it. With ``run()``, the human becomes a
passive hub participant: other agents can message it, and the terminal prompts the human to
respond each time. With ``start_interaction``, the human actively initiates a conversation
with a specific agent, and ``start_interaction`` manages its own blocking CLI loop
internally. When using ``start_interaction``, a separate ``run()`` task for the
``HumanAgent`` is not needed.

Interacting with the Network
------------------------------

Once agents are registered and running, there are three ways to initiate work.

Via HumanAgent (interactive CLI)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``HumanAgent`` opens a terminal prompt and routes your input to a target agent:

.. code-block:: python

   from agentconnect.agents import HumanAgent

   human = HumanAgent(
       agent_id="human_operator",   # must start with "human_"
       name="Operator",
       identity=AgentIdentity.create_key_based(),
   )
   await hub.register_agent(human)

   # Blocks until the user types "exit", "quit", or "bye"
   await human.start_interaction(planner)

``start_interaction`` targets one agent as the conversation entry point. That agent uses the
built-in collaboration tools to discover and delegate to other agents automatically. You
interact only with the entry point; the rest of the team operates behind it.

Via Agent-to-Agent Messages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To trigger work programmatically, send a message from one agent to another directly:

.. code-block:: python

   from agentconnect.core.types import MessageType

   # Planner delegates a research task to the researcher
   await planner.send_message(
       receiver_id=researcher.agent_id,
       content="Find the three most cited papers on transformer architecture from 2023.",
       message_type=MessageType.REQUEST_COLLABORATION,
   )

``send_message`` is fire-and-forget; the receiving agent processes and replies asynchronously
through its own run loop. Use this pattern for event-driven workflows where you do not need
to block and wait for the response inline.

Via Global Message Handlers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Attach an async function to observe every message flowing through the hub, without
interrupting delivery:

.. code-block:: python

   async def log_flow(message: Message) -> None:
       print(
           f"{message.sender_id} -> {message.receiver_id} "
           f"[{message.message_type.value}]"
       )

   hub.add_global_handler(log_flow)

Per-agent handlers scope observations to a specific agent:

.. code-block:: python

   hub.add_message_handler("researcher", log_flow)

For structured observability with LangSmith or callback-based tracing, pass
``external_callbacks`` when constructing an ``AIAgent``. See
:doc:`../monitoring/event_monitoring` for the full setup.

A Complete Example
-------------------

Two AI agents and one human operator, fully wired:

.. code-block:: python

   import asyncio
   import os
   from dotenv import load_dotenv

   from agentconnect.agents import AIAgent, HumanAgent
   from agentconnect.communication import CommunicationHub
   from agentconnect.core.registry import AgentRegistry
   from agentconnect.core.types import (
       AgentIdentity,
       AgentProfile,
       AgentType,
       Capability,
       InteractionMode,
       ModelName,
       ModelProvider,
       Skill,
   )


   async def main():
       load_dotenv()

       # Shared infrastructure
       registry = AgentRegistry()
       hub = CommunicationHub(registry)

       # Researcher: background specialist, reachable only by other agents
       researcher = AIAgent(
           agent_id="researcher",
           identity=AgentIdentity.create_key_based(),
           provider_type=ModelProvider.OPENAI,
           model_name=ModelName.GPT4O_MINI,
           api_key=os.getenv("OPENAI_API_KEY"),
           profile=AgentProfile(
               agent_id="researcher",
               agent_type=AgentType.AI,
               name="Research Specialist",
               summary="Retrieves factual information from various sources.",
               capabilities=[
                   Capability(
                       name="research",
                       description=(
                           "Research any topic and return structured findings "
                           "with supporting evidence."
                       ),
                   )
               ],
               skills=[
                   Skill(
                       name="web_research",
                       description="Searches and synthesizes web content.",
                   )
               ],
               tags=["research", "information-retrieval"],
           ),
           personality=(
               "I am a research specialist. I answer questions with factual, "
               "well-sourced information."
           ),
           interaction_modes=[InteractionMode.AGENT_TO_AGENT],
       )

       # Planner: entry point for humans and other agents
       planner = AIAgent(
           agent_id="planner",
           identity=AgentIdentity.create_key_based(),
           provider_type=ModelProvider.OPENAI,
           model_name=ModelName.GPT4O,
           api_key=os.getenv("OPENAI_API_KEY"),
           profile=AgentProfile(
               agent_id="planner",
               agent_type=AgentType.AI,
               name="Planning Agent",
               summary=(
                   "Understands user goals and coordinates with specialist "
                   "agents to deliver complete results."
               ),
               capabilities=[
                   Capability(
                       name="task_coordination",
                       description=(
                           "Break down user requests and coordinate with "
                           "specialist agents to fulfill them."
                       ),
                   )
               ],
               tags=["planning", "coordination"],
           ),
           personality=(
               "I understand user goals and coordinate with specialist agents "
               "to deliver thorough, complete results."
           ),
           interaction_modes=[InteractionMode.HUMAN_TO_AGENT, InteractionMode.AGENT_TO_AGENT],
       )

       # Human operator
       human = HumanAgent(
           agent_id="human_operator",
           name="Operator",
           identity=AgentIdentity.create_key_based(),
       )

       # Register all agents
       await hub.register_agent(researcher)
       await hub.register_agent(planner)
       await hub.register_agent(human)

       # Start specialist run loops; human uses start_interaction instead of run()
       researcher_task = asyncio.create_task(researcher.run())
       planner_task    = asyncio.create_task(planner.run())

       try:
           # Blocks until the user exits
           await human.start_interaction(planner)
       finally:
           # Stop processing, then remove from hub and registry
           await researcher.stop()
           await planner.stop()
           await hub.unregister_agent("researcher")
           await hub.unregister_agent("planner")
           await hub.unregister_agent("human_operator")


   if __name__ == "__main__":
       asyncio.run(main())

When the human types a request, the planner receives it. The planner's built-in tools search
the registry for capable agents, send the task to the researcher, and return the combined
result. Add more agents by repeating the profile, construction, registration, and task
pattern; the hub and registry scale to any number.

.. admonition:: Keep agent IDs unique
   :class: warning

   ``agent_id`` must be unique across all agents registered with the same hub. Registering a
   second agent with an existing ID overwrites the first without an error.

Clean Shutdown
---------------

Stop each agent before removing it from the hub:

.. code-block:: python

   # Drain in-flight messages and release resources
   for agent in [researcher, writer, planner]:
       await agent.stop()

   # Remove from hub routing and registry
   for agent_id in ["researcher", "writer", "planner", "human_operator"]:
       await hub.unregister_agent(agent_id)

Stopping before unregistering avoids delivering messages to an agent that is no longer
processing. ``unregister_agent`` also ends any active conversations the agent was part of.

See Also
---------

- :doc:`agent_toolbox` (the three built-in A2A tools)
- :doc:`../core/agents/base_agent` (full ``BaseAgent`` API and advanced patterns)
- :doc:`../core/agents/ai_agent` (custom LangChain tools via ``custom_tools``)
- :doc:`../payments/agent_payment` (payment-gated A2A workflows)
- :doc:`../monitoring/event_monitoring` (structured observability and tracing)
