Advanced Agent Example
===================

.. _advanced_agent_example:

Creating Advanced Agents with Custom Tools
---------------------------------------

This example demonstrates how to create advanced AI agents with custom tools and specialized prompts.

Custom Tools with PromptTools
---------------------------

AgentConnect allows you to extend agent capabilities with custom tools:

.. code-block:: python

    import os
    import asyncio
    from typing import Dict, Any, List, Optional, Type, TypeVar, Callable, Awaitable
    from dotenv import load_dotenv
    from langchain_core.tools import BaseTool, StructuredTool
    from pydantic import BaseModel, Field
    
    from agentconnect.agents.ai_agent import AIAgent
    from agentconnect.core.registry import AgentRegistry
    from agentconnect.communication.hub import CommunicationHub
    from agentconnect.core.types import (
        ModelProvider,
        ModelName,
        AgentIdentity,
        InteractionMode,
        MessageType,
        Capability
    )
    from agentconnect.prompts.tools import PromptTools
    from agentconnect.prompts.templates.prompt_templates import PromptTemplates, SystemPromptConfig
    
    # Load environment variables
    load_dotenv()
    
    # Define a schema for our custom tool
    class WeatherLookupInput(BaseModel):
        """Input for weather lookup tool."""
        
        location: str = Field(description="The city or location to check weather for")
        units: str = Field(description="Temperature units (celsius/fahrenheit)", default="celsius")
    
    class WeatherLookupOutput(BaseModel):
        """Output for weather lookup tool."""
        
        temperature: float = Field(description="Current temperature")
        condition: str = Field(description="Weather condition (sunny, cloudy, etc.)")
        humidity: float = Field(description="Humidity percentage")
    
    # Create a registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)
    
    # Set up the PromptTools instance with our registry and hub
    prompt_tools = PromptTools(agent_registry=registry, communication_hub=hub)
    
    # Define our custom tool function
    def weather_lookup(location: str, units: str = "celsius") -> Dict[str, Any]:
        """
        Look up the current weather for a location.
        
        Args:
            location: City or location to check
            units: Temperature units (celsius/fahrenheit)
            
        Returns:
            Dictionary with weather information
        """
        # In a real implementation, this would call a weather API
        # This is a mock implementation for demonstration
        weather_data = {
            "New York": {"temperature": 22.5, "condition": "Partly Cloudy", "humidity": 65.0},
            "London": {"temperature": 18.0, "condition": "Rainy", "humidity": 80.0},
            "Tokyo": {"temperature": 27.0, "condition": "Sunny", "humidity": 70.0},
            "Sydney": {"temperature": 24.5, "condition": "Clear", "humidity": 55.0},
        }
        
        # Default to a generic response if location not found
        result = weather_data.get(
            location, 
            {"temperature": 20.0, "condition": "Unknown", "humidity": 60.0}
        )
        
        # Convert temperature if needed
        if units.lower() == "fahrenheit":
            result["temperature"] = (result["temperature"] * 9/5) + 32
            
        return result
    
    # Create the asynchronous version of our tool
    async def weather_lookup_async(location: str, units: str = "celsius") -> Dict[str, Any]:
        """Async version of the weather lookup tool."""
        return weather_lookup(location, units)
    
    # Register our custom tool with PromptTools
    T = TypeVar('T', bound=BaseModel)
    
    weather_tool = prompt_tools.create_tool_from_function(
        func=weather_lookup,
        name="weather_lookup",
        description="Get current weather information for a location",
        args_schema=WeatherLookupInput,
        category="weather",
        coroutine=weather_lookup_async
    )

Creating an Agent with Custom Tools
---------------------------------

Now we'll create an agent that can use our custom tool:

.. code-block:: python

    # Create an agent with our custom tools
    weather_agent = AIAgent(
        agent_id="weather_assistant",
        name="Weather Assistant",
        provider_type=ModelProvider.GOOGLE,  # Or your preferred provider
        model_name=ModelName.GEMINI2_FLASH,  # Or your preferred model
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        capabilities=[
            Capability(
                name="weather_forecasting",
                description="Can provide weather information for locations worldwide",
                input_schema={"location": "string", "units": "string"},
                output_schema={"forecast": "string"}
            )
        ],
        personality="helpful weather expert",
        organization_id="example_org",
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT, InteractionMode.AGENT_TO_AGENT],
        prompt_tools=prompt_tools,  # Pass our customized PromptTools instance
        # Pass our custom tool in the custom_tools list
        custom_tools=[weather_tool],
    )
    
    # Register the agent with the hub
    async def setup_agent():
        await hub.register_agent(weather_agent)
        print(f"Registered weather agent with custom tools")
    
    # Run the setup
    asyncio.run(setup_agent())

Using Custom Prompt Templates
---------------------------

You can also customize the agent's behavior with specialized prompt templates:

.. code-block:: python

    from agentconnect.prompts.templates.prompt_templates import (
        PromptTemplates, 
        SystemPromptConfig,
        PromptType
    )
    
    # Create custom prompt templates for our weather agent
    prompt_templates = PromptTemplates()
    
    # Create a specialized system prompt config
    system_config = SystemPromptConfig(
        name="Weather Expert",
        capabilities=weather_agent.capabilities,
        personality="expert meteorologist who explains weather patterns clearly",
        temperature=0.3,  # Lower temperature for more precise answers
        additional_context={
            "expertise": "Weather forecasting and climate patterns",
            "data_sources": "Multiple international weather services",
            "specialty": "Translating complex weather data into understandable explanations"
        }
    )
    
    # Create a custom chat prompt template
    custom_prompt = prompt_templates.create_prompt(
        prompt_type=PromptType.SYSTEM,
        config=system_config,
        include_history=True
    )
    
    # Update our agent with the custom prompt templates
    weather_agent.prompt_templates = prompt_templates

Using Agent Workflows and Prompt Systems
--------------------------------------

AgentConnect provides powerful workflow capabilities to control agent behavior:

.. code-block:: python

    from agentconnect.prompts.agent_prompts import (
        AgentWorkflow,
        WorkflowState,
        AgentMode
    )
    
    # Create a custom workflow that specializes in weather analysis
    class WeatherAnalysisWorkflow(AgentWorkflow):
        """Specialized workflow for weather analysis."""
        
        def __init__(
            self,
            agent_id: str,
            system_prompt_config: SystemPromptConfig,
            llm,
            tools: PromptTools,
            prompt_templates: PromptTemplates,
            custom_tools: Optional[List[BaseTool]] = None,
        ):
            super().__init__(
                agent_id=agent_id,
                llm=llm,
                tools=tools,
                prompt_templates=prompt_templates,
                custom_tools=custom_tools,
            )
            
            self.system_prompt_config = system_prompt_config
            
        def build_workflow(self):
            """Build a custom workflow for weather analysis."""
            workflow = super().build_workflow()
            
            # Here we could add custom nodes and edges to the workflow
            # For example, specialized error handling for weather data
            
            return workflow
    
    # To use this custom workflow, you would modify the AIAgent initialization:
    # weather_agent.workflow_agent_type = "weather_analysis"
    # Then register a factory function for creating this workflow type
    
    # Create a message handler for our weather agent
    async def weather_message_handler(message):
        print(f"Weather agent received: {message.content[:50]}...")
        
        # Add specialized processing for weather queries
        if "forecast" in message.content.lower():
            print("Forecast request detected! Prioritizing...")
    
    # Add the message handler to the hub
    hub.add_message_handler("weather_assistant", weather_message_handler)

Complete Example with Task Decomposition Tool
------------------------------------------

Here's a complete example that combines custom tools with task decomposition:

.. code-block:: python

    import os
    import asyncio
    from dotenv import load_dotenv
    from langchain_core.tools import BaseTool
    from typing import Dict, Any, List, Optional
    
    from agentconnect.agents.ai_agent import AIAgent
    from agentconnect.agents.human_agent import HumanAgent
    from agentconnect.core.registry import AgentRegistry
    from agentconnect.communication.hub import CommunicationHub
    from agentconnect.core.types import (
        ModelProvider,
        ModelName,
        AgentIdentity,
        InteractionMode,
        Capability
    )
    from agentconnect.prompts.tools import PromptTools, Subtask
    from agentconnect.prompts.templates.prompt_templates import PromptTemplates, SystemPromptConfig
    
    async def run_advanced_agent_example():
        # Load environment variables
        load_dotenv()
        
        # Create registry and hub
        registry = AgentRegistry()
        hub = CommunicationHub(registry)
        
        # Create prompt tools with custom tools
        prompt_tools = PromptTools(agent_registry=registry, communication_hub=hub)
        
        # Define our custom data analysis tool function
        def analyze_weather_data(
            data: str, 
            analysis_type: str = "trends"
        ) -> Dict[str, Any]:
            """
            Analyze weather data and extract insights.
            
            Args:
                data: Weather data in text format
                analysis_type: Type of analysis (trends, anomalies, forecast)
                
            Returns:
                Dictionary with analysis results
            """
            # In a real implementation, this would perform actual data analysis
            # This is a mock implementation for demonstration
            
            analysis_results = {
                "trends": {
                    "summary": "Temperatures are trending 2°C higher than seasonal average",
                    "confidence": 0.89,
                    "key_points": ["Rising humidity levels", "Consistent pressure patterns"],
                },
                "anomalies": {
                    "summary": "Detected unusual wind pattern shifts",
                    "confidence": 0.76,
                    "key_points": ["Rapid pressure changes", "Unseasonable precipitation"],
                },
                "forecast": {
                    "summary": "Expect continued warming with periodic precipitation",
                    "confidence": 0.82,
                    "key_points": ["Temperature peaks mid-week", "Weekend cooling trend"],
                }
            }
            
            # Return the appropriate analysis or a default
            return analysis_results.get(
                analysis_type,
                {"summary": "Basic analysis completed", "confidence": 0.5, "key_points": []}
            )
        
        # Create the asynchronous version
        async def analyze_weather_data_async(
            data: str, 
            analysis_type: str = "trends"
        ) -> Dict[str, Any]:
            return analyze_weather_data(data, analysis_type)
        
        # Register our custom analysis tool
        analysis_tool = prompt_tools.create_tool_from_function(
            func=analyze_weather_data,
            name="analyze_weather_data",
            description="Analyze weather data and extract insights",
            args_schema=type('AnalysisInput', (BaseModel,), {
                "data": (str, Field(description="Weather data to analyze")),
                "analysis_type": (str, Field(description="Type of analysis to perform"))
            }),
            category="analysis",
            coroutine=analyze_weather_data_async
        )
        
        # Create an advanced AI agent with custom tools
        advanced_agent = AIAgent(
            agent_id="weather_expert",
            name="Advanced Weather Expert",
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O,
            api_key=os.getenv("OPENAI_API_KEY"),
            identity=AgentIdentity.create_key_based(),
            capabilities=[
                Capability(
                    name="weather_analysis",
                    description="Advanced analysis of weather patterns and data",
                    input_schema={"data": "string", "location": "string"},
                    output_schema={"analysis": "string", "recommendations": "string"}
                ),
                Capability(
                    name="task_management",
                    description="Can break down complex weather-related requests into subtasks",
                    input_schema={"request": "string"},
                    output_schema={"subtasks": "array"}
                )
            ],
            personality="methodical and detail-oriented weather scientist",
            organization_id="example_org",
            interaction_modes=[InteractionMode.HUMAN_TO_AGENT, InteractionMode.AGENT_TO_AGENT],
            prompt_tools=prompt_tools,
            custom_tools=[analysis_tool],  # Include our custom analysis tool
        )
        
        # Create a custom message handler for task decomposition
        async def task_decomposition_handler(message):
            if "analyze" in message.content.lower() and "weather" in message.content.lower():
                # This is a complex weather analysis task - decompose it
                decomposition_result = await prompt_tools.create_task_decomposition_tool().acoroutine(
                    task_description=message.content,
                    max_subtasks=3
                )
                
                print("Task decomposed into subtasks:")
                for idx, subtask in enumerate(decomposition_result.get("subtasks", [])):
                    print(f"  {idx+1}. {subtask.get('title')}: {subtask.get('description')}")
        
        # Register the agent and add the message handler
        await hub.register_agent(advanced_agent)
        hub.add_message_handler("weather_expert", task_decomposition_handler)
        
        # Start the agent's processing
        agent_task = asyncio.create_task(advanced_agent.run())
        
        # Create a human agent for interaction
        human = HumanAgent(
            agent_id="user",
            name="Example User",
            identity=AgentIdentity.create_key_based(),
            organization_id="example_org",
        )
        
        await hub.register_agent(human)
        
        # Simulate a complex weather analysis request
        await human.send_message(
            "weather_expert",
            "Please analyze the recent weather patterns in the Northeastern United States "
            "and provide insights on how they compare to historical data. Also suggest "
            "what this might indicate for agricultural planning in the region."
        )
        
        # Allow time for processing and task decomposition
        await asyncio.sleep(10)
        
        # Clean up
        advanced_agent.is_running = False
        await agent_task
        await hub.unregister_agent(advanced_agent.agent_id)
        await hub.unregister_agent(human.agent_id)
    
    if __name__ == "__main__":
        asyncio.run(run_advanced_agent_example())

Creating Custom Tool Registry and Workflow
----------------------------------------

For even more advanced use cases, you can create a custom tool registry:

.. code-block:: python

    from agentconnect.prompts.tools import ToolRegistry
    from langchain_core.tools import BaseTool
    
    # Create a custom tool registry
    custom_registry = ToolRegistry()
    
    # Define a simple custom tool
    def generate_weather_report(location: str, time_period: str = "today") -> str:
        """Generate a weather report for a location."""
        reports = {
            "New York": {
                "today": "Sunny with a high of 75°F, light winds from the west.",
                "tomorrow": "Partly cloudy with a chance of afternoon showers, high of 72°F.",
                "week": "Mostly sunny throughout the week with temperatures between 70-80°F."
            },
            "London": {
                "today": "Overcast with light rain, high of 18°C, moderate humidity.",
                "tomorrow": "Continued light rain with fog in the morning, high of 17°C.",
                "week": "Clearing by mid-week with temperatures around 16-20°C."
            }
        }
        
        # Get the report for the location and time period or return a default
        location_reports = reports.get(location, {})
        return location_reports.get(
            time_period, 
            f"Weather report for {location} ({time_period}): Generally favorable conditions."
        )
    
    # Create a LangChain-compatible tool
    from langchain.tools import Tool
    
    report_tool = Tool.from_function(
        func=generate_weather_report,
        name="generate_weather_report",
        description="Generates a weather report for a specific location and time period",
    )
    
    # Register the tool with our custom registry
    custom_registry.register_tool(report_tool)
    
    # Now we can use this tool registry with our agents or workflows
    # And access tools by name or category
    weather_tools = custom_registry.get_tools_by_category("weather")
    
    # Get a specific tool by name
    report_tool = custom_registry.get_tool("generate_weather_report")

LangChain and LangGraph Integration
----------------------------------

AgentConnect offers full compatibility with LangChain v0.3.x and LangGraph, allowing you to directly use their powerful tools and agents within the AgentConnect framework:

.. code-block:: python

    import os
    import asyncio
    from typing import List, Dict, Any
    from dotenv import load_dotenv
    
    # LangChain imports
    from langchain_core.tools import BaseTool, StructuredTool, Tool
    from langchain_openai import ChatOpenAI
    from langchain.agents import tool
    from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper
    from langchain_community.tools.tavily_search import TavilySearchResults
    
    # LangGraph imports
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    
    # AgentConnect imports
    from agentconnect.agents.ai_agent import AIAgent
    from agentconnect.core.registry import AgentRegistry
    from agentconnect.communication.hub import CommunicationHub
    from agentconnect.core.types import (
        ModelProvider,
        ModelName,
        AgentIdentity,
        InteractionMode,
        Capability
    )
    
    # Load environment variables
    load_dotenv()
    
    # Initialize registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)
    
    # Create LangChain tools
    # 1. Using the @tool decorator (langchain v0.3.x style)
    @tool
    def calculate_risk_score(market_data: str, risk_factors: List[str]) -> Dict[str, Any]:
        """Calculate investment risk score based on market data and risk factors."""
        # Simple mock implementation for demonstration
        risk_score = len(risk_factors) * 10
        return {
            "risk_score": risk_score,
            "risk_level": "high" if risk_score > 70 else "medium" if risk_score > 40 else "low",
            "recommendation": "Diversify" if risk_score > 70 else "Hold" if risk_score > 40 else "Invest"
        }
    
    # 2. Using TavilySearchResults - a real external tool from LangChain
    search_tool = TavilySearchResults(
        api_key=os.getenv("TAVILY_API_KEY", "your-tavily-api-key"),
        max_results=3
    )
    
    # Create an AIAgent that uses LangChain tools
    langchain_agent = AIAgent(
        agent_id="investment_advisor",
        name="Investment Advisor",
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key=os.getenv("OPENAI_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        capabilities=[
            Capability(
                name="investment_advice",
                description="Provides investment advice based on market conditions",
                input_schema={"query": "string", "risk_profile": "string"},
                output_schema={"advice": "string", "risk_analysis": "string"}
            )
        ],
        personality="cautious and data-driven financial advisor",
        organization_id="example_org",
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
        # Include LangChain tools directly in the custom_tools parameter
        custom_tools=[calculate_risk_score, search_tool],
    )
    
    # Register the agent
    async def setup_langchain_agent():
        await hub.register_agent(langchain_agent)
        print("Registered investment advisor with LangChain tools")
    
    # Run the setup
    asyncio.run(setup_langchain_agent())

Creating Advanced Workflows with LangGraph
----------------------------------------

You can also use LangGraph for complex agent workflows within AgentConnect:

.. code-block:: python

    from typing import TypedDict, Sequence, Annotated
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
    from langgraph.graph import StateGraph
    from langgraph.graph.message import add_messages

    # Define a state for our custom workflow
    class InvestmentState(TypedDict):
        """State for the investment advisor workflow."""
        messages: Annotated[Sequence[BaseMessage], add_messages]
        market_data: dict
        risk_profile: str
        recommendations: list
        current_step: str

    # Create a custom workflow for investment advice
    def create_investment_workflow(llm):
        # Create nodes for the workflow
        def get_market_data(state: InvestmentState) -> InvestmentState:
            """Get current market data."""
            # In a real implementation, this would call an API or database
            state["market_data"] = {
                "sp500": 4780.5,
                "nasdaq": 16950.2,
                "volatility_index": 18.2,
                "treasury_yield": 4.1,
                "sector_momentum": {
                    "tech": "positive",
                    "healthcare": "neutral",
                    "energy": "negative",
                    "financials": "positive",
                },
            }
            state["current_step"] = "analyze_risk"
            return state

        def analyze_risk(state: InvestmentState) -> InvestmentState:
            """Analyze risk based on market data and profile."""
            risk_score = 0
            
            # Simple risk calculation based on market data and profile
            if state["risk_profile"] == "conservative":
                risk_tolerance = 30
            elif state["risk_profile"] == "moderate":
                risk_tolerance = 60
            else:  # aggressive
                risk_tolerance = 90
                
            volatility = state["market_data"]["volatility_index"]
            
            # Basic risk calculation
            if volatility > 25:
                risk_score = 80
            elif volatility > 15:
                risk_score = 50
            else:
                risk_score = 30
                
            # Adjust based on profile
            adjusted_risk = min(100, risk_score * (risk_tolerance / 60))
            
            state["risk_analysis"] = {
                "score": adjusted_risk,
                "level": "high" if adjusted_risk > 70 else "medium" if adjusted_risk > 40 else "low",
            }
            
            state["current_step"] = "generate_recommendations"
            return state

        def generate_recommendations(state: InvestmentState) -> InvestmentState:
            """Generate investment recommendations."""
            # This would use the LLM in a real implementation
            risk_level = state["risk_analysis"]["level"]
            sector_momentum = state["market_data"]["sector_momentum"]
            
            recommendations = []
            if risk_level == "low":
                recommendations.append("Consider Treasury bonds with current yield of {:.1f}%".format(
                    state["market_data"]["treasury_yield"]
                ))
                # Add more conservative recommendations...
            elif risk_level == "medium":
                # Add balanced recommendations...
                for sector, momentum in sector_momentum.items():
                    if momentum == "positive":
                        recommendations.append(f"Consider moderate exposure to {sector} sector ETFs")
            else:  # high
                # Add aggressive recommendations...
                for sector, momentum in sector_momentum.items():
                    if momentum == "positive":
                        recommendations.append(f"Consider significant exposure to {sector} sector individual stocks")
            
            state["recommendations"] = recommendations
            state["current_step"] = "summarize"
            return state

        def summarize(state: InvestmentState) -> InvestmentState:
            """Summarize the analysis and recommendations."""
            # Here we could use the LLM to generate a natural language summary
            summary = (
                f"Based on current market conditions and your {state['risk_profile']} risk profile, "
                f"your risk level is {state['risk_analysis']['level']} "
                f"with a score of {state['risk_analysis']['score']:.1f}/100.\n\n"
                "Recommendations:\n"
            )
            
            for rec in state["recommendations"]:
                summary += f"- {rec}\n"
                
            # Add the summary as an AI message
            state["messages"].append(AIMessage(content=summary))
            state["current_step"] = "complete"
            return state

        # Create the state graph
        workflow = StateGraph(InvestmentState)
        
        # Add nodes
        workflow.add_node("get_market_data", get_market_data)
        workflow.add_node("analyze_risk", analyze_risk)
        workflow.add_node("generate_recommendations", generate_recommendations)
        workflow.add_node("summarize", summarize)
        
        # Add edges
        workflow.add_edge("get_market_data", "analyze_risk")
        workflow.add_edge("analyze_risk", "generate_recommendations")
        workflow.add_edge("generate_recommendations", "summarize")
        workflow.add_edge("summarize", END)
        
        # Set the entry point
        workflow.set_entry_point("get_market_data")
        
        # Compile the workflow
        return workflow.compile()

    # Create an AIAgent that uses a LangGraph workflow
    async def create_langgraph_agent():
        # Create an OpenAI LLM
        llm = ChatOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name="gpt-4o",
            temperature=0.2
        )
        
        # Create the investment workflow
        investment_workflow = create_investment_workflow(llm)
        
        # Create a custom agent that will use this workflow
        portfolio_advisor = AIAgent(
            agent_id="portfolio_advisor",
            name="Portfolio Advisor",
            provider_type=ModelProvider.OPENAI,
            model_name=ModelName.GPT4O,
            api_key=os.getenv("OPENAI_API_KEY"),
            identity=AgentIdentity.create_key_based(),
            capabilities=[
                Capability(
                    name="portfolio_management",
                    description="Creates personalized investment portfolios",
                    input_schema={"risk_profile": "string", "goals": "string"},
                    output_schema={"portfolio": "string", "rationale": "string"}
                )
            ],
            personality="methodical and data-driven investment advisor",
            organization_id="example_org",
            interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
        )
        
        # Register the agent
        await hub.register_agent(portfolio_advisor)
        
        # In a real implementation, you would set up a message handler
        # that invokes the LangGraph workflow when appropriate
        
        async def portfolio_message_handler(message):
            if "portfolio" in message.content.lower() or "invest" in message.content.lower():
                # Initialize the workflow state
                initial_state = {
                    "messages": [HumanMessage(content=message.content)],
                    "market_data": {},
                    "risk_profile": "moderate",  # Extract this from message in real implementation
                    "recommendations": [],
                    "current_step": "start"
                }
                
                # Run the workflow
                result = investment_workflow.invoke(initial_state)
                
                # Extract the response from the workflow
                response_content = result["messages"][-1].content
                
                print(f"Portfolio recommendation: {response_content[:100]}...")
                
                # Here you would send the response back to the user
        
        # Add the message handler
        hub.add_message_handler("portfolio_advisor", portfolio_message_handler)
        
        print("Registered portfolio advisor with LangGraph workflow")
    
    # Run the setup
    asyncio.run(create_langgraph_agent()) 