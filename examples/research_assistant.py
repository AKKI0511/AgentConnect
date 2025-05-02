#!/usr/bin/env python
"""
Advanced Multi-Agent Research Assistant Example

This example demonstrates a sophisticated multi-agent system using AgentConnect:
1. Core Interaction Agent: Primary interface between user and specialized agents
2. Research Agent: Performs web searches and creates comprehensive research reports
3. Markdown Formatting Agent: Transforms HTML content into clean markdown

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
from agentconnect.agents import (
    AIAgent,
    HumanAgent,
)
from agentconnect.communication import CommunicationHub
from agentconnect.core.types import (
    AgentIdentity,
    Capability,
    ModelName,
    ModelProvider,
)
from agentconnect.core.registry import AgentRegistry
from agentconnect.utils.callbacks import ToolTracerCallbackHandler
from agentconnect.utils.logging_config import (
    setup_logging,
    LogLevel,
    disable_all_logging,
)
from agentconnect.prompts.tools import PromptTools

# Add imports for real-world tools
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain.schema import Document
from langchain_community.document_transformers.markdownify import MarkdownifyTransformer
from langchain_community.tools.requests.tool import RequestsGetTool
from langchain_community.utilities import TextRequestsWrapper
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
    """Input schema for HTML to markdown conversion tool."""

    html_content: str = Field(description="The HTML content to convert to markdown.")


class MarkdownFormatOutput(BaseModel):
    """Output schema for HTML to markdown conversion tool."""

    markdown_content: str = Field(description="The HTML content converted to markdown.")


async def setup_agents() -> Dict[str, Any]:
    """
    Set up the registry, hub, and agents.
    
    Args:
        enable_logging (bool): Whether to enable detailed message flow logging
    
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
    model_name = ModelName.GEMINI2_5_FLASH_PREVIEW

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
    
    # Register message logger
    # hub.add_global_handler(demo_message_logger)
    # print_colored("Registered message flow logger to visualize agent collaboration", "INFO")

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
        external_callbacks=[ToolTracerCallbackHandler("core_agent")],
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
    requests_wrapper = TextRequestsWrapper()
    custom_tools.append(RequestsGetTool(requests_wrapper=requests_wrapper, allow_dangerous_requests=True))

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
            name="html_to_markdown_conversion",
            description="Converts HTML content to clean markdown format",
            input_schema={"html_content": "string"},
            output_schema={"markdown_content": "string"},
        ),
        Capability(
            name="content_organization",
            description="Organizes content with consistent styling and structure",
            input_schema={"content": "string"},
            output_schema={"organized_content": "string"},
        ),
    ]

    # Create HTML to Markdown conversion function
    def convert_html_to_markdown(html_content: str) -> Dict[str, str]:
        """
        Convert HTML content to clean markdown format using LangChain's MarkdownifyTransformer.

        Args:
            html_content (str): The HTML content to convert

        Returns:
            Dict[str, str]: Contains the converted markdown content
        """
        print_colored("Converting HTML content to markdown format", "MARKDOWN")

        try:
            # Initialize the transformer with appropriate options
            markdown_transformer = MarkdownifyTransformer(
                strip=["script", "style"],  # Remove unwanted elements
                heading_style="ATX",  # Use # style headings
                bullets="-",  # Use - for bullet points
            )
            
            # Create a document from the HTML content
            docs = [Document(page_content=html_content)]
            
            # Convert HTML to markdown
            converted_docs = markdown_transformer.transform_documents(docs)
            
            # Ensure the response is a single string, not a list of fragments
            markdown_content = converted_docs[0].page_content
            
            # Additional processing to ensure it's a single coherent document
            if isinstance(markdown_content, list):
                markdown_content = "\n\n".join(markdown_content)
            
            # Return the consolidated markdown content
            return {
                "markdown_content": markdown_content,
            }
        except Exception as e:
            print_colored(f"Error in HTML to markdown conversion: {e}", "ERROR")
            # Provide a basic fallback
            return {
                "markdown_content": f"Error converting HTML to markdown: {str(e)}\n\nOriginal content:\n{html_content}",
            }

    # Create the markdown agent with custom tools
    markdown_agent_tools = PromptTools(registry, hub)
    html_to_markdown_tool = markdown_agent_tools.create_tool_from_function(
        func=convert_html_to_markdown,
        name="convert_html_to_markdown",
        description="Convert HTML content to clean markdown format using LangChain's document transformers",
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
        personality="I am a markdown formatting specialist who excels at transforming unstructured or semi-structured content into well-formatted markdown.",
        custom_tools=[html_to_markdown_tool],
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
            level=LogLevel.INFO,
            module_levels={
                "AgentRegistry": LogLevel.WARNING,
                "CommunicationHub": LogLevel.WARNING,
                "agentconnect.agents.ai_agent": LogLevel.WARNING,
                "agentconnect.agents.human_agent": LogLevel.WARNING,
                "agentconnect.core.agent": LogLevel.WARNING,
                "agentconnect.prompts.tools": LogLevel.WARNING,
                "CapabilityDiscovery": LogLevel.WARNING,
                "agentconnect.prompts.custom_tools.collaboration_tools": LogLevel.WARNING,
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
        "3. Markdown Formatting Agent - Converts HTML content to clean markdown",
        "MARKDOWN",
    )
    print_colored("\nSetting up agents...", "SYSTEM")

    agents = None
    # message_logger_registered = enable_logging

    try:
        # Set up agents with logging flag
        agents = await setup_agents()

        print_colored("Agents are ready! Starting interaction...\n", "SYSTEM")
        print_colored(
            "You can ask the core agent to research any topic or convert HTML to markdown.",
            "SYSTEM",
        )
        print_colored(
            "Example: 'Research the latest developments in LangChain and LangGraph and convert the results to markdown.'",
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

            # Remove message logger if it was registered
            # if message_logger_registered and "hub" in agents:
            #     try:
            #         # agents["hub"].remove_global_handler(demo_message_logger)
            #         print_colored("Removed message flow logger", "INFO")
            #     except Exception as e:
            #         print_colored(f"Error removing message logger: {e}", "ERROR")

            # Stop all agents
            for agent_id in ["core_agent", "research_agent", "markdown_agent"]:
                if agent_id in agents:
                    try:
                        # Use the new stop method for proper cleanup
                        await agents[agent_id].stop()
                        await agents["hub"].unregister_agent(agents[agent_id].agent_id)
                        print_colored(f"Stopped and unregistered {agent_id}", "SYSTEM")
                    except Exception as e:
                        print_colored(f"Error stopping/unregistering {agent_id}: {e}", "ERROR")

            # Cancel any remaining tasks
            if "agent_tasks" in agents:
                for task in agents["agent_tasks"]:
                    if not task.done():
                        task.cancel()
                        try:
                            # Wait for task to properly cancel
                            await asyncio.wait_for(task, timeout=2.0)
                        except (asyncio.TimeoutError, asyncio.CancelledError):
                            pass

        print_colored("Demo completed successfully!", "SYSTEM")


# Define the global message logger function
# async def demo_message_logger(message: Message) -> None:
#     """
#     Global message handler for logging agent collaboration flow.
    
#     This handler inspects messages routed through the hub and logs specific events
#     in the research assistant demo to visualize agent collaboration.
    
#     Args:
#         message (Message): The message being routed through the hub
#     """
#     if message.receiver_id == "human_user" or message.sender_id == "human_user":
#         return
#     color_type = "SYSTEM"
#     if message.sender_id == "core_agent":
#         color_type = "CORE"
#     elif message.sender_id == "research_agent":
#         color_type = "RESEARCH"
#     elif message.sender_id == "markdown_agent":
#         color_type = "MARKDOWN"

#     print_colored(f"{message.sender_id} -> {message.receiver_id}: {message.content[:50]}...", color_type)
        

if __name__ == "__main__":
    try:
        asyncio.run(run_research_assistant_demo())
    except KeyboardInterrupt:
        print_colored("\nResearch session terminated by user", "SYSTEM")
    except Exception as e:
        print_colored(f"Fatal error: {e}", "ERROR")
        sys.exit(1)
