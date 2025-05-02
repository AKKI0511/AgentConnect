.. _external_tools:

Integrating External Tools with AIAgent
========================================

Introduction
-----------

While ``AIAgent`` comes with built-in collaboration tools and optional payment capabilities, many applications require specialized functionality specific to your domain. You might need agents that can:

* Query your organization's proprietary database
* Call your internal APIs
* Perform domain-specific calculations or transformations
* Access external services only your system has credentials for

AgentConnect allows you to extend agent capabilities by integrating standard `LangChain tools <https://python.langchain.com/docs/modules/tools/>`_, providing a flexible way to equip your agents with the exact functionality they need.

Adding Custom LangChain Tools
----------------------------

AgentConnect's ``AIAgent`` class accepts a ``custom_tools`` parameter in its constructor. This parameter takes a list of LangChain ``BaseTool`` instances (or tools created with decorators like ``@tool``).

Here's a simple example showing how to create and add custom tools:

.. code-block:: python

    import os
    from langchain_core.tools import tool
    from langchain.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    from agentconnect.agents import AIAgent
    from agentconnect.core.types import ModelProvider, ModelName, AgentIdentity
    
    # Simple tool using the @tool decorator
    @tool
    def calculate_compound_interest(principal: float, rate: float, time: int, compounds_per_year: int = 1) -> float:
        """
        Calculate compound interest for an investment.
        
        Args:
            principal: Initial investment amount
            rate: Annual interest rate (as a decimal, e.g. 0.05 for 5%)
            time: Time period in years
            compounds_per_year: Number of times interest compounds per year (default: 1)
            
        Returns:
            The final amount after compound interest
        """
        return principal * (1 + rate/compounds_per_year)**(compounds_per_year*time)
    
    # More complex tool using StructuredTool with Pydantic models
    class WeatherQueryInput(BaseModel):
        """Input for weather query."""
        location: str = Field(description="City name or zip code")
        forecast_days: int = Field(default=1, description="Number of days to forecast (1-7)")
    
    class WeatherQueryOutput(BaseModel):
        """Output for weather query."""
        temperature: float = Field(description="Current temperature in Celsius")
        conditions: str = Field(description="Weather conditions (e.g., sunny, rainy)")
        forecast: str = Field(description="Text forecast for the requested period")
    
    def get_weather(input_data: WeatherQueryInput) -> WeatherQueryOutput:
        """
        Get weather information for a specific location.
        
        This is a mock implementation. In a real application, you would:
        1. Call your weather API with the provided location
        2. Parse the response
        3. Return properly formatted data
        """
        # Mock implementation - in real code you would call a weather API
        # such as OpenWeatherMap, Weather.gov, etc.
        return WeatherQueryOutput(
            temperature=22.5,
            conditions="Partly Cloudy",
            forecast=f"Forecast for the next {input_data.forecast_days} days: Warm and partly cloudy."
        )
    
    # Create the structured tool
    weather_tool = StructuredTool.from_function(
        func=get_weather,
        name="get_weather",
        description="Get weather information for a specific location",
        args_schema=WeatherQueryInput,
        return_direct=False
    )
    
    # Initialize an AIAgent with custom tools
    agent = AIAgent(
        agent_id="domain_expert",
        name="Domain Expert Agent",
        provider_type=ModelProvider.ANTHROPIC,
        model_name=ModelName.CLAUDE_3_OPUS,
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        custom_tools=[calculate_compound_interest, weather_tool],  # Add your custom tools here
        personality="You are a helpful assistant that specializes in financial calculations and weather forecasting."
    )

When you provide ``custom_tools``, they are automatically added to the pool of tools available to the agent's internal LLM workflow. These tools will be available alongside any built-in collaboration or payment tools that the agent has access to.

Based on the user's requests and the conversation context, the agent's LLM will decide when to use these custom tools. The agent treats these tools as part of its capabilities and can invoke them when appropriate.

How Custom Tools Work With the Agent
-----------------------------------

When a user interacts with an agent equipped with custom tools, the workflow typically looks like this:

1. The user sends a request to the agent (e.g., "What would my $1000 investment be worth in 5 years at 7% interest?")
2. The agent's LLM processes the request and recognizes that it needs to perform a financial calculation
3. The LLM decides to use the ``calculate_compound_interest`` tool based on its description and parameters
4. The agent invokes the tool with the appropriate parameters
5. The tool returns the result to the agent
6. The agent incorporates the result into its response to the user

This process happens automatically within the agent's internal workflow, making the use of tools transparent to end users.

Designing Effective Custom Tools
------------------------------

For your custom tools to work optimally with AI agents, follow these best practices:

1. **Clear, Descriptive Names**: Use names that clearly indicate the tool's purpose (e.g., ``get_weather`` instead of ``weather_func``).

2. **Detailed Descriptions**: Include comprehensive docstrings or descriptions. The LLM relies on these to understand when and how to use the tool.

3. **Well-Defined Input Schemas**: Use type hints for simple tools or Pydantic models for more complex ones. This helps the LLM understand what parameters to provide.

4. **Error Handling**: Implement proper error handling in your tools to provide useful feedback when things go wrong.

5. **Focused Functionality**: Each tool should do one thing well. Break complex operations into multiple tools rather than creating monolithic functions.

6. **Consistent Return Types**: Make sure your tools return consistent data structures that the LLM can easily interpret and incorporate into responses.

.. code-block:: python

    # Example of a well-designed tool with clear typing, description, and error handling
    @tool
    def search_customer_database(customer_id: str) -> dict:
        """
        Search the customer database for a specific customer and return their information.
        
        Args:
            customer_id: The unique identifier for the customer (format: CUS-XXXXX)
            
        Returns:
            A dictionary containing customer information (name, email, subscription status, etc.)
            
        Raises:
            ValueError: If customer_id is not in the correct format
            KeyError: If no customer with the given ID exists
        """
        # Validate input
        if not customer_id.startswith("CUS-"):
            raise ValueError("Customer ID must be in format CUS-XXXXX")
            
        # Implement actual database query logic here
        # ...
        
        # Return customer data
        return {
            "name": "John Doe",
            "email": "john.doe@example.com",
            "subscription": "Premium",
            "signup_date": "2023-01-15"
        }

.. admonition:: Advanced Customization Planned
   :class: note

   This guide covers the standard method of adding discrete tools to agents. In future releases, 
   AgentConnect plans to support deeper levels of customization, potentially allowing developers to:
   
   * Inject entirely custom internal workflows (e.g., complex LangGraph state machines)
   * Fully override default prompt templates
   * Define custom input/output schemas for the agent's core processing logic
   * Integrate agents built with other frameworks
   
   Detailed guides and enhanced framework support for these advanced scenarios are planned for future releases.
   For now, ``custom_tools`` is the primary extension mechanism.

Next Steps
---------

To learn more about configuring and using agents:

* See :doc:`agent_configuration` for other agent parameters
* Explore the :doc:`/examples/index` section for practical examples
* Refer to the `LangChain documentation <https://python.langchain.com/docs/how_to/>`_ for more details on creating and using tools

By combining AgentConnect's built-in capabilities with your own custom tools, you can create agents that are perfectly tailored to your specific use cases and domain requirements. 