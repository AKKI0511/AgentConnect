Multi-Agent Example
=================

.. _multi_agent_example:

Working with Multiple Agents
---------------------------

This example demonstrates how to set up and manage multiple agents in a collaborative environment using AgentConnect's decentralized communication architecture.

Setting Up Multiple Agents
-------------------------

.. code-block:: python

    import os
    import asyncio
    from dotenv import load_dotenv
    
    from agentconnect.agents.ai_agent import AIAgent
    from agentconnect.core.registry import AgentRegistry
    from agentconnect.communication.hub import CommunicationHub
    from agentconnect.core.types import (
        ModelProvider,
        ModelName,
        AgentIdentity,
        InteractionMode,
        Capability,
        MessageType
    )
    from agentconnect.core.message import Message
    
    # Load environment variables
    load_dotenv()
    
    # Create a registry and communication hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)
    
    # Create specialized agents with different capabilities
    researcher = AIAgent(
        agent_id="researcher",
        name="Research Specialist",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        capabilities=[
            Capability(
                name="research",
                description="Can perform in-depth research on any topic",
                input_schema={"query": "string"},
                output_schema={"findings": "string"}
            )
        ],
        personality="thorough and analytical researcher",
        organization_id="example_org",
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
    )
    
    analyst = AIAgent(
        agent_id="analyst",
        name="Data Analyst",
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key=os.getenv("OPENAI_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        capabilities=[
            Capability(
                name="data_analysis",
                description="Can analyze data and extract insights",
                input_schema={"data": "string"},
                output_schema={"insights": "string"}
            )
        ],
        personality="precise and detail-oriented analyst",
        organization_id="example_org",
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
    )
    
    writer = AIAgent(
        agent_id="writer",
        name="Content Writer",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH_LITE,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        capabilities=[
            Capability(
                name="content_creation",
                description="Can write engaging content on any topic",
                input_schema={"topic": "string", "style": "string"},
                output_schema={"content": "string"}
            )
        ],
        personality="creative and articulate writer",
        organization_id="example_org",
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
    )
    
    # Register all agents with the hub
    async def setup():
        await hub.register_agent(researcher)
        await hub.register_agent(analyst)
        await hub.register_agent(writer)
        
        # Add message handlers to track communication
        hub.add_message_handler("researcher", lambda msg: print(f"Research message: {msg.content[:50]}..."))
        hub.add_message_handler("analyst", lambda msg: print(f"Analysis message: {msg.content[:50]}..."))
        hub.add_message_handler("writer", lambda msg: print(f"Writer message: {msg.content[:50]}..."))
    
    # Run the setup
    asyncio.run(setup())

Capability-Based Collaboration
----------------------------

With AgentConnect, agents can discover and collaborate with each other based on capabilities rather than pre-defined connections:

.. code-block:: python

    async def collaborative_task():
        # Human requests a comprehensive report on quantum computing
        initial_request = "I need a comprehensive report on the latest advancements in quantum computing"
        
        # Instead of hardcoding the sequence, we use capability discovery
        # The researcher discovers other agents based on their capabilities
        
        # Step 1: Send to researcher to gather information
        research_msg = Message.create(
            sender_id="human_user",
            receiver_id="researcher",
            content=initial_request,
            sender_identity=AgentIdentity.create_key_based(),
            message_type=MessageType.TEXT
        )
        
        research_response = await hub.route_message(research_msg)
        print(f"Research complete: {research_response.content[:100]}...")
        
        # Step 2: The analyst processes the research findings
        # The researcher uses the hub to find an agent with analysis capabilities
        analysis_result = await hub.send_collaboration_request(
            sender_id="researcher",
            receiver_id="analyst",  # In a real scenario, this could be discovered via capability search
            task_description=f"Analyze these quantum computing research findings and extract key insights: {research_response.content}",
            timeout=60
        )
        
        print(f"Analysis complete: {analysis_result[:100]}...")
        
        # Step 3: The writer creates the final report
        # Again, in a real scenario, this agent would be discovered via capabilities
        final_report = await hub.send_collaboration_request(
            sender_id="analyst",
            receiver_id="writer",
            task_description=f"Create a comprehensive report based on this analysis of quantum computing: {analysis_result}",
            timeout=60
        )
        
        print(f"Final report complete: {final_report[:100]}...")
        
        # Return the final report to the human
        final_msg = Message.create(
            sender_id="writer",
            receiver_id="human_user",
            content=final_report,
            sender_identity=AgentIdentity.create_key_based(),
            message_type=MessageType.TEXT
        )
        
        await hub.route_message(final_msg)
        
        return final_report
    
    # Run the collaborative task
    final_report = asyncio.run(collaborative_task())

Automatic Capability Discovery
---------------------------

AgentConnect's true power comes from decentralized capability discovery. Here's how to search for agents by capability:

.. code-block:: python

    async def capability_discovery_example():
        # Create a human agent as the requester
        human = AIAgent(
            agent_id="human_assistant",
            name="Human Assistant",
            provider_type=ModelProvider.GOOGLE,
            model_name=ModelName.GEMINI2_FLASH_LITE,
            api_key=os.getenv("GOOGLE_API_KEY"),
            identity=AgentIdentity.create_key_based(),
            interaction_modes=[InteractionMode.HUMAN_TO_AGENT, InteractionMode.AGENT_TO_AGENT],
            organization_id="example_org",
        )
        
        # Register this agent
        await hub.register_agent(human)
        
        # Search for agents with research capabilities
        research_agents = await registry.find_agents_by_capability("research")
        print(f"Found {len(research_agents)} agents with research capabilities")
        
        if research_agents:
            # Get the first research agent's ID
            research_agent_id = research_agents[0]
            
            # Send a collaboration request
            result = await hub.send_collaboration_request(
                sender_id="human_assistant",
                receiver_id=research_agent_id,
                task_description="Research the applications of quantum computing in healthcare",
                timeout=60
            )
            
            print(f"Research result: {result[:100]}...")
            
            # Now find an agent that can write content
            content_agents = await registry.find_agents_by_capability("content_creation")
            
            if content_agents:
                content_agent_id = content_agents[0]
                
                # Send the research to the content creator
                final_content = await hub.send_collaboration_request(
                    sender_id="human_assistant",
                    receiver_id=content_agent_id,
                    task_description=f"Create an easy-to-understand blog post about this research: {result}",
                    timeout=60
                )
                
                print(f"Final content: {final_content[:100]}...")
                return final_content
        
        return "No appropriate agents found"
    
    # Run the capability discovery example
    asyncio.run(capability_discovery_example())

Using Message Handlers for Coordination
------------------------------------

Message handlers allow you to track and orchestrate communication between agents:

.. code-block:: python

    async def message_handler_example():
        # Create a global message handler to track all communications
        def global_message_tracker(message):
            print(f"[GLOBAL] {message.sender_id} → {message.receiver_id}: {message.content[:50]}...")
        
        # Add global message handler
        hub.add_global_message_handler(global_message_tracker)
        
        # Create agent-specific message handlers for customized logic
        async def researcher_handler(message):
            print(f"[RESEARCH] Received: {message.content[:50]}...")
            # You could add specialized processing here
            
            # For example, logging research queries to a database
            # store_in_research_db(message.content)
            
            # Or triggering additional actions when certain keywords are detected
            if "quantum" in message.content.lower():
                print("[RESEARCH] Quantum-related request detected!")
        
        # Add the researcher-specific handler
        hub.add_message_handler("researcher", researcher_handler)
        
        # Send a test message to the researcher
        test_msg = Message.create(
            sender_id="human_user",
            receiver_id="researcher",
            content="Research the relationship between quantum computing and machine learning",
            sender_identity=AgentIdentity.create_key_based(),
            message_type=MessageType.TEXT
        )
        
        # Route the message and see the handlers in action
        await hub.route_message(test_msg)
    
    # Run the message handler example
    asyncio.run(message_handler_example())

Complete Multi-Agent System
------------------------

Here's a complete example that ties everything together:

.. code-block:: python

    import os
    import asyncio
    import json
    from dotenv import load_dotenv
    
    from agentconnect.agents.ai_agent import AIAgent
    from agentconnect.agents.human_agent import HumanAgent
    from agentconnect.core.registry import AgentRegistry
    from agentconnect.communication.hub import CommunicationHub
    from agentconnect.core.types import (
        ModelProvider,
        ModelName,
        AgentIdentity,
        InteractionMode,
        Capability,
        MessageType
    )
    
    async def run_multi_agent_system():
        # Load environment variables
        load_dotenv()
        
        # Create registry and hub
        registry = AgentRegistry()
        hub = CommunicationHub(registry)
        
        # Create specialized agents
        agents = {
            "researcher": AIAgent(
                agent_id="researcher",
                name="Research Specialist",
                provider_type=ModelProvider.GOOGLE,
                model_name=ModelName.GEMINI2_FLASH,
                api_key=os.getenv("GOOGLE_API_KEY"),
                identity=AgentIdentity.create_key_based(),
                capabilities=[
                    Capability(
                        name="research",
                        description="In-depth research on any topic",
                        input_schema={"query": "string"},
                        output_schema={"findings": "string"}
                    )
                ],
                personality="thorough researcher",
                organization_id="example_org",
                interaction_modes=[InteractionMode.AGENT_TO_AGENT, InteractionMode.HUMAN_TO_AGENT],
            ),
            "analyst": AIAgent(
                agent_id="analyst",
                name="Data Analyst",
                provider_type=ModelProvider.OPENAI,
                model_name=ModelName.GPT4O,
                api_key=os.getenv("OPENAI_API_KEY"),
                identity=AgentIdentity.create_key_based(),
                capabilities=[
                    Capability(
                        name="analysis",
                        description="Data analysis and insights extraction",
                        input_schema={"data": "string"},
                        output_schema={"insights": "string"}
                    )
                ],
                personality="precise analyst",
                organization_id="example_org",
                interaction_modes=[InteractionMode.AGENT_TO_AGENT, InteractionMode.HUMAN_TO_AGENT],
            ),
            "writer": AIAgent(
                agent_id="writer",
                name="Content Writer",
                provider_type=ModelProvider.GOOGLE,
                model_name=ModelName.GEMINI2_FLASH_LITE,
                api_key=os.getenv("GOOGLE_API_KEY"),
                identity=AgentIdentity.create_key_based(),
                capabilities=[
                    Capability(
                        name="writing",
                        description="Content creation and summarization",
                        input_schema={"topic": "string", "style": "string"},
                        output_schema={"content": "string"}
                    )
                ],
                personality="creative writer",
                organization_id="example_org",
                interaction_modes=[InteractionMode.AGENT_TO_AGENT, InteractionMode.HUMAN_TO_AGENT],
            ),
        }
        
        # Create a human agent
        human = HumanAgent(
            agent_id="human_user",
            name="Example User",
            identity=AgentIdentity.create_key_based(),
            organization_id="example_org",
        )
        
        # Register all agents
        for agent_id, agent in agents.items():
            await hub.register_agent(agent)
            print(f"Registered agent: {agent_id}")
            
            # Start agent background processing
            agent_task = asyncio.create_task(agent.run())
            
        # Register human
        await hub.register_agent(human)
        
        # Set up message tracking
        results = {}
        
        async def message_tracker(message):
            print(f"Message: {message.sender_id} → {message.receiver_id}: {message.content[:50]}...")
            # Store the latest message from each agent
            if message.sender_id in agents:
                results[message.sender_id] = message.content
        
        # Add global message handler
        hub.add_global_message_handler(message_tracker)
        
        # Human initiates the process
        initial_request = "Create a comprehensive report on the potential of quantum computing in medicine"
        
        # Human sends message to researcher
        await human.send_message(
            "researcher", 
            initial_request
        )
        
        # Wait for researcher to respond
        await asyncio.sleep(10)
        
        # Researcher automatically discovers and collaborates with the analyst based on capabilities
        # This happens through the agent's internal workflow
        
        # Wait for the full process to complete
        await asyncio.sleep(60)
        
        # Save all results
        with open("multi_agent_results.json", "w") as f:
            json.dump(results, f, indent=2)
            
        # Clean up
        for agent in agents.values():
            agent.is_running = False
            await hub.unregister_agent(agent.agent_id)
            
        await hub.unregister_agent(human.agent_id)
        
        return results
    
    if __name__ == "__main__":
        results = asyncio.run(run_multi_agent_system())
        print(f"Final results from all agents: {results.keys()}") 