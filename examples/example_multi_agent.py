#!/usr/bin/env python
"""
Multi-Agent E-Commerce Analysis Example for AgentConnect

This example demonstrates a collaborative interaction between specialized AI agents
analyzing e-commerce performance data. It showcases advanced capabilities of the
AgentConnect framework for autonomous agent-to-agent communication.

Key features demonstrated:
- Specialized agent capabilities for data processing and business analysis
- Autonomous agent-to-agent communication
- Capability-based agent discovery and collaboration
- Structured data analysis and insights generation
- Message tracking and conversation monitoring

Required environment variables:
- At least one provider API key (GOOGLE_API_KEY recommended for this example)
"""

import asyncio
import json
import os
import time
from typing import Dict, List

from colorama import Fore, Style, init
from dotenv import load_dotenv

# Import directly from the agentconnect package (using the public API)
from agentconnect.prebuilt import AIAgent
from agentconnect.team import CommunicationHub
from agentconnect.core.message import Message
from agentconnect.index.registry import AgentRegistry
from agentconnect.core.types import (
    AgentIdentity,
    Capability,
    InteractionMode,
    MessageKind,
    ModelName,
    ModelProvider,
)

# Initialize colorama for cross-platform colored output
init()

# Define colors for different agents
AGENT_COLORS = {
    "processor1": Fore.CYAN,
    "analyst1": Fore.MAGENTA,
    "system": Fore.YELLOW,
}

# Sample e-commerce data for analysis
ECOMMERCE_DATA = {
    "revenue": {
        "total": 1000000,
        "product_categories": {
            "electronics": 600000,
            "apparel": 300000,
            "home_goods": 100000,
        },
    },
    "customer_segments": {
        "new_customers": {
            "count": 5000,
            "revenue": 250000,
        },
        "returning_customers": {
            "count": 2000,
            "revenue": 750000,
        },
    },
    "marketing_campaigns": {
        "campaign_1": {
            "cost": 50000,
            "revenue": 200000,
        },
        "campaign_2": {
            "cost": 80000,
            "revenue": 300000,
        },
    },
}

# Define structured capabilities for agents
DATA_PROCESSING_CAPABILITY = Capability(
    name="data_processing",
    description="Process and transform raw data into structured formats",
    input_schema={"data": "Any raw data format"},
    output_schema={"processed_data": "Structured data format"},
)

STATISTICAL_ANALYSIS_CAPABILITY = Capability(
    name="statistical_analysis",
    description="Perform statistical analysis on data to extract insights",
    input_schema={"data": "Structured data format"},
    output_schema={"analysis_results": "Statistical insights"},
)

TREND_DETECTION_CAPABILITY = Capability(
    name="trend_detection",
    description="Identify trends and patterns in data over time",
    input_schema={"data": "Time-series data"},
    output_schema={"trends": "Identified patterns and trends"},
)

BUSINESS_ANALYSIS_CAPABILITY = Capability(
    name="business_analysis",
    description="Analyze business performance and metrics",
    input_schema={"business_data": "Business performance metrics"},
    output_schema={"business_insights": "Business performance analysis"},
)

STRATEGY_RECOMMENDATION_CAPABILITY = Capability(
    name="strategy_recommendation",
    description="Provide strategic recommendations based on data analysis",
    input_schema={"analysis_results": "Analysis results"},
    output_schema={"recommendations": "Strategic recommendations"},
)

PERFORMANCE_OPTIMIZATION_CAPABILITY = Capability(
    name="performance_optimization",
    description="Identify opportunities for performance optimization",
    input_schema={"performance_data": "Performance metrics"},
    output_schema={"optimization_suggestions": "Optimization recommendations"},
)

# Message tracking variables
message_count = 0
processed_message_ids = set()


def print_colored_message(sender_id: str, content: str) -> None:
    """
    Print a message with color based on the sender ID.

    Args:
        sender_id (str): ID of the message sender
        content (str): Message content to print
    """
    color = AGENT_COLORS.get(sender_id, Fore.WHITE)
    print(f"\n{color}{'='*35}[{sender_id}]{'='*35}")
    print(f"{content}{Style.RESET_ALL}\n")


def print_system_message(message: str) -> None:
    """
    Print a system message in yellow color.

    Args:
        message (str): System message to print
    """
    print(f"\n{Fore.YELLOW}{message}{Style.RESET_ALL}")


def get_message_type_color(message_type: MessageKind) -> str:
    """
    Get the appropriate color for a message type.

    Args:
        message_type: The message type

    Returns:
        The ANSI color code for the message type
    """
    type_colors = {
        MessageKind.EVENT: Fore.WHITE,
        MessageKind.RESPONSE: Fore.GREEN,
        MessageKind.ERROR: Fore.RED,
        MessageKind.EVENT: Fore.YELLOW,
        MessageKind.REQUEST: Fore.BLUE,
        MessageKind.RESPONSE: Fore.CYAN,
        MessageKind.EVENT: Fore.MAGENTA,
        MessageKind.EVENT: Fore.RED,
        MessageKind.EVENT: Fore.LIGHTBLACK_EX,
    }
    return type_colors.get(message_type, Fore.WHITE)


async def message_tracking_handler(message: Message) -> None:
    """
    Global message tracking handler that automatically logs all messages.

    Args:
        message: The message to track
    """
    global message_count, processed_message_ids

    # Skip if we've already processed this message
    if message.id in processed_message_ids:
        return

    # Add to processed messages
    processed_message_ids.add(message.id)
    message_count += 1

    # Get colors for sender and message type
    sender_color = AGENT_COLORS.get(message.sender_id, Fore.WHITE)
    type_color = get_message_type_color(message.kind)

    # Format metadata for display
    metadata_str = ""
    if message.metadata:
        # Only show relevant metadata fields
        relevant_fields = ["request_id", "response_to", "task", "error_type"]
        filtered_metadata = {
            k: v for k, v in message.metadata.items() if k in relevant_fields
        }
        if filtered_metadata:
            metadata_str = f"\n{Fore.LIGHTBLACK_EX}Metadata: {json.dumps(filtered_metadata, indent=2)}{Style.RESET_ALL}"

    # Print formatted message
    print(
        f"\n{sender_color}[{message.sender_id}] {Fore.WHITE}→ {sender_color}[{message.receiver_id}] "
        f"{type_color}[{message.kind.value}]{Style.RESET_ALL}"
    )

    # Truncate content if too long
    content = message.content
    if len(content) > 500:
        content = content[:500] + "... (truncated)"

    print(f"{sender_color}{content}{Style.RESET_ALL}{metadata_str}")
    print(f"{Fore.LIGHTBLACK_EX}{'─' * 80}{Style.RESET_ALL}")


async def run_ecommerce_analysis_demo(enable_logging: bool = False) -> None:
    """
    Run an e-commerce analysis demo with multiple AI agents collaborating to analyze data.

    This demo showcases interaction between a data processor and business analyst agent
    analyzing e-commerce performance data and providing insights.

    Args:
        enable_logging (bool): Flag to enable detailed logging. Defaults to False.
    """
    # Load environment variables from .env file
    load_dotenv()

    # Check for required API keys
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print_system_message("❌ Error: Missing GOOGLE_API_KEY environment variable")
        print_system_message("This example works best with Google's Gemini models")

        # Check if any alternative API keys are available
        fallback_providers = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY"]
        for provider_env in fallback_providers:
            if os.getenv(provider_env):
                print_system_message(
                    f"Found {provider_env} - will use this as fallback"
                )
                provider_name = provider_env.split("_")[0].lower()
                provider_type = ModelProvider(provider_name)
                model_name = (
                    ModelName.GPT4O
                    if provider_name == "openai"
                    else (
                        ModelName.CLAUDE_3_OPUS
                        if provider_name == "anthropic"
                        else ModelName.LLAMA3_70B
                    )
                )
                api_key = os.getenv(provider_env)
                break
        else:
            print_system_message(
                "No API keys found. Please set at least one provider API key."
            )
            return
    else:
        # Use Google provider and models
        provider_type = ModelProvider.GOOGLE
        model_name = ModelName.GEMINI2_FLASH

    # Opt-in example logging: elevate a small allowlist to INFO
    if enable_logging:
        import logging as _pylog
        for name in [
            "agentconnect.team.runtime",
            "agentconnect.agent.base",
            "agentconnect.prebuilt.human_agent",
            "agentconnect.prebuilt.ai_agent",
            "agentconnect.index.registry.registry_base",
        ]:
            _pylog.getLogger(name).setLevel(_pylog.INFO)

    # Initialize core components
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    # Register the message tracking handler as a global handler
    hub.add_global_handler(message_tracking_handler)
    print_system_message(
        "🔍 Message tracking enabled - all messages will be automatically logged"
    )

    # Create secure agent identities
    data_processor_identity = AgentIdentity.create_key_based()
    analyst_identity = AgentIdentity.create_key_based()

    # Initialize specialized AI agents
    data_processor = AIAgent(
        agent_id="processor1",
        name="DataProcessor",
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=data_processor_identity,
        capabilities=[
            DATA_PROCESSING_CAPABILITY,
            STATISTICAL_ANALYSIS_CAPABILITY,
            TREND_DETECTION_CAPABILITY,
        ],
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
        personality="detail-oriented data analyst focused on identifying key metrics and trends",
        max_tokens_per_minute=7000,
        max_tokens_per_hour=120000,
    )

    business_analyst = AIAgent(
        agent_id="analyst1",
        name="BusinessAnalyst",
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=analyst_identity,
        capabilities=[
            BUSINESS_ANALYSIS_CAPABILITY,
            STRATEGY_RECOMMENDATION_CAPABILITY,
            PERFORMANCE_OPTIMIZATION_CAPABILITY,
        ],
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
        personality="strategic business analyst focused on actionable insights and recommendations",
        max_tokens_per_minute=7000,
        max_tokens_per_hour=120000,
    )

    agents = [data_processor, business_analyst]
    tasks: List[asyncio.Task] = []

    try:
        # Register agents
        registration_successful = True
        for agent in agents:
            if not await hub.register_agent(agent):
                print_system_message(f"❌ Failed to register {agent.name}")
                registration_successful = False
                break
            print_system_message(
                f"✅ Registered agent: {agent.name} ({agent.agent_id})"
            )

        if not registration_successful:
            print_system_message("❌ Agent registration failed. Exiting demo.")
            return

        # Start agent processing loops
        tasks = [asyncio.create_task(agent.run()) for agent in agents]
        print_system_message(f"🚀 Started {len(tasks)} agent processing loops")

        print_system_message("=== Starting E-commerce Analysis ===")

        # Initialize analysis with structured data
        print_system_message(
            "📤 Sending initial message from data processor to business analyst..."
        )
        initial_message = await data_processor.send_message(
            receiver_id=business_analyst.agent_id,
            content=f"""I have processed our e-commerce platform's recent performance data.
            Here's the detailed dataset for analysis:
            {json.dumps(ECOMMERCE_DATA, indent=2)}

            Could you analyze this data and provide strategic insights on:
            1. Revenue trends and opportunities
            2. Customer segment performance
            3. Marketing campaign effectiveness
            4. Recommendations for optimization""",
            metadata={
                "task": "ecommerce_analysis",
                "data_type": "performance_metrics",
                "time_period": "current_month",
                "analysis_required": [
                    "trend_analysis",
                    "segment_performance",
                    "campaign_effectiveness",
                    "optimization_recommendations",
                ],
            },
        )

        if not initial_message:
            raise RuntimeError("Failed to send initial message")

        print_system_message("🔄 Agents are analyzing the e-commerce data...")
        print_system_message("=== Live Analysis Discussion ===")

        # Monitor the autonomous analysis discussion
        max_wait_time = 120  # Increased wait time to account for rate limiting
        start_time = time.time()
        conversation_ended = False
        last_message_time = time.time()
        current_message_count = message_count

        while time.time() - start_time < max_wait_time and not conversation_ended:
            await asyncio.sleep(0.5)

            # Check if new messages have been processed
            if message_count > current_message_count:
                current_message_count = message_count
                last_message_time = time.time()

            # Check for conversation timeout (no new messages for a while)
            if time.time() - last_message_time >= 30:
                print_system_message(
                    f"No new messages received for 30 seconds. Assuming conversation has ended."
                )
                conversation_ended = True

        if not conversation_ended:
            print_system_message("Maximum wait time reached. Ending session.")

        # Print conversation summary
        print_system_message(f"=== Analysis Complete ===")
        print_system_message(f"Total messages exchanged: {message_count}")

        # Get the full message history for analysis
        message_history = hub.get_message_history()

        # Count messages by type
        message_types: Dict[str, int] = {}
        for msg in message_history:
            msg_type = msg.kind.value
            message_types[msg_type] = message_types.get(msg_type, 0) + 1

        # Print message type statistics
        print_system_message("Message type statistics:")
        for msg_type, count in message_types.items():
            print(f"  - {msg_type}: {count}")

    except KeyboardInterrupt:
        print_system_message("\n⚠️ Operation interrupted by user.")
    except Exception as e:
        print_system_message(f"\n❌ Error during analysis: {e}")
    finally:
        print_system_message("\n🛑 Concluding analysis session...")

        # Cleanup resources
        for agent in agents:
            await agent.stop()
            print_system_message(f"Stopped agent: {agent.name}")

        # Cancel running tasks
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass

        # Unregister agents
        for agent in agents:
            try:
                await hub.unregister_agent(agent.agent_id)
                print_system_message(
                    f"✅ Unregistered agent: {agent.name} ({agent.agent_id})"
                )
            except Exception as e:
                print_system_message(f"⚠️ Error unregistering {agent.name}: {str(e)}")

        print_system_message("✅ Analysis session completed")


if __name__ == "__main__":
    asyncio.run(run_ecommerce_analysis_demo())
