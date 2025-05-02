#!/usr/bin/env python
"""
Multi-Agent System with AgentConnect

This example demonstrates a modular multi-agent system using AgentConnect framework.
Each agent is implemented in its own file, and this script orchestrates their interactions.

Key features demonstrated:
- Modular agent design with separation of concerns
- Registry-based agent discovery and collaboration
- Clean dependency injection
- Human-in-the-loop CLI interaction
- Message flow visualization

Components:
1. Telegram Agent - Handles Telegram messaging platform interactions
2. Research Agent - Performs web searches and information retrieval
3. Content Processing Agent - Handles document processing and format conversion
4. Data Analysis Agent - Analyzes data and creates visualizations
5. HumanAgent - Provides CLI interface for direct agent interaction

Required Environment Variables:
- TELEGRAM_BOT_TOKEN: API token for your Telegram bot (get from @BotFather) 
- An LLM provider API key (one of the following):
  - GOOGLE_API_KEY
  - OPENAI_API_KEY
  - ANTHROPIC_API_KEY
  - GROQ_API_KEY
- TAVILY_API_KEY: Optional API key for Tavily Search (get from https://tavily.com)

Usage:
    python examples/multi_agent/multi_agent_system.py
"""

import asyncio
import os
import sys
from typing import Dict, Any
from dotenv import load_dotenv
from colorama import init

# Import agents from their respective modules
from agentconnect.core.registry import AgentRegistry
from agentconnect.communication import CommunicationHub
from agentconnect.core.types import ModelProvider, ModelName
from agentconnect.utils.logging_config import setup_logging, LogLevel, disable_all_logging
from agentconnect.agents import HumanAgent
from agentconnect.core.types import AgentIdentity

# Import agent creators from their respective modules
from examples.multi_agent.telegram_agent import create_telegram_agent
from examples.multi_agent.research_agent import create_research_agent
from examples.multi_agent.content_processing_agent import create_content_processing_agent 
from examples.multi_agent.data_analysis_agent import create_data_analysis_agent
from examples.multi_agent.message_logger import print_colored, agent_message_logger

# Initialize colorama
init()

async def setup_agents(enable_logging: bool = False) -> Dict[str, Any]:
    """
    Set up the registry, hub, and agents.
    
    Args:
        enable_logging (bool): Whether to enable detailed logging
        
    Returns:
        Dict[str, Any]: Dictionary containing registry, hub, agents, and tasks
    """
    # Load environment variables
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
        disable_all_logging()

    # Check for required API keys
    api_key = os.getenv("GOOGLE_API_KEY")
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")

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

    if not telegram_token:
        print_colored(
            "Warning: TELEGRAM_BOT_TOKEN not found. Telegram agent functionality will be limited.", 
            "WARNING"
        )

    # Create registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    # Register message logger to visualize agent collaboration
    hub.add_global_handler(agent_message_logger)
    print_colored("Registered agent message flow logger to visualize collaboration", "INFO")
    
    # Create human agent for CLI interaction
    human_identity = AgentIdentity.create_key_based()
    human_agent = HumanAgent(
        agent_id="human_cli_user",
        name="CLI User",
        identity=human_identity,
    )

    # Create all agents
    try:
        # Create agents using the factory functions from their respective modules
        telegram_agent = create_telegram_agent(provider_type, model_name, api_key)
        research_agent = create_research_agent(provider_type, model_name, api_key)
        content_processing_agent = create_content_processing_agent(provider_type, model_name, api_key)
        data_analysis_agent = create_data_analysis_agent(provider_type, model_name, api_key, registry, hub)
        
        # Register all agents with the hub
        await hub.register_agent(telegram_agent)
        await hub.register_agent(research_agent)
        await hub.register_agent(content_processing_agent)
        await hub.register_agent(data_analysis_agent)
        await hub.register_agent(human_agent)
        
        print_colored("All agents registered successfully!", "INFO")
        
        # Start the agent processing loops
        agent_tasks = []
        agent_tasks.append(asyncio.create_task(telegram_agent.run()))
        agent_tasks.append(asyncio.create_task(research_agent.run()))
        agent_tasks.append(asyncio.create_task(content_processing_agent.run()))
        agent_tasks.append(asyncio.create_task(data_analysis_agent.run()))
        
        return {
            "registry": registry,
            "hub": hub,
            "human_agent": human_agent,
            "telegram_agent": telegram_agent,
            "research_agent": research_agent,
            "content_processing_agent": content_processing_agent,
            "data_analysis_agent": data_analysis_agent,
            "agent_tasks": agent_tasks,
        }
        
    except Exception as e:
        print_colored(f"Error setting up agents: {e}", "ERROR")
        raise RuntimeError(f"Failed to set up agents: {e}")


async def run_multi_agent_system(enable_logging: bool = False) -> None:
    """
    Main function to run the multi-agent system.
    
    Args:
        enable_logging (bool): Whether to enable detailed logging
    """
    print_colored("=== AgentConnect Multi-Agent System ===", "SYSTEM")
    print_colored(
        "This example demonstrates a modular multi-agent system with separate agent implementations.", 
        "SYSTEM"
    )
    print_colored("Available specialized agents:", "SYSTEM")
    print_colored("1. Telegram Agent - Handles Telegram user interactions", "TELEGRAM")
    print_colored(
        "2. Research Agent - Performs web searches and creates research reports", "RESEARCH"
    )
    print_colored(
        "3. Content Processing Agent - Processes and transforms content between formats", "CONTENT"
    )
    print_colored("4. Data Analysis Agent - Analyzes data and creates visualizations", "DATA")
    print_colored("\nSetting up agents...", "SYSTEM")

    agents = None

    try:
        # Set up agents
        agents = await setup_agents(enable_logging)

        print_colored("Agents are ready! System is now running.", "SYSTEM")
        
        if os.getenv("TELEGRAM_BOT_TOKEN"):
            print_colored("Telegram bot is active. Open your Telegram app and start chatting with your bot.", "TELEGRAM")
        
        # Start CLI interaction with the content processing agent
        print_colored("\n=== CLI Interface with Content Processing Agent ===", "CONTENT")
        print_colored("You can directly interact with the Content Processing Agent through this CLI.", "CONTENT")
        print_colored("Type your messages and press Enter to send. Type 'exit' to end the session.", "CONTENT")
        print_colored("Agent interactions will be displayed in the terminal.", "CONTENT")
        
        # Start interaction between human agent and content processing agent
        human_interaction_task = asyncio.create_task(
            agents["human_agent"].start_interaction(agents["content_processing_agent"])
        )
        
        # Add the human interaction task to the list of tasks
        agents["agent_tasks"].append(human_interaction_task)
        
        print_colored("Press Ctrl+C to stop all agents and exit.", "SYSTEM")

        # Keep the main task running until interrupted
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print_colored("\nOperation interrupted by user", "WARNING")
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

            # Remove message logger
            if "hub" in agents:
                try:
                    agents["hub"].remove_global_handler(agent_message_logger)
                    print_colored("Removed agent message flow logger", "INFO")
                except Exception as e:
                    print_colored(f"Error removing message logger: {e}", "ERROR")

            # Stop all agents with the new stop method
            for agent_id in [
                "telegram_agent",
                "research_agent",
                "content_processing_agent",
                "data_analysis_agent",
            ]:
                if agent_id in agents:
                    try:
                        await agents[agent_id].stop()
                        print_colored(f"Stopped {agent_id}", "SYSTEM")
                    except Exception as e:
                        print_colored(f"Error stopping {agent_id}: {e}", "ERROR")

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

            # Unregister agents
            for agent_id in [
                "telegram_agent",
                "research_agent",
                "content_processing_agent",
                "data_analysis_agent",
                "human_agent",
            ]:
                if agent_id in agents:
                    try:
                        await agents["hub"].unregister_agent(agents[agent_id].agent_id)
                        print_colored(f"Unregistered {agent_id}", "SYSTEM")
                    except Exception as e:
                        print_colored(f"Error unregistering {agent_id}: {e}", "ERROR")

        print_colored("Multi-agent system stopped successfully!", "SYSTEM")


if __name__ == "__main__":
    try:
        # Add --logging flag for detailed logging
        if "--logging" in sys.argv:
            asyncio.run(run_multi_agent_system(enable_logging=True))
        else:
            asyncio.run(run_multi_agent_system())
    except KeyboardInterrupt:
        print_colored("\nAll agents terminated by user", "WARNING")
    except Exception as e:
        print_colored(f"Fatal error: {e}", "ERROR")
        sys.exit(1) 