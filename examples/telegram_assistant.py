#!/usr/bin/env python
"""
Advanced Telegram Bot Assistant with Multi-Agent Capabilities

This example demonstrates a sophisticated Telegram bot using the AgentConnect framework's
TelegramAIAgent class, which provides a seamless integration with the Telegram messaging platform.

Architecture:
1. Telegram Agent (TelegramAIAgent): Handles all Telegram interactions and serves as the primary
   interface between users and the AgentConnect ecosystem
2. Research Agent: Performs web searches and provides information
3. Markdown Formatting Agent: Formats content into well-structured text
4. Data Analysis Agent: Processes data and creates visualizations

Key Implementation Features:
- TelegramAIAgent Integration: Utilizes the agentconnect.agents.telegram.TelegramAIAgent class
  which handles all Telegram-specific operations including:
  - Message processing from both private and group chats
  - Media handling (images, documents, etc.)
  - Command routing (/start, /help, etc.)
  - Publishing messages/announcements to Telegram channels/groups
  - Editing messages/announcements in Telegram channels/groups
  - Bot lifecycle management (initialization, polling, shutdown)

- Multi-Agent Collaboration: Demonstrates how the Telegram agent can:
  - Process user requests and identify required specialized capabilities
  - Discover and collaborate with other agents in the system
  - Delegate tasks to specialized agents
  - Collect and present results back to Telegram users

- Specialized Capabilities:
  - Web search and information retrieval
  - Content formatting and organization
  - Data analysis and visualization
  - Asynchronous message processing

Required Environment Variables:
- TELEGRAM_BOT_TOKEN: API token for your Telegram bot (get from @BotFather)
- GOOGLE_API_KEY or another LLM provider API key (OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY)
- TAVILY_API_KEY: Optional API key for Tavily Search (get from https://tavily.com)

Usage:
1. Set environment variables
2. Run this script directly: python examples/telegram_assistant.py
3. Add the bot to Telegram and start interacting

For detailed documentation on the TelegramAIAgent and its features, see:
- agentconnect/agents/telegram/telegram_agent.py
- agentconnect/agents/telegram/README.md
"""

import asyncio
import os
import sys
from typing import Dict, List, Any
import logging
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Import directly from the agentconnect package
from agentconnect.agents import (
    AIAgent,
)
from agentconnect.agents.telegram.telegram_agent import TelegramAIAgent
from agentconnect.communication import CommunicationHub
from agentconnect.core.types import (
    AgentIdentity,
    Capability,
    ModelName,
    ModelProvider,
)
from agentconnect.core.registry import AgentRegistry
from agentconnect.utils.logging_config import (
    setup_logging,
    LogLevel,
)
from agentconnect.prompts.tools import PromptTools

# Add imports for real-world tools
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_community.document_loaders.tomarkdown import ToMarkdownLoader
from langchain.text_splitter import HTMLHeaderTextSplitter
from langchain.schema import Document
from langchain_community.document_transformers.markdownify import MarkdownifyTransformer

# Import for data analysis
import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend for server environments
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import io
import json
import os

# Set up logging
logger = logging.getLogger(__name__)


# Custom tool schemas for specialized agents
class WebSearchInput(BaseModel):
    """Input schema for web search tool."""

    query: str = Field(description="The search query to find information.")
    num_results: int = Field(
        default=3, description="Number of search results to return."
    )


class WebSearchOutput(BaseModel):
    """Output schema for web search tool."""

    results: List[Dict[str, str]] = Field(
        description="List of search results with title, snippet, and URL."
    )
    query: str = Field(description="The original search query.")


class MarkdownFormatInput(BaseModel):
    """Input schema for markdown formatting tool."""

    content: str = Field(description="The content to format as markdown.")
    format_type: str = Field(
        default="report",
        description="The type of markdown format to apply (report, documentation, etc.).",
    )


class MarkdownFormatOutput(BaseModel):
    """Output schema for markdown formatting tool."""

    formatted_content: str = Field(description="The content formatted in markdown.")
    format_applied: str = Field(description="The type of format that was applied.")


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
    """
    Set up the registry, hub, and agents.

    Returns:
        Dict[str, Any]: Dictionary containing registry, hub, and agents

    Raises:
        RuntimeError: If required API keys are missing
    """
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

    if not tavily_api_key:
        logger.warning(
            "Warning: TAVILY_API_KEY not found. Research capabilities will be limited.\n"
            "Get a free API key at https://tavily.com"
        )

    # Create registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    # Create Telegram agent
    telegram_identity = AgentIdentity.create_key_based()
    telegram_capabilities = [
        Capability(
            name="telegram_interface",
            description="Provides interface for Telegram users, handling messages and commands",
            input_schema={"message": "string", "chat_id": "string"},
            output_schema={"response": "string", "success": "boolean"},
        ),
    ]

    telegram_agent = TelegramAIAgent(
        agent_id="telegram_agent",
        name="Telegram Assistant",
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=telegram_identity,
        capabilities=telegram_capabilities,
        personality="I am a helpful and friendly Telegram assistant. I can answer questions, provide information, and collaborate with other specialized agents to solve complex problems.",
    )

    # Create research agent with web search capabilities
    research_identity = AgentIdentity.create_key_based()
    research_capabilities = [
        Capability(
            name="web_search",
            description="Searches the web for information on various topics",
            input_schema={"query": "string", "num_results": "integer"},
            output_schema={"results": "list"},
        ),
        Capability(
            name="research_report",
            description="Creates comprehensive research reports with proper citations",
            input_schema={"topic": "string", "depth": "string"},
            output_schema={"report": "string", "citations": "list"},
        ),
        Capability(
            name="query_planning",
            description="Generates effective search queries from user questions",
            input_schema={"question": "string"},
            output_schema={"queries": "list"},
        ),
    ]

    # Create research agent with Tavily Search tool
    custom_tools = []
    if tavily_api_key:
        try:
            tavily_search = TavilySearchResults(
                api_key=tavily_api_key,
                max_results=3,
                include_raw_content=True,
                include_images=False,
            )
            custom_tools.append(tavily_search)
        except Exception as e:
            logger.error(f"Error initializing Tavily search: {e}")

    research_agent = AIAgent(
        agent_id="research_agent",
        name="Research Agent",
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=research_identity,
        capabilities=research_capabilities,
        personality="I am a research specialist who excels at finding information on various topics. I generate effective search queries, retrieve information from the web, and synthesize findings into comprehensive reports with proper citations.",
        custom_tools=custom_tools,
    )

    # Create markdown formatting agent
    markdown_identity = AgentIdentity.create_key_based()
    markdown_capabilities = [
        Capability(
            name="markdown_formatting",
            description="Transforms content into well-formatted markdown",
            input_schema={"content": "string", "format_type": "string"},
            output_schema={"formatted_content": "string"},
        ),
        Capability(
            name="content_organization",
            description="Organizes content with consistent styling and structure",
            input_schema={"content": "string"},
            output_schema={"organized_content": "string"},
        ),
    ]

    # Create markdown formatting tools
    def format_markdown(content: str, format_type: str = "report") -> Dict[str, str]:
        """
        Format content as markdown using LangChain's document transformers and structured text splitting.
        Supports HTML-to-Markdown conversion and maintains document structure.

        Args:
            content (str): The content to format
            format_type (str): The type of format to apply (report, documentation, etc.)

        Returns:
            Dict[str, str]: Contains formatted content and format type
        """
        logger.info(f"Formatting content as {format_type} markdown")

        try:
            # Convert HTML to markdown if content contains HTML
            if "<" in content and ">" in content:
                markdown_transformer = MarkdownifyTransformer(
                    strip=["script", "style"],  # Remove unwanted elements
                    heading_style="ATX",  # Use # style headings
                    bullets="-",  # Use - for bullet points
                )
                docs = [Document(page_content=content)]
                converted_docs = markdown_transformer.transform_documents(docs)
                content = converted_docs[0].page_content

            # Use structured text splitting based on format type
            if format_type == "report":
                # Define headers to split on for reports
                headers_to_split_on = [
                    ("h1", "title"),
                    ("h2", "section"),
                    ("h3", "subsection"),
                ]

                try:
                    splitter = HTMLHeaderTextSplitter(
                        headers_to_split_on=headers_to_split_on
                    )

                    # Split and recombine with proper structure
                    splits = splitter.split_text(content)
                    formatted_content = "# Research Report\n\n"

                    # Add executive summary
                    formatted_content += "## Executive Summary\n"
                    formatted_content += "\n".join(
                        split.page_content[:200] for split in splits[:1]
                    )
                    formatted_content += "\n\n"

                    # Add main content with sections
                    formatted_content += "## Detailed Analysis\n\n"
                    for split in splits:
                        if "title" in split.metadata:
                            formatted_content += f"### {split.metadata['title']}\n\n"
                        formatted_content += split.page_content + "\n\n"

                    # Add references section
                    formatted_content += "## References\n"
                    formatted_content += (
                        "_Generated from the research content above._\n\n"
                    )
                except Exception:
                    # Fallback if HTML splitting fails
                    formatted_content = "# Research Report\n\n"
                    formatted_content += "## Executive Summary\n\n"
                    formatted_content += content[:300] + "...\n\n"
                    formatted_content += "## Detailed Analysis\n\n"
                    formatted_content += content + "\n\n"
                    formatted_content += "## References\n\n"
                    formatted_content += (
                        "_Generated from the research content above._\n\n"
                    )

            elif format_type == "documentation":
                # Use UnstructuredMarkdownLoader for documentation
                try:
                    loader = UnstructuredMarkdownLoader.from_str(content)
                    docs = loader.load()

                    formatted_content = "# Technical Documentation\n\n"
                    formatted_content += "## Overview\n\n"
                    formatted_content += docs[0].page_content[:200] + "...\n\n"
                    formatted_content += "## Detailed Documentation\n\n"
                    formatted_content += docs[0].page_content + "\n\n"
                    formatted_content += "## API Reference\n\n"
                    formatted_content += (
                        "_Generated from the documentation content above._\n"
                    )
                except Exception:
                    # Fallback
                    formatted_content = "# Technical Documentation\n\n"
                    formatted_content += content
            else:
                # For general formatting, use ToMarkdownLoader with error handling
                try:
                    loader = ToMarkdownLoader.from_str(content)
                    docs = loader.load()
                    formatted_content = f"# {format_type.title()}\n\n"
                    formatted_content += docs[0].page_content
                except Exception:
                    # Fallback
                    formatted_content = f"# {format_type.title()}\n\n"
                    formatted_content += content

            return {
                "formatted_content": formatted_content,
                "format_applied": format_type,
            }
        except Exception as e:
            logger.error(f"Error in markdown formatting: {e}")
            # Provide a basic fallback format
            return {
                "formatted_content": f"# {format_type.title()}\n\n{content}",
                "format_applied": "basic",
            }

    # Create data analysis agent with visualization capabilities
    data_analysis_identity = AgentIdentity.create_key_based()
    data_analysis_capabilities = [
        Capability(
            name="data_analysis",
            description="Analyzes data and provides insights",
            input_schema={"data": "string", "analysis_type": "string"},
            output_schema={"result": "string", "visualization_path": "string"},
        ),
        Capability(
            name="data_visualization",
            description="Creates visualizations from data",
            input_schema={"data": "string", "chart_type": "string"},
            output_schema={"visualization_path": "string", "description": "string"},
        ),
    ]

    # Function for data analysis tool
    def analyze_data(data: str, analysis_type: str = "summary") -> Dict[str, str]:
        """
        Analyze data and generate visualizations.

        Args:
            data (str): Data in CSV or JSON format
            analysis_type (str): Type of analysis to perform

        Returns:
            Dict[str, str]: Results of analysis and path to any visualizations
        """
        logger.info(f"Performing {analysis_type} analysis on data")

        # Create a directory for visualizations if it doesn't exist
        viz_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "visualizations"
        )
        if not os.path.exists(viz_dir):
            os.makedirs(viz_dir)

        try:
            # Load data
            if data.startswith("{") or data.startswith("["):
                # Try to parse as JSON
                data_dict = json.loads(data)
                df = pd.DataFrame(data_dict)
            else:
                # Try to parse as CSV
                df = pd.read_csv(io.StringIO(data))

            # Get basic stats
            num_rows, num_cols = df.shape
            column_types = df.dtypes.to_dict()
            numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
            categorical_columns = df.select_dtypes(include=["object"]).columns.tolist()

            summary = f"Dataset has {num_rows} rows and {num_cols} columns.\n\n"

            if analysis_type == "summary":
                # Basic summary statistics
                summary += "## Summary Statistics\n\n"
                for col in numeric_columns:
                    summary += f"### {col}\n"
                    summary += f"- Mean: {df[col].mean():.2f}\n"
                    summary += f"- Median: {df[col].median():.2f}\n"
                    summary += f"- Min: {df[col].min():.2f}\n"
                    summary += f"- Max: {df[col].max():.2f}\n"
                    summary += f"- Standard Deviation: {df[col].std():.2f}\n\n"

                for col in categorical_columns:
                    summary += f"### {col}\n"
                    summary += f"- Unique values: {df[col].nunique()}\n"
                    summary += f"- Top value: {df[col].value_counts().index[0]}\n\n"

            elif analysis_type == "correlation" and len(numeric_columns) > 1:
                # Correlation analysis
                corr = df[numeric_columns].corr()

                # Create correlation heatmap
                plt.figure(figsize=(10, 8))
                plt.matshow(corr, fignum=1)
                plt.title("Correlation Matrix")
                plt.colorbar()

                # Add correlation values
                for i in range(len(corr.columns)):
                    for j in range(len(corr.columns)):
                        plt.text(
                            i, j, f"{corr.iloc[i, j]:.2f}", va="center", ha="center"
                        )

                # Save visualization
                viz_path = os.path.join(viz_dir, "correlation_matrix.png")
                plt.savefig(viz_path)
                plt.close()

                # Add correlation summary to results
                summary += "## Correlation Analysis\n\n"
                summary += "The correlation matrix between numeric variables has been saved as an image.\n\n"

                # Find strongest correlations
                corr_values = corr.unstack().sort_values(ascending=False)
                # Remove self-correlations (which are always 1.0)
                corr_values = corr_values[corr_values < 0.999]

                summary += "### Strongest correlations:\n"
                for i, (idx, val) in enumerate(corr_values.items()):
                    if i >= 5:  # Top 5 correlations
                        break
                    summary += f"- {idx[0]} vs {idx[1]}: {val:.2f}\n"

                return {"result": summary, "visualization_path": viz_path}

            elif analysis_type == "visualization":
                # Create multiple visualizations for numeric columns
                viz_paths = []
                viz_summary = ""

                # Create a histogram for each numeric column
                for col in numeric_columns[:3]:  # Limit to first 3 columns
                    plt.figure(figsize=(8, 6))
                    plt.hist(df[col].dropna(), bins=20, alpha=0.7)
                    plt.title(f"Histogram of {col}")
                    plt.xlabel(col)
                    plt.ylabel("Frequency")
                    viz_path = os.path.join(
                        viz_dir, f"histogram_{col}.png".replace("/", "_")
                    )
                    plt.savefig(viz_path)
                    plt.close()
                    viz_paths.append(viz_path)
                    viz_summary += f"- Histogram of {col}\n"

                # Create a pie chart for a categorical column if available
                if categorical_columns:
                    col = categorical_columns[0]
                    plt.figure(figsize=(8, 8))
                    value_counts = df[col].value_counts()
                    # Limit to top 5 categories for readability
                    if len(value_counts) > 5:
                        other_count = value_counts[5:].sum()
                        value_counts = value_counts[:5]
                        value_counts["Other"] = other_count
                    plt.pie(value_counts, labels=value_counts.index, autopct="%1.1f%%")
                    plt.title(f"Distribution of {col}")
                    viz_path = os.path.join(
                        viz_dir, f"pie_chart_{col}.png".replace("/", "_")
                    )
                    plt.savefig(viz_path)
                    plt.close()
                    viz_paths.append(viz_path)
                    viz_summary += f"- Pie chart of {col} distribution\n"

                summary += "## Visualizations Created\n\n"
                summary += viz_summary
                summary += f"\nVisualizations saved to {viz_dir}\n"

                return {"result": summary, "visualization_path": ",".join(viz_paths)}

            # Default return for summary
            return {"result": summary, "visualization_path": ""}

        except Exception as e:
            error_msg = f"Error analyzing data: {str(e)}"
            logger.error(error_msg)
            return {
                "result": f"Error analyzing data: {str(e)}",
                "visualization_path": "",
            }

    # Create the tools for the agents
    markdown_agent_tools = PromptTools(registry, hub)
    markdown_format_tool = markdown_agent_tools.create_tool_from_function(
        func=format_markdown,
        name="markdown_format",
        description="Format content as markdown using document transformers and structured text splitting",
        args_schema=MarkdownFormatInput,
        category="formatting",
    )

    data_analysis_agent_tools = PromptTools(registry, hub)
    data_analysis_tool = data_analysis_agent_tools.create_tool_from_function(
        func=analyze_data,
        name="analyze_data",
        description="Analyze data and generate visualizations",
        args_schema=DataAnalysisInput,
        category="data_analysis",
    )

    # Create the markdown agent with custom tools
    markdown_agent = AIAgent(
        agent_id="markdown_agent",
        name="Markdown Formatting Agent",
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=markdown_identity,
        capabilities=markdown_capabilities,
        personality="I am a markdown formatting specialist who excels at transforming unstructured or semi-structured content into well-formatted markdown. I apply consistent styling and organization to optimize content for readability.",
        custom_tools=[markdown_format_tool],
    )

    # Create the data analysis agent with custom tools
    data_analysis_agent = AIAgent(
        agent_id="data_analysis_agent",
        name="Data Analysis Agent",
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=data_analysis_identity,
        capabilities=data_analysis_capabilities,
        personality="I am a data analysis specialist who excels at analyzing data, generating insights, and creating visualizations. I can process CSV and JSON data to discover patterns and present results in a clear, understandable format.",
        custom_tools=[data_analysis_tool],
    )

    # Register all agents with the hub
    try:
        await hub.register_agent(telegram_agent)
        await hub.register_agent(research_agent)
        await hub.register_agent(markdown_agent)
        await hub.register_agent(data_analysis_agent)
    except Exception as e:
        logger.error(f"Error registering agents: {e}")
        raise RuntimeError(f"Failed to register agents: {e}")

    # Start the agent processing loops
    agent_tasks = []
    try:
        agent_tasks.append(asyncio.create_task(telegram_agent.run()))
        agent_tasks.append(asyncio.create_task(research_agent.run()))
        agent_tasks.append(asyncio.create_task(markdown_agent.run()))
        agent_tasks.append(asyncio.create_task(data_analysis_agent.run()))
    except Exception as e:
        logger.error(f"Error starting agent tasks: {e}")
        # Cancel any tasks that were started
        for task in agent_tasks:
            task.cancel()
        raise RuntimeError(f"Failed to start agent tasks: {e}")

    return {
        "registry": registry,
        "hub": hub,
        "telegram_agent": telegram_agent,
        "research_agent": research_agent,
        "markdown_agent": markdown_agent,
        "data_analysis_agent": data_analysis_agent,
        "agent_tasks": agent_tasks,  # Return tasks for proper cleanup
    }


async def run_telegram_assistant(enable_logging: bool = False) -> None:
    """
    Run the Telegram assistant with multiple specialized agents.

    Args:
        enable_logging (bool): Enable detailed logging for debugging. Defaults to False.
    """
    load_dotenv()

    # Configure logging
    if enable_logging:
        setup_logging(
            level=LogLevel.WARNING,
            module_levels={
                "AgentRegistry": LogLevel.WARNING,
                "CommunicationHub": LogLevel.DEBUG,
                "agentconnect.agents.ai_agent": LogLevel.INFO,
                "agentconnect.agents.telegram.telegram_agent": LogLevel.DEBUG,
                "agentconnect.core.agent": LogLevel.INFO,
                "agentconnect.prompts.tools": LogLevel.INFO,
            },
        )
    else:
        # Set up basic logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    logger.info("=== Advanced Telegram Bot with Multi-Agent Capabilities ===")
    logger.info(
        "This demo showcases a sophisticated Telegram bot using AgentConnect with specialized agents."
    )
    logger.info("Available specialized agents:")
    logger.info("1. Telegram Agent - Handles Telegram user interactions")
    logger.info(
        "2. Research Agent - Performs web searches and creates research reports"
    )
    logger.info(
        "3. Markdown Formatting Agent - Transforms content into well-formatted text"
    )
    logger.info("4. Data Analysis Agent - Analyzes data and creates visualizations")
    logger.info("\nSetting up agents...")

    agents = None

    try:
        # Set up agents
        agents = await setup_agents()

        logger.info("Agents are ready! Telegram bot is now running.")
        logger.info("Open your Telegram app and start chatting with your bot.")
        logger.info(
            "The bot will use specialized agents for research, formatting, and data analysis."
        )
        logger.info("Press Ctrl+C to stop the bot.")

        # Keep the main task running until interrupted
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("\nOperation interrupted by user")
    except RuntimeError as e:
        logger.error(f"\nCritical error: {e}")
    except Exception as e:
        logger.error(f"\nUnexpected error: {e}")
        if enable_logging:
            import traceback

            traceback.print_exc()
    finally:
        # Clean up
        if agents:
            logger.info("\nCleaning up resources...")

            # Stop all agent tasks
            if "agent_tasks" in agents:
                for task in agents["agent_tasks"]:
                    task.cancel()
                    try:
                        # Wait for task to properly cancel
                        await asyncio.wait_for(task, timeout=2.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        pass

            # Unregister agents
            for agent_id in [
                "telegram_agent",
                "research_agent",
                "markdown_agent",
                "data_analysis_agent",
            ]:
                if agent_id in agents:
                    try:
                        await agents["hub"].unregister_agent(agents[agent_id].agent_id)
                        logger.info(f"Unregistered {agent_id}")
                    except Exception as e:
                        logger.error(f"Error unregistering {agent_id}: {e}")

        logger.info("Telegram bot stopped successfully!")


if __name__ == "__main__":
    try:
        # Add --logging flag for detailed logging
        if "--logging" in sys.argv:
            asyncio.run(run_telegram_assistant(enable_logging=True))
        else:
            asyncio.run(run_telegram_assistant())
    except KeyboardInterrupt:
        logger.info("\nTelegram bot terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
