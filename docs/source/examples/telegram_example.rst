Telegram Agent Example
====================

This example demonstrates how to build a Telegram AI Agent with AgentConnect that integrates with multiple specialized agents to provide advanced capabilities.

Overview
--------

We'll create a Telegram bot with the following features:

1. Natural language chat interface through Telegram
2. Web search capabilities
3. Data analysis and visualization
4. Multi-agent collaboration
5. Media processing

Prerequisites
------------

Before running this example, make sure you have:

1. Set up a Telegram bot through BotFather and obtained a token
2. Added your API keys to a ``.env`` file:

.. code-block:: text

    # Required
    TELEGRAM_BOT_TOKEN=your_telegram_bot_token
    
    # At least one of these LLM API keys
    GOOGLE_API_KEY=your_google_api_key
    # OR
    OPENAI_API_KEY=your_openai_api_key
    # OR
    ANTHROPIC_API_KEY=your_anthropic_api_key
    # OR
    GROQ_API_KEY=your_groq_api_key
    
    # Optional for improved research capabilities
    TAVILY_API_KEY=your_tavily_api_key

Full Example Code
----------------

Here's a comprehensive example that creates a Telegram bot with multi-agent capabilities. We'll walk through the code step by step afterward:

.. code-block:: python

    #!/usr/bin/env python
    """
    Advanced Telegram Bot with Multi-Agent Capabilities

    This example demonstrates a Telegram bot using the AgentConnect framework
    with the following agents:
    1. Telegram Agent: Primary interface for Telegram users
    2. Research Agent: Performs web searches and provides information
    3. Data Analysis Agent: Processes data and creates visualizations
    """
    
    import asyncio
    import os
    import sys
    import logging
    from typing import Dict, List, Any
    from pathlib import Path
    from dotenv import load_dotenv
    from pydantic import BaseModel, Field
    import matplotlib.pyplot as plt
    import pandas as pd
    import io
    import json
    
    # Import AgentConnect components
    from agentconnect.agents import AIAgent
    from agentconnect.agents.telegram import TelegramAIAgent
    from agentconnect.communication import CommunicationHub
    from agentconnect.core.types import (
        AgentIdentity,
        Capability,
        ModelName,
        ModelProvider,
    )
    from agentconnect.core.registry import AgentRegistry
    from agentconnect.utils.logging_config import setup_logging, LogLevel
    
    # Import tools
    from langchain_community.tools.tavily_search import TavilySearchResults
    
    # Configure logging
    logger = logging.getLogger(__name__)
    
    # Tool schema definitions
    class WebSearchInput(BaseModel):
        """Input schema for web search tool."""
        query: str = Field(description="The search query to find information.")
        num_results: int = Field(default=3, description="Number of search results to return.")
    
    class WebSearchOutput(BaseModel):
        """Output schema for web search tool."""
        results: List[Dict[str, str]] = Field(
            description="List of search results with title, snippet, and URL."
        )
        query: str = Field(description="The original search query.")
    
    class DataAnalysisInput(BaseModel):
        """Input schema for data analysis tool."""
        data: str = Field(description="The data to analyze in CSV or JSON format.")
        analysis_type: str = Field(
            default="summary",
            description="The type of analysis to perform (summary, correlation, visualization).",
        )
    
    class DataAnalysisOutput(BaseModel):
        """Output schema for data analysis tool."""
        result: str = Field(description="The result of the analysis.")
        visualization_path: str = Field(description="Path to any generated visualization.")
    
    async def setup_agents() -> Dict[str, Any]:
        """Set up the registry, hub, and agents."""
        # Load environment variables
        load_dotenv()
        
        # Check for required API keys
        api_key = os.getenv("GOOGLE_API_KEY")
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        
        if not telegram_token:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN not found. Please set it in your environment or .env file."
            )
        
        # Fall back to other API keys if Google's isn't available
        provider_type = ModelProvider.GOOGLE
        model_name = ModelName.GEMINI2_FLASH
        
        if not api_key:
            logger.info("GOOGLE_API_KEY not found. Checking for alternatives...")
            
            if os.getenv("OPENAI_API_KEY"):
                api_key = os.getenv("OPENAI_API_KEY")
                provider_type = ModelProvider.OPENAI
                model_name = ModelName.GPT4O
                logger.info("Using OpenAI's GPT-4 model instead")
            
            elif os.getenv("ANTHROPIC_API_KEY"):
                api_key = os.getenv("ANTHROPIC_API_KEY")
                provider_type = ModelProvider.ANTHROPIC
                model_name = ModelName.CLAUDE_3_OPUS
                logger.info("Using Anthropic's Claude model instead")
            
            elif os.getenv("GROQ_API_KEY"):
                api_key = os.getenv("GROQ_API_KEY")
                provider_type = ModelProvider.GROQ
                model_name = ModelName.LLAMA3_70B
                logger.info("Using Groq's LLaMA 3 model instead")
            
            else:
                raise RuntimeError(
                    "No LLM API key found. Please set GOOGLE_API_KEY, OPENAI_API_KEY, "
                    "ANTHROPIC_API_KEY, or GROQ_API_KEY in your environment or .env file."
                )
        
        # Create registry and hub
        registry = AgentRegistry()
        hub = CommunicationHub(registry)
        
        # Create Research Agent
        research_capabilities = [
            Capability(
                name="web_research",
                description="Performs web searches and retrieves information",
                input_schema={"query": "string", "depth": "int"},
                output_schema={"results": "string", "sources": "list"}
            )
        ]
        
        research_agent = AIAgent(
            agent_id="research_agent",
            name="Research Specialist",
            provider_type=provider_type,
            model_name=model_name,
            api_key=api_key,
            identity=AgentIdentity.create_key_based(),
            capabilities=research_capabilities,
            personality="thorough researcher who provides detailed, accurate information with sources"
        )
        
        # Add Tavily search tool if API key is available
        if tavily_api_key:
            os.environ["TAVILY_API_KEY"] = tavily_api_key
            search_tool = TavilySearchResults(max_results=5)
            research_agent.add_tools([search_tool])
        
        # Create Data Analysis Agent
        data_analysis_capabilities = [
            Capability(
                name="data_analysis",
                description="Analyzes data and creates visualizations",
                input_schema={"data": "string", "analysis_type": "string"},
                output_schema={"results": "string", "visualizations": "list"}
            )
        ]
        
        # Function to analyze data
        async def analyze_data(data_str, analysis_type="summary"):
            try:
                # Determine if data is CSV or JSON
                if data_str.strip().startswith('{') or data_str.strip().startswith('['):
                    # JSON data
                    data = pd.read_json(io.StringIO(data_str))
                else:
                    # CSV data
                    data = pd.read_csv(io.StringIO(data_str))
                
                # Create output directory if it doesn't exist
                output_dir = Path("visualizations")
                output_dir.mkdir(exist_ok=True)
                
                # Perform analysis based on type
                if analysis_type == "summary":
                    result = {
                        "shape": data.shape,
                        "columns": data.columns.tolist(),
                        "data_types": data.dtypes.astype(str).to_dict(),
                        "summary": data.describe().to_dict(),
                        "missing_values": data.isnull().sum().to_dict()
                    }
                    
                    # Create a simple visualization
                    plt.figure(figsize=(10, 6))
                    for i, col in enumerate(data.select_dtypes(include=['number']).columns[:4]):
                        plt.subplot(2, 2, i+1)
                        data[col].hist()
                        plt.title(f'Histogram of {col}')
                    
                    plt.tight_layout()
                    viz_path = output_dir / "data_summary.png"
                    plt.savefig(viz_path)
                    plt.close()
                    
                    return {
                        "result": json.dumps(result, indent=2),
                        "visualization_path": str(viz_path)
                    }
                
                elif analysis_type == "correlation":
                    # Calculate correlation matrix
                    corr = data.select_dtypes(include=['number']).corr()
                    
                    # Create heatmap
                    plt.figure(figsize=(10, 8))
                    plt.matshow(corr, fignum=1)
                    plt.title('Correlation Matrix')
                    plt.colorbar()
                    plt.xticks(range(len(corr.columns)), corr.columns, rotation=90)
                    plt.yticks(range(len(corr.columns)), corr.columns)
                    
                    viz_path = output_dir / "correlation.png"
                    plt.savefig(viz_path)
                    plt.close()
                    
                    return {
                        "result": corr.to_json(),
                        "visualization_path": str(viz_path)
                    }
                
                else:
                    return {
                        "result": "Unsupported analysis type",
                        "visualization_path": ""
                    }
                    
            except Exception as e:
                return {
                    "result": f"Error analyzing data: {str(e)}",
                    "visualization_path": ""
                }
        
        # Create custom tool for data analysis
        from langchain.tools import StructuredTool
        
        data_analysis_tool = StructuredTool.from_function(
            func=analyze_data,
            name="analyze_data",
            description="Analyze data in CSV or JSON format and create visualizations",
            args_schema=DataAnalysisInput,
            return_direct=False
        )
        
        data_analysis_agent = AIAgent(
            agent_id="data_analysis_agent",
            name="Data Analyst",
            provider_type=provider_type,
            model_name=model_name,
            api_key=api_key,
            identity=AgentIdentity.create_key_based(),
            capabilities=data_analysis_capabilities,
            personality="precise data analyst who provides clear interpretations of data",
            custom_tools=[data_analysis_tool]
        )
        
        # Create Telegram Agent
        telegram_identity = AgentIdentity.create_key_based()
        telegram_agent = TelegramAIAgent(
            agent_id="telegram_bot",
            name="AgentConnect Telegram Assistant",
            provider_type=provider_type,
            model_name=model_name,
            api_key=api_key,
            identity=telegram_identity,
            personality="helpful, friendly, and conversational assistant",
            telegram_token=telegram_token,
        )
        
        # Register all agents with the hub
        await hub.register_agent(telegram_agent)
        await hub.register_agent(research_agent)
        await hub.register_agent(data_analysis_agent)
        
        logger.info("All agents registered with the hub successfully")
        
        return {
            "registry": registry,
            "hub": hub,
            "telegram_agent": telegram_agent,
            "research_agent": research_agent,
            "data_analysis_agent": data_analysis_agent
        }
    
    async def main():
        """Main function to run the Telegram bot with multi-agent system."""
        try:
            # Set up logging
            setup_logging(level=LogLevel.INFO)
            
            # Initialize agents
            agents = await setup_agents()
            
            # Start agent processing loops
            tasks = []
            for name, agent in agents.items():
                if isinstance(agent, (AIAgent, TelegramAIAgent)) and name != "registry" and name != "hub":
                    logger.info(f"Starting {name}")
                    task = asyncio.create_task(agent.run())
                    tasks.append((name, task))
            
            # Run until interrupted
            logger.info("All agents started and running. Press Ctrl+C to stop.")
            
            # Keep the main task alive
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.exception(f"Error in main function: {e}")
        finally:
            # Cleanup
            for name, agent in agents.items():
                if isinstance(agent, TelegramAIAgent) and name != "registry" and name != "hub":
                    logger.info(f"Stopping {name}")
                    await agent.stop_telegram_bot()
            
            # Cancel all tasks
            for name, task in tasks:
                if not task.done():
                    logger.info(f"Cancelling {name} task")
                    task.cancel()
            
            # Wait for all tasks to complete
            if tasks:
                await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
            
            # Unregister agents
            hub = agents.get("hub")
            if hub:
                for name, agent in agents.items():
                    if isinstance(agent, (AIAgent, TelegramAIAgent)) and name != "registry" and name != "hub":
                        logger.info(f"Unregistering {name}")
                        await hub.unregister_agent(agent.agent_id)
    
    if __name__ == "__main__":
        # Run the main function
        asyncio.run(main())

Step-by-Step Explanation
-----------------------

Let's break down the example code to understand each component:

1. Setup and Imports
~~~~~~~~~~~~~~~~~~~

First, we import all necessary libraries and set up logging:

.. code-block:: python

    import asyncio
    import os
    import sys
    import logging
    from typing import Dict, List, Any
    from pathlib import Path
    from dotenv import load_dotenv
    # ... other imports

    # Configure logging
    logger = logging.getLogger(__name__)

2. Define Tool Schemas
~~~~~~~~~~~~~~~~~~~~~

We define input and output schemas for our custom tools using Pydantic models:

.. code-block:: python

    class WebSearchInput(BaseModel):
        """Input schema for web search tool."""
        query: str = Field(description="The search query to find information.")
        num_results: int = Field(default=3, description="Number of search results to return.")

    # ... other schemas

3. Set Up Agents
~~~~~~~~~~~~~~~

The ``setup_agents()`` function:

- Loads environment variables
- Checks for required API keys
- Creates a registry and communication hub
- Initializes specialized agents:
  - Research Agent with web search capabilities
  - Data Analysis Agent for processing data
  - Telegram Agent as the user interface

.. code-block:: python

    async def setup_agents() -> Dict[str, Any]:
        """Set up the registry, hub, and agents."""
        # Load environment variables
        load_dotenv()
        
        # ... key checks and initialization ...
        
        # Create Research Agent
        research_capabilities = [
            Capability(
                name="web_research",
                description="Performs web searches and retrieves information",
                input_schema={"query": "string", "depth": "int"},
                output_schema={"results": "string", "sources": "list"}
            )
        ]
        
        # ... create and configure agents ...

4. Create Custom Data Analysis Tool
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We implement a custom tool for data analysis that:

- Parses CSV or JSON data
- Performs statistical analysis
- Creates visualizations
- Returns results to the agent

.. code-block:: python

    # Function to analyze data
    async def analyze_data(data_str, analysis_type="summary"):
        try:
            # Determine if data is CSV or JSON
            if data_str.strip().startswith('{') or data_str.strip().startswith('['):
                # JSON data
                data = pd.read_json(io.StringIO(data_str))
            else:
                # CSV data
                data = pd.read_csv(io.StringIO(data_str))
            
            # ... analysis and visualization code ...
            
            return {
                "result": json.dumps(result, indent=2),
                "visualization_path": str(viz_path)
            }
            
        except Exception as e:
            return {
                "result": f"Error analyzing data: {str(e)}",
                "visualization_path": ""
            }

5. Initialize Telegram Agent
~~~~~~~~~~~~~~~~~~~~~~~~~~

We create the TelegramAIAgent with appropriate configuration:

.. code-block:: python

    # Create Telegram Agent
    telegram_identity = AgentIdentity.create_key_based()
    telegram_agent = TelegramAIAgent(
        agent_id="telegram_bot",
        name="AgentConnect Telegram Assistant",
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=telegram_identity,
        personality="helpful, friendly, and conversational assistant",
        telegram_token=telegram_token,
    )

6. Register and Run Agents
~~~~~~~~~~~~~~~~~~~~~~~~

Finally, we register all agents with the hub and start their processing loops:

.. code-block:: python

    # Register all agents with the hub
    await hub.register_agent(telegram_agent)
    await hub.register_agent(research_agent)
    await hub.register_agent(data_analysis_agent)
    
    # Start agent processing loops
    tasks = []
    for name, agent in agents.items():
        if isinstance(agent, (AIAgent, TelegramAIAgent)) and name != "registry" and name != "hub":
            logger.info(f"Starting {name}")
            task = asyncio.create_task(agent.run())
            tasks.append((name, task))

7. Proper Cleanup
~~~~~~~~~~~~~~~

We implement proper cleanup to ensure all resources are released:

.. code-block:: python

    finally:
        # Cleanup
        for name, agent in agents.items():
            if isinstance(agent, TelegramAIAgent) and name != "registry" and name != "hub":
                logger.info(f"Stopping {name}")
                await agent.stop_telegram_bot()
        
        # Cancel all tasks
        for name, task in tasks:
            if not task.done():
                logger.info(f"Cancelling {name} task")
                task.cancel()
        
        # ... additional cleanup ...

Running the Example
------------------

To run this example:

1. Create a ``.env`` file with your API keys and tokens
2. Save the code as ``telegram_bot.py``
3. Run the script:

.. code-block:: bash

    python telegram_bot.py

4. Open Telegram and start chatting with your bot

Interacting with the Bot
-----------------------

Once the bot is running, you can interact with it in various ways:

1. **Basic Conversation**: Simply chat with the bot in a private conversation

   .. code-block::
   
      User: Hello, who are you?
      Bot: I'm AgentConnect Telegram Assistant, an AI-powered bot that can help answer
           questions, research topics, and analyze data. What can I help you with today?

2. **Web Search**: Ask the bot to research a topic

   .. code-block::
   
      User: Research the latest advancements in quantum computing
      Bot: I'll research that for you...
           [detailed response with information about quantum computing]

3. **Data Analysis**: Send data for the bot to analyze

   .. code-block::
   
      User: Can you analyze this data?
            id,name,age,score
            1,Alice,25,92
            2,Bob,30,85
            3,Charlie,22,78
            4,Diana,28,95
      Bot: Analyzing your data...
           [summary statistics and visualization results]

4. **Group Interactions**: Add the bot to a group and mention it

   .. code-block::
   
      User: @AgentConnectBot tell us about renewable energy
      Bot: [responds with information about renewable energy]

5. **Research and Broadcast**: Research a topic and create announcements for multiple groups

   .. code-block::
   
      User: Research the latest trends in AI and create an announcement for all registered groups.
            Make it professional and include key statistics.
      
      Bot: I'll research AI trends and prepare an announcement.
           [Agent researches the topic, possibly collaborating with a research agent]
           
      Bot: Here's a preview of the announcement:
           
           📊 **AI INDUSTRY TRENDS: Q2 REPORT** 📊
           
           Our analysis reveals significant developments in AI:
           - 📈 Generative AI funding increased by 132% YoY
           - 🤖 53% of enterprises now integrating AI in core business processes
           - 🔬 Multi-modal models have seen 3.5x improvement in benchmark performance
           
           Would you like me to send this to all registered groups?
      
      User: Yes, and attach a visualization of the funding data
      
      Bot: Generating visualization...
           [Agent creates or requests a visualization from a data analysis agent]
           Announcement with visualization sent to 4 registered groups successfully!
      
      User: Edit the message to mention the impact on job markets
      
      Bot: I'll update the announcement. Here's the edited version:
           
           📊 **AI INDUSTRY TRENDS: Q2 REPORT** 📊
           
           Our analysis reveals significant developments in AI:
           - 📈 Generative AI funding increased by 132% YoY
           - 🤖 53% of enterprises now integrating AI in core business processes
           - 🔬 Multi-modal models have seen 3.5x improvement in benchmark performance
           - 👩‍💼 Estimated 18% job role transformation in knowledge worker sectors
           
           Should I apply this edit to all groups?
      
      User: Yes, update all groups
      
      Bot: Updated announcement sent to all 4 groups.

How It Works
-----------

The example demonstrates several key concepts:

1. **Multi-Agent Collaboration**: The Telegram agent serves as the user interface, while specialized agents handle specific tasks:
   - The Research Agent performs web searches
   - The Data Analysis Agent processes and visualizes data

2. **Capability-Based Discovery**: Agents discover each other through their advertised capabilities, not through hardcoded connections.

3. **Asynchronous Processing**: All agents run concurrently using asyncio, processing messages as they arrive.

4. **User Interface Integration**: The TelegramAIAgent provides a natural language interface through Telegram.

5. **Tool Integration**: Custom tools enhance agent capabilities, such as data analysis and visualization.

Extending the Example
-------------------

You can extend this example in several ways:

1. **Add More Specialized Agents**:
   - Document processing agent
   - Translation agent
   - Image generation agent

2. **Enhance Bot Commands**:
   - Add custom commands for specific functionality
   - Implement admin commands for bot management

3. **Improve Data Visualization**:
   - Add more chart types
   - Support interactive visualizations

4. **Implement User Authentication**:
   - Restrict certain bot features to authorized users
   - Track user preferences

Conclusion
---------

This example demonstrates how to build a sophisticated Telegram bot with the AgentConnect framework. By leveraging the TelegramAIAgent and integrating it with specialized agents, you can create powerful applications that provide valuable services to users through the familiar Telegram interface.

For more information on the Telegram agent and its capabilities, see the :doc:`Telegram Integration Guide </guides/telegram_integration>`. 