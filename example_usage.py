import asyncio
import logging
import os

from colorama import Fore, Style, init
from dotenv import load_dotenv

from src.agents.ai_agent import AIAgent
from src.agents.human_agent import HumanAgent
from src.communication.hub import CommunicationHub
from src.core.registry import AgentRegistry
from src.core.types import AgentIdentity, InteractionMode, ModelName, ModelProvider
from src.providers.provider_factory import ProviderFactory
from src.utils.logging_config import LogLevel, setup_logging

# Initialize colorama for cross-platform colored output
init()

# Define colors for different message types
COLORS = {
    "SYSTEM": Fore.YELLOW,
    "USER": Fore.GREEN,
    "AI": Fore.CYAN,
    "ERROR": Fore.RED,
    "INFO": Fore.MAGENTA,
}


def print_colored(message: str, color_type: str = "SYSTEM") -> None:
    """Print a message with specified color"""
    color = COLORS.get(color_type, Fore.WHITE)
    print(f"{color}{message}{Style.RESET_ALL}")


async def main(enable_logging: bool = False) -> None:
    """
    Run an interactive demo between a human user and an AI assistant.

    This demo showcases:
    1. Dynamic provider and model selection
    2. Secure agent registration and communication
    3. Real-time message exchange with proper error handling
    4. Graceful session management and cleanup

    Args:
        enable_logging (bool): Enable detailed logging for debugging. Defaults to False.
    """
    load_dotenv()

    if enable_logging:
        setup_logging(
            level=LogLevel.INFO,
            module_levels={
                "AgentRegistry": LogLevel.WARNING,
                "CommunicationHub": LogLevel.INFO,
                "SimpleAgentProtocol": LogLevel.DEBUG,
                "src.utils.interaction_control": LogLevel.INFO,
            },
        )
    else:
        logging.disable(logging.CRITICAL)

    # Initialize core components
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    # Create secure agent identities
    human_identity = AgentIdentity.create_key_based()
    ai_identity = AgentIdentity.create_key_based()

    # Provider selection
    print_colored("\n=== AI Provider Selection ===", "SYSTEM")
    print_colored("\nAvailable providers:", "INFO")
    for provider in ModelProvider:
        print_colored(f"  • {provider.value}", "INFO")

    provider_name = input(f"{COLORS['USER']}Select provider: {Style.RESET_ALL}").lower()
    provider_type = ModelProvider(provider_name)

    # Get API key
    api_key = os.getenv(f"{provider_name.upper()}_API_KEY")
    if not api_key:
        raise ValueError(f"Missing API key for {provider_name}")

    # Model selection
    provider = ProviderFactory.create_provider(provider_type, api_key)
    print_colored("\nAvailable models:", "INFO")
    available_models = provider.get_available_models()
    for model in available_models:
        print_colored(f"  • {model.value}", "INFO")

    model_name = ModelName(input(f"{COLORS['USER']}Select model: {Style.RESET_ALL}"))

    # Initialize agents
    human = HumanAgent(
        agent_id="human1", name="User", identity=human_identity, organization_id="org1"
    )

    ai_assistant = AIAgent(
        agent_id="ai1",
        name="Assistant",
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=ai_identity,
        capabilities=["conversation"],
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
        personality="helpful and professional",
        organization_id="org2",
    )

    agents = [human, ai_assistant]

    try:
        # Register agents
        for agent in agents:
            if not await hub.register_agent(agent):
                print_colored(f"Failed to register {agent.name}", "ERROR")
                return

        # Start AI processing
        ai_task = asyncio.create_task(ai_assistant.run())

        print_colored("\n=== Starting Interactive Session ===", "SYSTEM")
        print_colored("Type your messages and press Enter to send", "INFO")
        print_colored("Type 'exit' to end the session", "INFO")

        await human.start_interaction(ai_assistant)

    except Exception as e:
        print_colored(f"Error in interaction: {str(e)}", "ERROR")
    finally:
        print_colored("\nEnding session...", "SYSTEM")
        # Cleanup
        ai_assistant.is_running = False
        try:
            await asyncio.wait_for(ai_task, timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            ai_task.cancel()

        for agent in agents:
            await hub.unregister_agent(agent.agent_id)

        print_colored("Session ended successfully", "SYSTEM")


if __name__ == "__main__":
    asyncio.run(main())
