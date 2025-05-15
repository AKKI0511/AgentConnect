#!/usr/bin/env python
"""
Autonomous Workflow Demo for AgentConnect

This script demonstrates a multi-agent workflow using the AgentConnect framework.
It features three agents:
1. User Proxy Agent - Orchestrates the workflow based on user requests
2. Research Agent - Performs company research using web search tools
3. Telegram Broadcast Agent - Broadcasts messages to a Telegram group

The demo showcases autonomous service discovery, execution, and payment between agents
using AgentKit/CDP SDK integration within the AgentConnect framework.
"""

import asyncio
import os
from typing import List, Tuple

from dotenv import load_dotenv
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.tools.requests.tool import RequestsGetTool
from langchain_community.utilities import TextRequestsWrapper
from colorama import init, Fore, Style

from agentconnect.agents.ai_agent import AIAgent
from agentconnect.agents.human_agent import HumanAgent
from agentconnect.agents.telegram.telegram_agent import TelegramAIAgent
from agentconnect.communication.hub import CommunicationHub
from agentconnect.core.agent import BaseAgent
from agentconnect.core.types import (
    AgentIdentity,
    Capability,
    ModelProvider,
    ModelName,
    AgentProfile,
    AgentType,
    Skill,
)
from agentconnect.core.registry import AgentRegistry
from agentconnect.utils.logging_config import (
    setup_logging,
    LogLevel,
    disable_all_logging,
)
from agentconnect.utils.callbacks import ToolTracerCallbackHandler

# Initialize colorama for cross-platform colored output
init()

# Define colors for different message types
COLORS = {
    "SYSTEM": Fore.YELLOW,
    "USER_PROXY": Fore.CYAN,
    "RESEARCH": Fore.BLUE,
    "TELEGRAM": Fore.MAGENTA,
    "HUMAN": Fore.GREEN,
    "ERROR": Fore.RED,
    "INFO": Fore.WHITE,
}

def print_colored(message: str, color_type: str = "SYSTEM") -> None:
    """Print a message with specified color"""
    color = COLORS.get(color_type.upper(), Fore.WHITE)
    print(f"{color}{message}{Style.RESET_ALL}")

# Define Base Sepolia USDC Contract Address
BASE_SEPOLIA_USDC_ADDRESS = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"

# Define Capabilities
GENERAL_RESEARCH = Capability(
    name="general_research",
    description="Performs detailed research on a given topic, project, or URL, providing a structured report.",
)

TELEGRAM_BROADCAST = Capability(
    name="telegram_broadcast",
    description="Broadcasts a given message summary to pre-configured Telegram groups.",
)


async def setup_agents() -> Tuple[AIAgent, AIAgent, TelegramAIAgent, HumanAgent]:
    """
    Set up and configure all agents needed for the workflow.

    Returns:
        Tuple containing (user_proxy_agent, research_agent, telegram_broadcaster, human_agent)
    """
    # Load environment variables
    load_dotenv()

    # Retrieve API keys from environment
    google_api_key = os.getenv("GOOGLE_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")

    # Check for required environment variables
    missing_vars = []
    if not google_api_key and not openai_api_key:
        missing_vars.append("GOOGLE_API_KEY or OPENAI_API_KEY")
    if not os.getenv("CDP_API_KEY_NAME"):
        missing_vars.append("CDP_API_KEY_NAME")
    if not os.getenv("CDP_API_KEY_PRIVATE_KEY"):
        missing_vars.append("CDP_API_KEY_PRIVATE_KEY")
    if not telegram_token:
        missing_vars.append("TELEGRAM_BOT_TOKEN")
    if not tavily_api_key:
        missing_vars.append("TAVILY_API_KEY")

    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    # Determine which LLM to use based on available API keys
    if google_api_key:
        provider_type = ModelProvider.GOOGLE
        model_name = ModelName.GEMINI2_5_FLASH_PREVIEW
        api_key = google_api_key
    else:
        provider_type = ModelProvider.OPENAI
        model_name = ModelName.GPT4O
        api_key = openai_api_key

    print_colored(f"Using {provider_type.value}: {model_name.value}", "INFO")

    # Configure Callback Handler
    monitor_callback = ToolTracerCallbackHandler(agent_id="user_proxy_agent")

    # Define Agent IDs
    USER_PROXY_AGENT_ID = "user_proxy_agent"
    RESEARCH_AGENT_ID = "research_agent"
    TELEGRAM_AGENT_ID = "telegram_broadcaster_agent"

    # Create User Proxy Agent (Workflow Orchestrator)
    user_proxy_skills = [
        Skill(name="workflow_orchestration", description="Coordinates tasks across multiple agents."),
        Skill(name="service_discovery", description="Finds and utilizes other agents' capabilities."),
        Skill(name="payment_management", description="Handles payments for agent services."),
    ]
    user_proxy_profile = AgentProfile(
        agent_id=USER_PROXY_AGENT_ID,
        agent_type=AgentType.AI,
        name="Workflow Orchestrator",
        summary="Manages and orchestrates multi-agent workflows, including service discovery and payments.",
        description="An AI agent responsible for understanding user requests, breaking them down into tasks, finding suitable agents for those tasks, coordinating their execution, and managing payments.",
        version="1.0.0",
        capabilities=[],  # Orchestrator itself doesn't offer direct capabilities but uses others
        skills=user_proxy_skills,
        tags=["orchestration", "workflow", "multi-agent", "payments", "coordination"],
    )
    user_proxy_agent = AIAgent(
        agent_id=USER_PROXY_AGENT_ID,
        profile=user_proxy_profile,
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=AgentIdentity.create_key_based(),
        enable_payments=True,
        external_callbacks=[monitor_callback],
        personality=f"""You are a workflow orchestrator. You interact with other agents to complete tasks. You are responsible for managing payments and returning results.
        If a payment is made, provide the amount and the transaction hash in your response.

        **Payment Details (USDC on Base Sepolia):**
        - Contract: {BASE_SEPOLIA_USDC_ADDRESS}
        - Amount: 6 decimals. 1 USDC = '1000000'.
        """
    )

    # Create Research Agent
    research_agent_skills = [
        Skill(name="web_search", description="Performs targeted web searches using tools like Tavily."),
        Skill(name="information_extraction", description="Extracts relevant information from web pages and documents."),
        Skill(name="report_generation", description="Compiles research findings into structured reports."),
        Skill(name="source_evaluation", description="Assesses the reliability of information sources."),
    ]
    research_agent_profile = AgentProfile(
        agent_id=RESEARCH_AGENT_ID,
        agent_type=AgentType.AI,
        name="Research Specialist",
        summary="Provides detailed research reports on various topics using web search tools.",
        description="An AI agent specialized in conducting in-depth research on companies, projects, topics, or URLs. It uses web search tools to gather information and presents it in a well-structured report, including sources.",
        version="1.0.0",
        capabilities=[GENERAL_RESEARCH],
        skills=research_agent_skills,
        tags=["research", "web_search", "analysis", "reporting", "information_retrieval"],
        examples=[
            "Research the company 'OpenAI'.",
            "What are the latest advancements in quantum computing?",
            "Provide a report on the Uniswap protocol."
        ]
    )
    research_agent = AIAgent(
        agent_id=RESEARCH_AGENT_ID,
        profile=research_agent_profile,
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=AgentIdentity.create_key_based(),
        enable_payments=True,
        personality="""You are a Research Specialist. You provide detailed, well-structured reports on any given topic, project, or URL using web search tools.

**Report Structure:**
- **For companies/projects/organizations:** Aim to structure your report using these sections when applicable: Topic/Project Name, Executive Summary, Key Personnel/Founders, Offerings/Products, Ecosystem/Partners, Asset/Token Details, Community Sentiment, Sources Consulted, Closing Summary.
- **For conceptual topics or general questions:** Adapt the structure logically. Focus on defining the concept, explaining key aspects, providing examples, discussing benefits/drawbacks, listing sources, and offering a concluding summary.
- **Always include Sources Consulted.**

Your fee is 2 USDC (Base Sepolia). When responding, state your fee.""",
        custom_tools=[
            TavilySearchResults(api_key=tavily_api_key, max_results=5),
            RequestsGetTool(
                requests_wrapper=TextRequestsWrapper(), allow_dangerous_requests=True
            ),
        ],
    )

    # Create Telegram Broadcast Agent
    telegram_broadcaster_skills = [
        Skill(name="message_formatting", description="Formats messages appropriately for Telegram."),
        Skill(name="telegram_api_interaction", description="Uses Telegram Bot API to send messages."),
        Skill(name="group_broadcasting", description="Sends messages to multiple pre-configured Telegram groups."),
    ]
    telegram_broadcaster_profile = AgentProfile(
        agent_id=TELEGRAM_AGENT_ID,
        agent_type=AgentType.AI,
        name="Telegram Broadcaster",
        summary="Broadcasts messages to configured Telegram groups.",
        description="An AI agent that specializes in broadcasting messages to one or more Telegram groups. It takes a message summary and ensures its delivery.",
        version="1.0.0",
        capabilities=[TELEGRAM_BROADCAST],
        skills=telegram_broadcaster_skills,
        tags=["telegram", "broadcast", "messaging", "notifications"],
        examples=["Broadcast: 'Project Alpha update now available.'"]
    )
    telegram_broadcaster = TelegramAIAgent(
        agent_id=TELEGRAM_AGENT_ID,
        profile=telegram_broadcaster_profile,
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=AgentIdentity.create_key_based(),
        enable_payments=True,
        personality="""You are a Telegram Broadcast Specialist. You broadcast messages to all regestered Telegram groups. \
            Your fee is 1 USDC (Base Sepolia). After broadcasting, state your fee in your response.""",
        telegram_token=telegram_token,
    )

    # Create Human Agent
    human_agent = HumanAgent(
        agent_id="human_user",
        name="Human User",
        identity=AgentIdentity.create_key_based(),
        organization="demo_org",
    )

    return user_proxy_agent, research_agent, telegram_broadcaster, human_agent


async def main(enable_logging: bool = False):
    """
    Main execution flow for the autonomous workflow demo.

    Sets up the agents, registers them with the communication hub,
    and handles user input for research and broadcast requests.

    Args:
        enable_logging: Whether to enable verbose logging
    """

    if not enable_logging:
        disable_all_logging()
    else:
        # Keep logging setup simple if enabled, main feedback via print_colored
        setup_logging(level=LogLevel.WARNING)

    try:
        print_colored("\nSetting up agents...", "SYSTEM")
        # Set up agents
        user_proxy_agent, research_agent, telegram_broadcaster, human_agent = (
            await setup_agents()
        )
        agents: List[BaseAgent] = [
            user_proxy_agent,
            research_agent,
            telegram_broadcaster,
            human_agent,
        ]

        # Create registry and communication hub
        registry = AgentRegistry()
        hub = CommunicationHub(registry)

        print_colored("Registering agents with Communication Hub...", "SYSTEM")
        # Register all agents
        for agent in agents:
            if not await hub.register_agent(agent):
                print_colored(f"Failed to register {agent.agent_id}", "ERROR")
                return
            print_colored(f"  ✓ Registered: {agent.name} ({agent.agent_id})", "INFO")

            # Display payment address if available
            if hasattr(agent, "metadata") and hasattr(
                agent.metadata, "payment_address"
            ):
                if agent.metadata.payment_address: # Check if address is not None or empty
                    print_colored(
                        f"    Payment Address ({agent.name}): {agent.metadata.payment_address}", "INFO"
                    )
                else:
                     print_colored(f"    Payment address pending initialization for {agent.name}...", "INFO")

        print_colored("All agents registered. Waiting for initialization...", "SYSTEM")

        # Start agent processing loops
        tasks = []
        try:
            print_colored("Starting agent processing loops...", "SYSTEM")
            # Start the AI agents
            telegram_task = asyncio.create_task(telegram_broadcaster.run())
            tasks.append(telegram_task)

            research_task = asyncio.create_task(research_agent.run())
            tasks.append(research_task)

            user_proxy_task = asyncio.create_task(user_proxy_agent.run())
            tasks.append(user_proxy_task)

            # Allow some time for agents to initialize
            await asyncio.sleep(3)

            # Print welcome message and instructions
            print_colored("\n=== AgentConnect Autonomous Workflow Demo ===", "SYSTEM")
            print_colored(
                "This demo showcases multi-agent workflows with service discovery and payments.",
                "SYSTEM",
            )
            print_colored("Available agents:", "INFO")
            print_colored("  - User Proxy (Orchestrator)", "USER_PROXY")
            print_colored("  - Research Agent (2 USDC per request)", "RESEARCH")
            print_colored("  - Telegram Broadcaster (1.0 USDC per broadcast)", "TELEGRAM")
            print_colored("\nExample commands:", "INFO")
            print_colored("  - Research X and broadcast the summary", "INFO")
            print_colored(
                "  - Find information about Y and share it on Telegram", "INFO"
            )
            print_colored("\nType 'exit' or 'quit' to end the demo", "INFO")

            # Start human interaction with the user proxy agent
            # HumanAgent will handle its own colored printing for the chat
            print_colored("\n▶️ Starting interactive session with Workflow Orchestrator...", "SYSTEM")
            await human_agent.start_interaction(user_proxy_agent)

        except asyncio.CancelledError:
            print_colored("Tasks cancelled", "SYSTEM")
        except Exception as e:
            print_colored(f"Error in main execution: {e}", "ERROR")
        finally:
            # Cleanup
            print_colored("\nCleaning up...", "SYSTEM")

            # Stop all agents
            for agent in agents:
                await agent.stop()
                print_colored(f"Stopped {agent.agent_id}", "SYSTEM")

            # Cancel all tasks
            for task in tasks:
                if not task.done():
                    task.cancel()

            # Wait for tasks to finish
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            # Stop the Telegram bot explicitly
            if telegram_broadcaster:
                print_colored("Stopping Telegram bot...", "SYSTEM")
                await telegram_broadcaster.stop_telegram_bot()

            # Unregister agents
            print_colored("Unregistering agents...", "SYSTEM")
            for agent in agents:
                # Skip human agent as it doesn't run a loop
                if agent.agent_id == "human_user":
                    continue
                try:
                    await hub.unregister_agent(agent.agent_id)
                    print_colored(f"  ✓ Unregistered {agent.agent_id}", "INFO")
                except Exception as e:
                    print_colored(f"  ✗ Error unregistering {agent.agent_id}: {e}", "ERROR")

    except ValueError as e:
        print_colored(f"Setup error: {e}", "ERROR")
    except Exception as e:
        print_colored(f"Unexpected error: {e}", "ERROR")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_colored("\nDemo interrupted by user. Shutting down...", "SYSTEM")
    except Exception as e:
        print_colored(f"Fatal error: {e}", "ERROR")
    finally:
        print_colored("\nDemo shutdown complete.", "SYSTEM")


# Research the Uniswap protocol (uniswap.org), summarize its core function and tokenomics, and broadcast the summary on telegram.