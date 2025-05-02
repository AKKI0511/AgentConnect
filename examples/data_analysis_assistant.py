#!/usr/bin/env python
"""
Advanced Multi-Agent Data Analysis Assistant Example

This example demonstrates a sophisticated multi-agent system using AgentConnect:
1. Core Interaction Agent: Primary interface between user and specialized agents
2. Data Analysis Agent: Processes and analyzes data using pandas and visualization tools
3. Visualization Agent: Creates interactive visualizations with Plotly
4. Insight Generation Agent: Extracts meaningful insights from analysis results

This showcases:
- Multi-agent collaboration
- Memory persistence
- Task delegation and specialized agent capabilities
- Human-in-the-loop interaction
- Capability-based agent discovery
- Integration with real-world data analysis tools

Required Environment Variables:
- GOOGLE_API_KEY: API key for Google's Gemini models
- LANGCHAIN_TRACING_V2: Set to 'true' to enable LangSmith tracing (optional)
- LANGCHAIN_API_KEY: API key for LangSmith if tracing is enabled (optional)
"""

import asyncio
import os
from typing import Any, Dict, List, Optional

import pandas as pd

# Add new imports for real-world tools
import plotly.express as px
from colorama import Fore, Style, init
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from agentconnect.agents.ai_agent import AIAgent
from agentconnect.agents.human_agent import HumanAgent
from agentconnect.communication.hub import CommunicationHub
from agentconnect.core.agent import AgentIdentity
from agentconnect.core.registry import AgentRegistry
from agentconnect.core.types import Capability, ModelName, ModelProvider
from agentconnect.prompts.tools import PromptTools
from agentconnect.utils.logging_config import (
    LogLevel,
    disable_all_logging,
    setup_logging,
)

# Initialize colorama for cross-platform colored output
init()

# Define colors for different message types
COLORS = {
    "SYSTEM": Fore.YELLOW,
    "USER": Fore.GREEN,
    "AI": Fore.CYAN,
    "ERROR": Fore.RED,
    "INFO": Fore.MAGENTA,
    "DATA": Fore.BLUE,
    "VISUALIZATION": Fore.WHITE,
    "INSIGHT": Fore.LIGHTGREEN_EX,
}


def print_colored(message: str, color_type: str = "SYSTEM") -> None:
    """Print a message with specified color"""
    color = COLORS.get(color_type, Fore.WHITE)
    print(f"{color}{message}{Style.RESET_ALL}")


# Custom tool schemas for specialized agents
class DataAnalysisInput(BaseModel):
    """Input schema for data analysis tool."""

    data_source: str = Field(
        description="The data source to analyze (file path, URL, or sample data name)."
    )
    analysis_type: str = Field(
        description="Type of analysis to perform (descriptive, correlation, etc.)."
    )
    columns: Optional[str] = Field(
        default="", description="Specific columns to analyze, comma-separated."
    )

    model_config = {"arbitrary_types_allowed": True}


class DataAnalysisOutput(BaseModel):
    """Output schema for data analysis tool."""

    results: Dict[str, Any] = Field(description="Analysis results.")
    summary: str = Field(description="Summary of the analysis findings.")


class VisualizationInput(BaseModel):
    """Input schema for visualization tool."""

    data_source: str = Field(
        description="The data source to visualize (file path, URL, or sample data name)"
    )
    chart_type: str = Field(
        description="Type of chart to create (bar, line, scatter, etc.)."
    )
    x_column: Optional[str] = Field(
        default=None, description="Column to use for x-axis."
    )
    y_column: Optional[str] = Field(
        default=None, description="Column to use for y-axis."
    )
    title: Optional[str] = Field(
        default=None, description="Title for the visualization."
    )

    model_config = {"arbitrary_types_allowed": True}


class VisualizationOutput(BaseModel):
    """Output schema for visualization tool."""

    plot_data: str = Field(
        description="The visualization data (base64 encoded or JSON)."
    )
    plot_type: str = Field(description="The type of plot that was created.")


class InsightInput(BaseModel):
    """Input schema for insight generation tool."""

    analysis_summary: str = Field(description="Summary of the analysis results.")
    visualization_type: Optional[str] = Field(
        default=None, description="Type of visualization that was created."
    )
    focus_area: Optional[str] = Field(
        default=None, description="Specific area to focus insights on."
    )

    model_config = {"arbitrary_types_allowed": True}


class InsightOutput(BaseModel):
    """Output schema for insight generation tool."""

    insights: List[str] = Field(description="List of insights extracted from the data.")
    recommendations: Optional[List[str]] = Field(
        default=None, description="Recommendations based on insights."
    )

    model_config = {"arbitrary_types_allowed": True}


# Sample datasets for quick testing
SAMPLE_DATASETS = {
    "titanic": "https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv",
    "iris": "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv",
    "housing": "https://raw.githubusercontent.com/ageron/handson-ml/master/datasets/housing/housing.csv",
    "stocks": "https://raw.githubusercontent.com/plotly/datasets/master/finance-charts-apple.csv",
}


async def setup_agents():
    """Set up the registry, hub, and agents"""
    # Create registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    # Create human agent
    human_identity = AgentIdentity.create_key_based()
    human_agent = HumanAgent(
        agent_id="human_user",
        name="Human User",
        identity=human_identity,
    )

    # Create core interaction agent
    core_identity = AgentIdentity.create_key_based()
    core_capabilities = [
        Capability(
            name="task_routing",
            description="Routes tasks to appropriate specialized agents",
            input_schema={"task": "string"},
            output_schema={"agent_id": "string", "task": "string"},
        ),
        Capability(
            name="conversation_management",
            description="Maintains conversation context across multiple turns",
            input_schema={"conversation_history": "string"},
            output_schema={"context_summary": "string"},
        ),
        Capability(
            name="result_presentation",
            description="Presents final results to the user in a coherent manner",
            input_schema={"results": "string"},
            output_schema={"presentation": "string"},
        ),
    ]

    core_agent = AIAgent(
        agent_id="core_agent",
        name="Core Interaction Agent",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH_LITE,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=core_identity,
        capabilities=core_capabilities,
        personality="I am the primary interface between you and specialized agents. I understand your requests, delegate tasks to specialized agents, and present their findings in a coherent manner. I maintain conversation context and ensure a smooth experience.",
    )

    # Create data analysis agent
    data_analysis_identity = AgentIdentity.create_key_based()
    data_analysis_capabilities = [
        Capability(
            name="data_loading",
            description="Loads data from various sources including CSV, Excel, and URLs",
            input_schema={"source": "string", "format": "string"},
            output_schema={"data": "object", "summary": "string"},
        ),
        Capability(
            name="data_cleaning",
            description="Cleans and preprocesses data by handling missing values, outliers, and formatting issues",
            input_schema={"data": "object", "operations": "list"},
            output_schema={"cleaned_data": "object", "changes_made": "list"},
        ),
        Capability(
            name="statistical_analysis",
            description="Performs statistical analysis including descriptive statistics, hypothesis testing, and correlation analysis",
            input_schema={"data": "object", "analysis_type": "string"},
            output_schema={"results": "object", "interpretation": "string"},
        ),
        Capability(
            name="data_transformation",
            description="Transforms data through operations like aggregation, filtering, and feature engineering",
            input_schema={"data": "object", "transformations": "list"},
            output_schema={
                "transformed_data": "object",
                "transformation_summary": "string",
            },
        ),
    ]

    # Create pandas dataframe agent tool
    def analyze_dataframe(
        data_source: str, analysis_type: str, columns: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a pandas DataFrame using pandas and basic statistical methods.

        Args:
            data_source: The data source to analyze (file path, URL, or sample data name)
            analysis_type: Type of analysis to perform (descriptive, correlation, etc.)
            columns: Specific columns to analyze (comma-separated string)

        Returns:
            Dict containing analysis results and summary
        """
        print_colored(
            f"Analyzing data from {data_source} with {analysis_type} analysis", "DATA"
        )

        try:
            # Load the data
            if data_source in SAMPLE_DATASETS:
                df = pd.read_csv(SAMPLE_DATASETS[data_source])
                print_colored(f"Loaded sample dataset: {data_source}", "DATA")
            elif data_source.startswith("http"):
                df = pd.read_csv(data_source)
                print_colored(f"Loaded data from URL: {data_source}", "DATA")
            else:
                try:
                    df = pd.read_csv(data_source)
                    print_colored(f"Loaded CSV data from: {data_source}", "DATA")
                except:
                    try:
                        df = pd.read_excel(data_source)
                        print_colored(f"Loaded Excel data from: {data_source}", "DATA")
                    except:
                        return {
                            "results": {
                                "error": f"Could not load data from {data_source}"
                            },
                            "summary": f"Error: Failed to load data from {data_source}. Please check the file path or URL.",
                        }

            # Filter columns if specified
            if columns:
                # Convert comma-separated string to list
                column_list = [col.strip() for col in columns.split(",")]
                available_columns = [col for col in column_list if col in df.columns]
                if available_columns:
                    df = df[available_columns]
                    print_colored(f"Filtered to columns: {available_columns}", "DATA")
                else:
                    print_colored(
                        f"Warning: None of the specified columns {column_list} found in the data",
                        "ERROR",
                    )

            # Initialize results dictionary
            results = {}
            summary = ""

            # Perform the requested analysis
            if analysis_type.lower() == "descriptive":
                # Basic descriptive statistics
                results["descriptive_stats"] = df.describe().to_dict()
                results["info"] = {
                    "shape": df.shape,
                    "columns": list(df.columns),
                    "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                    "missing_values": df.isnull().sum().to_dict(),
                }
                summary = f"Performed descriptive analysis on {df.shape[0]} rows and {df.shape[1]} columns."

            elif analysis_type.lower() == "correlation":
                # Correlation analysis
                numeric_df = df.select_dtypes(include=["number"])
                if not numeric_df.empty:
                    results["correlations"] = numeric_df.corr().to_dict()
                    summary = f"Performed correlation analysis on {len(numeric_df.columns)} numeric columns."
                else:
                    results["error"] = (
                        "No numeric columns available for correlation analysis"
                    )
                    summary = "Could not perform correlation analysis: no numeric columns found."

            elif analysis_type.lower() == "group":
                # Group analysis - try to find categorical columns for grouping
                categorical_cols = df.select_dtypes(
                    include=["object", "category"]
                ).columns.tolist()
                numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

                if categorical_cols and numeric_cols:
                    results["group_comparisons"] = {}
                    for cat_col in categorical_cols[
                        :3
                    ]:  # Limit to first 3 categorical columns
                        group_stats = (
                            df.groupby(cat_col)[numeric_cols]
                            .agg(["mean", "median"])
                            .to_dict()
                        )
                        results["group_comparisons"][cat_col] = group_stats
                    summary = f"Performed group analysis using {len(categorical_cols[:3])} categorical columns."
                else:
                    results["error"] = (
                        "Could not find appropriate categorical and numeric columns for group analysis"
                    )
                    summary = "Could not perform group analysis: need both categorical and numeric columns."
            else:
                # Default to basic analysis
                results["head"] = df.head().to_dict()
                results["shape"] = df.shape
                results["columns"] = list(df.columns)
                results["dtypes"] = {
                    col: str(dtype) for col, dtype in df.dtypes.items()
                }
                results["missing_values"] = df.isnull().sum().to_dict()
                summary = f"Performed basic analysis on dataset with {df.shape[0]} rows and {df.shape[1]} columns."

            return {"results": results, "summary": summary}

        except Exception as e:
            return {
                "results": {"error": str(e)},
                "summary": f"Error during analysis: {str(e)}",
            }

    # Create the data analysis agent with custom tools
    data_analysis_agent_tools = PromptTools(registry, hub)
    dataframe_analysis_tool = data_analysis_agent_tools.create_tool_from_function(
        func=analyze_dataframe,
        name="analyze_dataframe",
        description="Analyzes data using pandas and basic statistical methods",
        args_schema=DataAnalysisInput,
        category="data_analysis",
    )

    # Create data analysis agent with pandas dataframe agent
    data_analysis_agent = AIAgent(
        agent_id="data_analysis_agent",
        name="Data Analysis Agent",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=data_analysis_identity,
        capabilities=data_analysis_capabilities,
        personality="I am a data analysis specialist who excels at processing and analyzing data. I can load data from various sources, clean and preprocess it, perform statistical analysis, and transform data to extract meaningful insights.",
        custom_tools=[dataframe_analysis_tool],
    )

    # Create visualization agent
    visualization_identity = AgentIdentity.create_key_based()
    visualization_capabilities = [
        Capability(
            name="data_visualization",
            description="Creates various types of visualizations including bar charts, line charts, scatter plots, and heatmaps",
            input_schema={
                "data": "object",
                "chart_type": "string",
                "parameters": "object",
            },
            output_schema={"visualization": "object", "interpretation": "string"},
        ),
        Capability(
            name="interactive_plotting",
            description="Generates interactive plots with hover information, zooming, and filtering capabilities",
            input_schema={
                "data": "object",
                "plot_type": "string",
                "interactive_features": "list",
            },
            output_schema={"interactive_plot": "object"},
        ),
        Capability(
            name="multi_dimensional_visualization",
            description="Creates visualizations for multi-dimensional data using techniques like faceting, small multiples, and 3D plots",
            input_schema={"data": "object", "dimensions": "list"},
            output_schema={
                "visualization": "object",
                "dimension_explanation": "string",
            },
        ),
    ]

    # Create visualization tools
    def create_visualization(
        data_source: str,
        chart_type: str,
        x_column: Optional[str] = None,
        y_column: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Create interactive visualizations using Plotly.

        Args:
            data_source: The data source to visualize (file path, URL, or sample data name)
            chart_type: Type of chart to create (bar, line, scatter, etc.)
            x_column: Column to use for x-axis
            y_column: Column to use for y-axis
            title: Title for the visualization

        Returns:
            Dict containing the visualization data and type
        """
        print_colored(
            f"Creating {chart_type} visualization from {data_source}", "VISUALIZATION"
        )

        try:
            # Load the data
            if data_source in SAMPLE_DATASETS:
                df = pd.read_csv(SAMPLE_DATASETS[data_source])
                print_colored(f"Loaded sample dataset: {data_source}", "VISUALIZATION")
            elif data_source.startswith("http"):
                df = pd.read_csv(data_source)
                print_colored(f"Loaded data from URL: {data_source}", "VISUALIZATION")
            else:
                try:
                    df = pd.read_csv(data_source)
                    print_colored(
                        f"Loaded CSV data from: {data_source}", "VISUALIZATION"
                    )
                except:
                    try:
                        df = pd.read_excel(data_source)
                        print_colored(
                            f"Loaded Excel data from: {data_source}", "VISUALIZATION"
                        )
                    except:
                        return {
                            "plot_data": f"Error: Could not load data from {data_source}",
                            "plot_type": "error",
                        }

            # Set default columns if not provided
            if x_column is None and len(df.columns) > 0:
                x_column = df.columns[0]
            if y_column is None and len(df.columns) > 1:
                y_column = df.columns[1]

            # Set default title if not provided
            if title is None:
                title = f"{chart_type.capitalize()} Chart of {y_column} by {x_column}"

            # Create the visualization based on chart type
            if chart_type.lower() == "bar":
                fig = px.bar(df, x=x_column, y=y_column, title=title)
            elif chart_type.lower() == "line":
                fig = px.line(df, x=x_column, y=y_column, title=title)
            elif chart_type.lower() == "scatter":
                fig = px.scatter(df, x=x_column, y=y_column, title=title)
            elif chart_type.lower() == "histogram":
                fig = px.histogram(df, x=x_column, title=title)
            elif chart_type.lower() == "box":
                fig = px.box(df, x=x_column, y=y_column, title=title)
            elif chart_type.lower() == "violin":
                fig = px.violin(df, x=x_column, y=y_column, title=title)
            elif chart_type.lower() == "pie":
                fig = px.pie(df, names=x_column, values=y_column, title=title)
            else:
                # Default to a simple scatter plot
                fig = px.scatter(
                    df,
                    x=x_column,
                    y=y_column,
                    title=f"Default Scatter Plot of {y_column} by {x_column}",
                )

            # Update layout for better appearance
            fig.update_layout(
                template="plotly_white",
                title={"y": 0.95, "x": 0.5, "xanchor": "center", "yanchor": "top"},
            )

            # Convert to JSON for transmission
            plot_json = fig.to_json()

            return {"plot_data": plot_json, "plot_type": chart_type.lower()}

        except Exception as e:
            return {
                "plot_data": f"Error creating visualization: {str(e)}",
                "plot_type": "error",
            }

    # Create the visualization agent with custom tools
    visualization_agent_tools = PromptTools(registry, hub)
    visualization_tool = visualization_agent_tools.create_tool_from_function(
        func=create_visualization,
        name="create_visualization",
        description="Creates interactive visualizations from data using Plotly",
        args_schema=VisualizationInput,
        category="visualization",
    )

    visualization_agent = AIAgent(
        agent_id="visualization_agent",
        name="Visualization Agent",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=visualization_identity,
        capabilities=visualization_capabilities,
        personality="I am a visualization specialist who excels at creating insightful and interactive data visualizations. I can create various types of charts and plots to help users understand their data better.",
        custom_tools=[visualization_tool],
    )

    # Create insight generation agent
    insight_identity = AgentIdentity.create_key_based()
    insight_capabilities = [
        Capability(
            name="insight_extraction",
            description="Extracts meaningful insights from data analysis results and visualizations",
            input_schema={"analysis_results": "object", "visualization_data": "object"},
            output_schema={"insights": "list", "confidence": "object"},
        ),
        Capability(
            name="pattern_recognition",
            description="Identifies patterns, trends, and anomalies in data",
            input_schema={"data": "object", "pattern_types": "list"},
            output_schema={"patterns": "list", "explanation": "string"},
        ),
        Capability(
            name="recommendation_generation",
            description="Generates actionable recommendations based on data insights",
            input_schema={"insights": "list", "context": "string"},
            output_schema={"recommendations": "list", "justification": "string"},
        ),
    ]

    insight_agent = AIAgent(
        agent_id="insight_agent",
        name="Insight Generation Agent",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=insight_identity,
        capabilities=insight_capabilities,
        personality="I am an insight generation specialist who excels at extracting meaningful patterns and trends from data. I can identify key findings, recognize patterns, and generate actionable recommendations based on data analysis.",
    )

    # Register all agents with the hub
    await hub.register_agent(human_agent)
    await hub.register_agent(core_agent)
    await hub.register_agent(data_analysis_agent)
    await hub.register_agent(visualization_agent)
    await hub.register_agent(insight_agent)

    # Start the agent processing loops
    asyncio.create_task(core_agent.run())
    asyncio.create_task(data_analysis_agent.run())
    asyncio.create_task(visualization_agent.run())
    asyncio.create_task(insight_agent.run())

    return {
        "registry": registry,
        "hub": hub,
        "human_agent": human_agent,
        "core_agent": core_agent,
        "data_analysis_agent": data_analysis_agent,
        "visualization_agent": visualization_agent,
        "insight_agent": insight_agent,
    }


async def run_data_analysis_assistant_demo(enable_logging: bool = False) -> None:
    """
    Run the data analysis assistant demo with multiple specialized agents.

    Args:
        enable_logging (bool): Enable detailed logging for debugging. Defaults to False.
    """
    load_dotenv()

    # Check for required environment variables
    required_env_vars = {
        "GOOGLE_API_KEY": "Google API key for Gemini models",
    }

    optional_env_vars = {
        "LANGCHAIN_TRACING_V2": "Set to 'true' to enable LangSmith tracing",
        "LANGCHAIN_API_KEY": "API key for LangSmith if tracing is enabled",
    }

    missing_vars = [
        var for var, desc in required_env_vars.items() if not os.getenv(var)
    ]
    if missing_vars:
        print_colored("Error: Missing required environment variables:", "ERROR")
        for var in missing_vars:
            print_colored(f"  - {var}: {required_env_vars[var]}", "ERROR")
        print_colored(
            "\nPlease set these variables in your .env file or environment.", "ERROR"
        )
        return

    # Check for optional environment variables
    missing_optional_vars = []
    if os.getenv("LANGCHAIN_TRACING_V2") == "true" and not os.getenv(
        "LANGCHAIN_API_KEY"
    ):
        missing_optional_vars.append("LANGCHAIN_API_KEY")

    if missing_optional_vars:
        print_colored("Warning: Missing optional environment variables:", "INFO")
        for var in missing_optional_vars:
            print_colored(f"  - {var}: {optional_env_vars[var]}", "INFO")
        print_colored("These are not required but may enhance functionality.", "INFO")

    if enable_logging:
        setup_logging(
            level=LogLevel.WARNING,
            module_levels={
                "AgentRegistry": LogLevel.WARNING,
                "CommunicationHub": LogLevel.DEBUG,
                "src.agents.ai_agent": LogLevel.INFO,
                "src.agents.human_agent": LogLevel.WARNING,
                "src.core.agent": LogLevel.INFO,
                "src.prompts.tools": LogLevel.INFO,
            },
        )
    else:
        # Disable all logging when not in debug mode
        disable_all_logging()

    print_colored("=== Advanced Multi-Agent Data Analysis System Demo ===", "SYSTEM")
    print_colored(
        "This demo showcases a sophisticated multi-agent system using AgentConnect with LangGraph and LangChain.",
        "SYSTEM",
    )
    print_colored(
        "You'll interact with a core agent that delegates tasks to specialized agents.",
        "SYSTEM",
    )
    print_colored("Available specialized agents:", "SYSTEM")
    print_colored(
        "1. Core Interaction Agent - Routes tasks and maintains conversation context",
        "INFO",
    )
    print_colored(
        "2. Data Analysis Agent - Processes and analyzes data using pandas", "DATA"
    )
    print_colored(
        "3. Visualization Agent - Creates interactive visualizations with Plotly",
        "VISUALIZATION",
    )
    print_colored(
        "4. Insight Generation Agent - Extracts meaningful insights from analysis results",
        "INSIGHT",
    )
    print_colored("\nSample datasets available for quick testing:", "SYSTEM")
    for name, url in SAMPLE_DATASETS.items():
        print_colored(f"  - {name}: {url.split('/')[-1]}", "INFO")
    print_colored("\nSetting up agents...", "SYSTEM")

    try:
        # Set up agents
        agents = await setup_agents()

        print_colored("Agents are ready! Starting interaction...\n", "SYSTEM")
        print_colored(
            "You can ask the core agent to analyze data, create visualizations, or extract insights.",
            "SYSTEM",
        )
        print_colored(
            "Example: 'Load the titanic dataset, analyze survival rates by gender and class, and visualize the results.'",
            "SYSTEM",
        )
        print_colored("Type 'exit' to end the conversation.\n", "SYSTEM")

        # Start interaction with the core agent
        await agents["human_agent"].start_interaction(agents["core_agent"])

        # Clean up
        print_colored("\nCleaning up resources...", "SYSTEM")

        # Stop all agents
        for agent_id, agent in agents.items():
            if agent_id not in ["registry", "hub"] and agent_id != "human_agent":
                # Use the new stop method to properly clean up resources
                await agent.stop()
                # Unregister from the hub
                await agents["hub"].unregister_agent(agent.agent_id)

        print_colored("Demo completed successfully!", "SYSTEM")

    except Exception as e:
        print_colored(f"Error in multi-agent system demo: {str(e)}", "ERROR")
        raise


if __name__ == "__main__":
    asyncio.run(run_data_analysis_assistant_demo())
