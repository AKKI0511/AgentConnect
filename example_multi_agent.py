import asyncio
import json
import logging
import os
import time
from dotenv import load_dotenv
from colorama import init, Fore, Style
from typing import List

from src.agents.ai_agent import AIAgent
from src.communication.hub import CommunicationHub
from src.core.registry import AgentRegistry
from src.core.types import (
    ModelProvider,
    ModelName,
    InteractionMode,
    AgentIdentity,
    MessageType,
)
from src.utils.logging_config import LogLevel, setup_logging

# Initialize colorama for cross-platform colored output
init()

# Define colors for different agents
AGENT_COLORS = {
    "processor1": Fore.CYAN,
    "analyst1": Fore.MAGENTA,
    "system": Fore.YELLOW
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

async def run_ecommerce_analysis_demo(enable_logging: bool = True) -> None:
    """
    Run an e-commerce analysis demo with multiple AI agents collaborating to analyze data.
    
    This demo showcases interaction between a data processor and business analyst agent
    analyzing e-commerce performance data and providing insights.
    
    Args:
        enable_logging (bool): Flag to enable detailed logging. Defaults to False.
    """
    load_dotenv()

    # Configure logging
    if enable_logging:
        setup_logging(level=LogLevel.INFO)
    else:
        logging.disable(logging.CRITICAL)

    # Initialize core components
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    # Create secure agent identities
    data_processor_identity = AgentIdentity.create_key_based()
    analyst_identity = AgentIdentity.create_key_based()

    # Initialize specialized AI agents
    data_processor = AIAgent(
        agent_id="processor1",
        name="DataProcessor",
        provider_type=ModelProvider.GROQ,
        model_name=ModelName.LLAMA33_70B_VTL,
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        identity=data_processor_identity,
        capabilities=["data_processing", "statistical_analysis", "trend_detection"],
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
        personality="detail-oriented data analyst focused on identifying key metrics and trends",
        max_tokens_per_minute=7000,
        max_tokens_per_hour=120000,
    )

    business_analyst = AIAgent(
        agent_id="analyst1",
        name="BusinessAnalyst", 
        provider_type=ModelProvider.GROQ,
        model_name=ModelName.LLAMA3_70B,
        api_key=os.getenv("OPENAI_API_KEY"),
        identity=analyst_identity,
        capabilities=["business_analysis", "strategy_recommendation", "performance_optimization"],
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
        personality="strategic business analyst focused on actionable insights and recommendations",
        max_tokens_per_minute=700,
        max_tokens_per_hour=120000,
    )

    agents = [data_processor, business_analyst]
    tasks: List[asyncio.Task] = []

    try:
        # Register agents
        for agent in agents:
            if not await hub.register_agent(agent):
                print_system_message(f"❌ Failed to register {agent.name}")
                return

        # Start agent processing loops
        tasks = [asyncio.create_task(agent.run()) for agent in agents]

        print_system_message("=== Starting E-commerce Analysis ===")

        # Initialize analysis with structured data
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
        previous_message_count = 0
        max_wait_time = 20
        start_time = time.time()
        conversation_ended = False

        while time.time() - start_time < max_wait_time and not conversation_ended:
            await asyncio.sleep(1)
            messages = hub.get_message_history()

            # Display new messages with colors
            if len(messages) > previous_message_count:
                for message in messages[previous_message_count:]:
                    if message.message_type == MessageType.STOP:
                        conversation_ended = True
                        break
                    print_colored_message(message.sender_id, message.content)
                previous_message_count = len(messages)

            # Check for conversation timeout
            if len(messages) == previous_message_count:
                elapsed_time = time.time() - start_time
                if elapsed_time >= 5:
                    print_system_message("No new messages received. Assuming conversation has ended.")
                    conversation_ended = True

        if not conversation_ended:
            print_system_message("Maximum wait time reached. Ending session.")

        print_system_message("=== Analysis Complete ===")

    except Exception as e:
        print_system_message(f"\n❌ Error during analysis: {e}")
    finally:
        print_system_message("\n🛑 Concluding analysis session...")
        
        # Cleanup resources
        for agent in agents:
            agent.is_running = False

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
            await hub.unregister_agent(agent.agent_id)

        print_system_message("✅ Analysis session completed")

if __name__ == "__main__":
    asyncio.run(run_ecommerce_analysis_demo())
