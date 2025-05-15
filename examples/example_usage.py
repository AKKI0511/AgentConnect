#!/usr/bin/env python
"""
Basic Chat Example for AgentConnect

This example demonstrates a simple interactive conversation between a human user
and an AI assistant. It showcases the fundamental capabilities of AgentConnect
including agent creation, secure communication, and real-time message exchange.

Key features demonstrated:
- Dynamic provider and model selection
- Secure agent registration and communication with cryptographic verification
- Real-time message exchange with proper error handling
- Graceful session management and cleanup
- Optional payment capabilities using blockchain technology

Required environment variables:
- At least one provider API key (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
- For payment capabilities: CDP_API_KEY_NAME, CDP_API_KEY_PRIVATE (Coinbase Developer Platform)
"""

import asyncio
import logging
import os

from colorama import Fore, Style, init
from dotenv import load_dotenv

# Import directly from the agentconnect package (using the public API)
from agentconnect.agents import AIAgent, HumanAgent
from agentconnect.communication import CommunicationHub
from agentconnect.core.registry import AgentRegistry
from agentconnect.core.types import (
    AgentIdentity,
    AgentProfile,
    AgentType,
    Capability,
    InteractionMode,
    ModelName,
    ModelProvider,
    Skill,
)
from agentconnect.providers import ProviderFactory
from agentconnect.utils.logging_config import LogLevel, setup_logging

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


async def main(enable_logging: bool = False, enable_payments: bool = False) -> None:
    """
    Run an interactive demo between a human user and an AI assistant.

    This demo showcases:
    1. Dynamic provider and model selection
    2. Secure agent registration and communication
    3. Real-time message exchange with proper error handling
    4. Graceful session management and cleanup
    5. Optional blockchain payment capabilities

    Args:
        enable_logging (bool): Enable detailed logging for debugging. Defaults to False.
        enable_payments (bool): Enable blockchain payment capabilities. Defaults to False.
    """
    # Load environment variables from .env file
    load_dotenv()

    # Configure logging
    if enable_logging:
        setup_logging(
            level=LogLevel.DEBUG,
            module_levels={
                "AgentRegistry": LogLevel.WARNING,
                "CommunicationHub": LogLevel.INFO,
                "SimpleAgentProtocol": LogLevel.DEBUG,
                "utils.interaction_control": LogLevel.INFO,
                "agents.ai_agent": LogLevel.INFO,
                "agents.human_agent": LogLevel.INFO,
                "core.agent": LogLevel.INFO,
                "core.message": LogLevel.INFO,
                "core.registry": LogLevel.INFO,
                "communication.hub": LogLevel.INFO,
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

    # Check for available API keys
    api_keys = {}
    for provider in ModelProvider:
        env_var = f"{provider.value.upper()}_API_KEY"
        if os.getenv(env_var):
            api_keys[provider.value] = env_var

    if not api_keys:
        print_colored(
            "No API keys found in environment. Please set at least one provider API key.",
            "ERROR",
        )
        print_colored("Example: OPENAI_API_KEY=your_key_here", "ERROR")
        return

    # Provider selection
    print_colored("\n=== AI Provider Selection ===", "SYSTEM")
    print_colored("\nAvailable providers:", "INFO")
    for provider in api_keys:
        print_colored(f"  • {provider}", "INFO")

    # Get provider selection
    while True:
        provider_name = input(
            f"{COLORS['USER']}Select provider: {Style.RESET_ALL}"
        ).lower()
        if provider_name in api_keys:
            break
        print_colored(
            f"Invalid provider. Please select from: {', '.join(api_keys.keys())}",
            "ERROR",
        )

    # Get API key
    try:
        provider_type = ModelProvider(provider_name)
        api_key = os.getenv(api_keys[provider_name])
        if not api_key:
            raise ValueError(f"Missing API key for {provider_name}")
    except ValueError as e:
        print_colored(f"Error: {str(e)}", "ERROR")
        return

    # Model selection
    try:
        provider = ProviderFactory.create_provider(provider_type, api_key)
        print_colored("\nAvailable models:", "INFO")
        available_models = provider.get_available_models()
        for model in available_models:
            print_colored(f"  • {model.value}", "INFO")

        # Get model selection
        while True:
            model_input = input(f"{COLORS['USER']}Select model: {Style.RESET_ALL}")
            try:
                model_name = ModelName(model_input)
                if model_name in available_models:
                    break
                print_colored(
                    f"Model not available. Please select from the list above.", "ERROR"
                )
            except ValueError:
                print_colored(
                    f"Invalid model name. Please enter exactly as shown above.", "ERROR"
                )
    except Exception as e:
        print_colored(f"Error initializing provider: {str(e)}", "ERROR")
        return

    # Initialize agents
    human = HumanAgent(
        agent_id="human1", name="User", identity=human_identity, organization="org1"
    )

    # --- AI Agent Setup ---

    # Create Capability objects for AI capabilities
    ai_capabilities = [
        Capability(
            name="conversation",
            description="General conversation and assistance",
            input_schema={"query": "string"},
            output_schema={"response": "string"},
        )
    ]
    
    # Create AI agent skills
    ai_skills = [
        Skill(name="general_assistance", description="Provide helpful responses to user queries"),
        Skill(name="information_retrieval", description="Retrieve and present information accurately"),
        Skill(name="conversation", description="Engage in natural, helpful dialogue")
    ]

    # Create agent profile
    ai_profile = AgentProfile(
        agent_id="ai1",
        agent_type=AgentType.AI,
        name="Assistant",
        summary="A helpful AI assistant for general conversation",
        description="An AI assistant that provides helpful, accurate, and professional responses to user queries.",
        capabilities=ai_capabilities,
        skills=ai_skills,
        tags=["assistant", "conversation", "help"],
        examples=[
            "How can I help you today?",
            "I can answer questions on various topics.",
            "Let me assist you with that request."
        ]
    )

    # Initialize wallet configuration if payments are enabled
    if enable_payments:
        print_colored(
            "Payment capabilities enabled. Environment will be validated during agent initialization.",
            "INFO"
        )
        print_colored(
            "Required environment variables: CDP_API_KEY_NAME, CDP_API_KEY_PRIVATE_KEY, (optional) CDP_NETWORK_ID",
            "INFO"
        )

    ai_assistant = AIAgent(
        agent_id="ai1",
        identity=ai_identity,
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        profile=ai_profile,
        personality="helpful and professional",
        enable_payments=enable_payments,  # Enable payment capabilities if requested
    )
    # --- End AI Agent Setup ---

    agents = [human, ai_assistant]
    ai_task = None

    try:
        # Register agents
        for agent in agents:
            if not await hub.register_agent(agent):
                print_colored(f"Failed to register {agent.name}", "ERROR")
                return

        # Start AI processing
        ai_task = asyncio.create_task(ai_assistant.run())

        # Display payment address if payment capabilities are enabled
        if enable_payments and ai_assistant.payments_enabled:
            print_colored(f"\nAI Assistant Payment Address: {ai_assistant.metadata.payment_address}", "INFO")

        print_colored("\n=== Starting Interactive Session ===", "SYSTEM")
        print_colored("Type your messages and press Enter to send", "INFO")
        print_colored("Type 'exit' to end the session", "INFO")

        await human.start_interaction(ai_assistant)

    except KeyboardInterrupt:
        print_colored("\nInterrupted by user. Ending session...", "SYSTEM")
    except Exception as e:
        print_colored(f"Error in interaction: {str(e)}", "ERROR")
    finally:
        print_colored("\nEnding session...", "SYSTEM")
        # Cleanup
        if ai_assistant:
            await ai_assistant.stop()
        if ai_task:
            try:
                await asyncio.wait_for(ai_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                if not ai_task.done():
                    ai_task.cancel()

        # Unregister agents
        for agent in agents:
            try:
                await hub.unregister_agent(agent.agent_id)
            except Exception as e:
                print_colored(
                    f"Error unregistering {agent.agent_id}: {str(e)}", "ERROR"
                )

        print_colored("Session ended successfully", "SYSTEM")


if __name__ == "__main__":
    # By default, run without payments enabled for simpler setup
    # To enable payments, you would call main(enable_payments=True)
    asyncio.run(main(enable_payments=False))
