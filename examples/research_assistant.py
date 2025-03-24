#!/usr/bin/env python
"""
Advanced Multi-Agent Research Assistant Example

This example demonstrates a sophisticated multi-agent system using AgentConnect:
1. Core Interaction Agent: Primary interface between user and specialized agents
2. Research Agent: Performs web searches and creates comprehensive research reports
3. Markdown Formatting Agent: Transforms content into well-formatted markdown

This showcases:
- Multi-agent collaboration
- Memory persistence
- Task delegation and specialized agent capabilities
- Human-in-the-loop interaction
- Capability-based agent discovery

Required Environment Variables:
- GOOGLE_API_KEY or another LLM provider API key
- TAVILY_API_KEY: API key for Tavily Search (get one at https://tavily.com)
"""

import asyncio
import os
import sys
from typing import Dict, List, Any
from colorama import init, Fore, Style
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Import directly from the agentconnect package (using the public API)
from agentconnect import (
    CommunicationHub,
    AIAgent,
    HumanAgent,
)
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
    disable_all_logging,
)
from agentconnect.prompts.tools import PromptTools

# Add imports for real-world tools
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_community.document_loaders.tomarkdown import ToMarkdownLoader
from langchain.text_splitter import HTMLHeaderTextSplitter
from langchain.schema import Document
from langchain_community.document_transformers.markdownify import MarkdownifyTransformer

# Initialize colorama for cross-platform colored output
init()

# Define colors for different message types
COLORS = {
    "SYSTEM": Fore.YELLOW,
    "USER": Fore.GREEN,
    "AI": Fore.CYAN,
    "ERROR": Fore.RED,
    "INFO": Fore.MAGENTA,
    "RESEARCH": Fore.BLUE,
    "MARKDOWN": Fore.WHITE,
}


def print_colored(message: str, color_type: str = "SYSTEM") -> None:
    """
    Print a message with specified color.

    Args:
        message (str): The message to print
        color_type (str): The type of color to use (SYSTEM, USER, AI, etc.)
    """
    color = COLORS.get(color_type, Fore.WHITE)
    print(f"{color}{message}{Style.RESET_ALL}")


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
    tavily_api_key = os.getenv("TAVILY_API_KEY")

    # Fall back to other API keys if Google's isn't available
    provider_type = ModelProvider.GOOGLE
    model_name = ModelName.GEMINI2_FLASH

    if not api_key:
        print_colored("GOOGLE_API_KEY not found. Checking for alternatives...", "INFO")

        if os.getenv("OPENAI_API_KEY"):
            api_key = os.getenv("OPENAI_API_KEY")
            provider_type = ModelProvider.OPENAI
            model_name = ModelName.GPT4O
            print_colored("Using OpenAI's GPT-4 model instead", "INFO")

        elif os.getenv("ANTHROPIC_API_KEY"):
            api_key = os.getenv("ANTHROPIC_API_KEY")
            provider_type = ModelProvider.ANTHROPIC
            model_name = ModelName.CLAUDE_3_OPUS
            print_colored("Using Anthropic's Claude model instead", "INFO")

        elif os.getenv("GROQ_API_KEY"):
            api_key = os.getenv("GROQ_API_KEY")
            provider_type = ModelProvider.GROQ
            model_name = ModelName.LLAMA3_70B
            print_colored("Using Groq's LLaMA 3 model instead", "INFO")

        else:
            raise RuntimeError(
                "No LLM API key found. Please set GOOGLE_API_KEY, OPENAI_API_KEY, "
                "ANTHROPIC_API_KEY, or GROQ_API_KEY in your environment or .env file."
            )

    if not tavily_api_key:
        print_colored(
            "Warning: TAVILY_API_KEY not found. Research capabilities will be limited.\n"
            "Get a free API key at https://tavily.com",
            "ERROR",
        )

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
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=core_identity,
        capabilities=core_capabilities,
        personality="I am the primary interface between you and specialized agents. I understand your requests, delegate tasks to specialized agents, and present their findings in a coherent manner. I maintain conversation context and ensure a smooth experience.",
    )

    # Create research agent
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
            print_colored(f"Error initializing Tavily search: {e}", "ERROR")

    research_agent = AIAgent(
        agent_id="research_agent",
        name="Research Agent",
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=research_identity,
        capabilities=research_capabilities,
        personality="I am a research specialist who excels at finding information on various topics. I generate effective search queries, retrieve information from the web, and synthesize findings into comprehensive research reports with proper citations.",
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
        print_colored(f"Formatting content as {format_type} markdown", "MARKDOWN")

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
            print_colored(f"Error in markdown formatting: {e}", "ERROR")
            # Provide a basic fallback format
            return {
                "formatted_content": f"# {format_type.title()}\n\n{content}",
                "format_applied": "basic",
            }

    # Create the markdown agent with custom tools
    markdown_agent_tools = PromptTools(registry, hub)
    markdown_format_tool = markdown_agent_tools.create_tool_from_function(
        func=format_markdown,
        name="markdown_format",
        description="Format content as markdown using LangChain's document transformers and structured text splitting",
        args_schema=MarkdownFormatInput,
        category="formatting",
    )

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

    # Register all agents with the hub
    try:
        await hub.register_agent(human_agent)
        await hub.register_agent(core_agent)
        await hub.register_agent(research_agent)
        await hub.register_agent(markdown_agent)
    except Exception as e:
        print_colored(f"Error registering agents: {e}", "ERROR")
        raise RuntimeError(f"Failed to register agents: {e}")

    # Start the agent processing loops
    agent_tasks = []
    try:
        agent_tasks.append(asyncio.create_task(core_agent.run()))
        agent_tasks.append(asyncio.create_task(research_agent.run()))
        agent_tasks.append(asyncio.create_task(markdown_agent.run()))
    except Exception as e:
        print_colored(f"Error starting agent tasks: {e}", "ERROR")
        # Cancel any tasks that were started
        for task in agent_tasks:
            task.cancel()
        raise RuntimeError(f"Failed to start agent tasks: {e}")

    return {
        "registry": registry,
        "hub": hub,
        "human_agent": human_agent,
        "core_agent": core_agent,
        "research_agent": research_agent,
        "markdown_agent": markdown_agent,
        "agent_tasks": agent_tasks,  # Return tasks for proper cleanup
    }


async def run_research_assistant_demo(enable_logging: bool = False) -> None:
    """
    Run the research assistant demo with multiple specialized agents.

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
                "agentconnect.agents.human_agent": LogLevel.WARNING,
                "agentconnect.core.agent": LogLevel.INFO,
                "agentconnect.prompts.tools": LogLevel.INFO,
            },
        )
    else:
        # Disable all logging when not in debug mode
        disable_all_logging()

    print_colored("=== Advanced Multi-Agent System Demo ===", "SYSTEM")
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
        "2. Research Agent - Performs web searches and creates research reports",
        "RESEARCH",
    )
    print_colored(
        "3. Markdown Formatting Agent - Transforms content into well-formatted markdown",
        "MARKDOWN",
    )
    print_colored("\nSetting up agents...", "SYSTEM")

    agents = None

    try:
        # Set up agents
        agents = await setup_agents()

        print_colored("Agents are ready! Starting interaction...\n", "SYSTEM")
        print_colored(
            "You can ask the core agent to research any topic or format content as markdown.",
            "SYSTEM",
        )
        print_colored(
            "Example: 'Research the latest developments in LangChain and LangGraph and format the results as a markdown report.'",
            "SYSTEM",
        )
        print_colored("Type 'exit' to end the conversation.\n", "SYSTEM")

        # Start interaction with the core agent
        await agents["human_agent"].start_interaction(agents["core_agent"])

    except KeyboardInterrupt:
        print_colored("\nOperation interrupted by user", "SYSTEM")
    except RuntimeError as e:
        print_colored(f"\nCritical error: {e}", "ERROR")
    except Exception as e:
        print_colored(f"\nUnexpected error: {e}", "ERROR")
        if enable_logging:
            import traceback

            traceback.print_exc()
    finally:
        # Clean up
        if agents:
            print_colored("\nCleaning up resources...", "SYSTEM")

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
            for agent_id in ["core_agent", "research_agent", "markdown_agent"]:
                if agent_id in agents:
                    try:
                        await agents["hub"].unregister_agent(agents[agent_id].agent_id)
                        print_colored(f"Unregistered {agent_id}", "SYSTEM")
                    except Exception as e:
                        print_colored(f"Error unregistering {agent_id}: {e}", "ERROR")

        print_colored("Demo completed successfully!", "SYSTEM")


if __name__ == "__main__":
    try:
        asyncio.run(run_research_assistant_demo())
    except KeyboardInterrupt:
        print_colored("\nResearch session terminated by user", "SYSTEM")
    except Exception as e:
        print_colored(f"Fatal error: {e}", "ERROR")
        sys.exit(1)
