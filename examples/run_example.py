#!/usr/bin/env python
"""
[DEPRECATED] AgentConnect Examples Runner

⚠️ DEPRECATION NOTICE ⚠️
This script is deprecated and will be removed in a future release.
Please use the official AgentConnect CLI tool instead:

    # Run an example
    agentconnect --example chat
    agentconnect --example multi
    agentconnect --example research
    agentconnect --example data
    agentconnect --example telegram

    # Enable verbose logging
    agentconnect --example telegram --verbose

The CLI tool provides the same functionality with better integration
and is the recommended way to run examples.

-------------------

This script provides a simple command-line interface to run various examples
from the AgentConnect framework. It uses argparse to parse command-line arguments
and executes the selected example.

Usage:
    python run_example.py <example_name> [--enable-logging]

Available examples:
    chat - Simple chat with an AI assistant
    multi - Multi-agent e-commerce analysis
    research - Research assistant with multiple agents
    data - Data analysis and visualization assistant
    telegram - Telegram bot with specialized agents
"""

import argparse
import asyncio
import os
import sys

from colorama import Fore, Style, init
from dotenv import load_dotenv

# Initialize colorama for cross-platform colored output
init()

# Add parent directory to path to ensure examples can be run from any directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_colored(message: str, color: str = Fore.WHITE) -> None:
    """
    Print a colored message to the console.

    Args:
        message: The message to print
        color: The color to use (from colorama.Fore)
    """
    print(f"{color}{message}{Style.RESET_ALL}")


def check_environment(example_name: str = None) -> bool:
    """
    Check if necessary environment variables are set.

    Args:
        example_name: Optional name of the example to check specific requirements

    Returns:
        bool: True if required API keys are available
    """
    load_dotenv()

    # List of supported API keys
    api_keys = {
        "OPENAI_API_KEY": "OpenAI",
        "GOOGLE_API_KEY": "Google",
        "ANTHROPIC_API_KEY": "Anthropic",
        "GROQ_API_KEY": "Groq",
    }

    # Check for available API keys
    available_keys = []
    for key, provider in api_keys.items():
        if os.getenv(key):
            available_keys.append(provider)

    if not available_keys:
        print_colored(
            "⚠️ No API keys found. The examples require at least one of these:",
            Fore.YELLOW,
        )
        for key, provider in api_keys.items():
            print_colored(f"  - {key} ({provider})", Fore.YELLOW)
        print_colored(
            "Please set at least one API key in your environment or .env file.",
            Fore.YELLOW,
        )
        return False

    print_colored(f"✅ Found API key(s) for: {', '.join(available_keys)}", Fore.GREEN)
    
    # Check for example-specific requirements
    if example_name == "telegram":
        if not os.getenv("TELEGRAM_BOT_TOKEN"):
            print_colored(
                "⚠️ TELEGRAM_BOT_TOKEN not found. The Telegram example requires this environment variable.",
                Fore.YELLOW,
            )
            print_colored(
                "Please set TELEGRAM_BOT_TOKEN in your environment or .env file.",
                Fore.YELLOW,
            )
            return False
        else:
            print_colored("✅ Found TELEGRAM_BOT_TOKEN", Fore.GREEN)
    
    return True


async def run_example(example_name: str, enable_logging: bool = False) -> None:
    """
    Run the specified example.

    Args:
        example_name: Name of the example to run
        enable_logging: Whether to enable detailed logging

    Raises:
        ValueError: If the example name is not recognized
    """
    # Show deprecation notice
    print_colored("\n⚠️ DEPRECATION NOTICE ⚠️", Fore.YELLOW)
    print_colored(
        "This script is deprecated. Please use the CLI tool instead:",
        Fore.YELLOW,
    )
    print_colored(f"  agentconnect --example {example_name}", Fore.CYAN)
    if enable_logging:
        print_colored("  --verbose", Fore.CYAN)
    print_colored("", Fore.WHITE)
    
    # Import examples only when needed (lazy loading)
    try:
        if example_name == "chat":
            from examples.example_usage import main as run_chat_example

            await run_chat_example(enable_logging=enable_logging)

        elif example_name == "multi":
            from examples.example_multi_agent import \
                run_ecommerce_analysis_demo

            await run_ecommerce_analysis_demo(enable_logging=enable_logging)

        elif example_name == "research":
            from examples.research_assistant import run_research_assistant_demo

            await run_research_assistant_demo(enable_logging=enable_logging)

        elif example_name == "data":
            from examples.data_analysis_assistant import \
                run_data_analysis_assistant_demo

            await run_data_analysis_assistant_demo(enable_logging=enable_logging)
                
        elif example_name == "telegram":
            from examples.multi_agent.multi_agent_system import run_multi_agent_system as run_telegram_assistant

            await run_telegram_assistant(enable_logging=enable_logging)

        else:
            raise ValueError(f"Unknown example: {example_name}")

    except ImportError as e:
        print_colored(f"❌ Error importing example module: {e}", Fore.RED)
        print_colored(
            "Make sure you're running from the root directory of the project.",
            Fore.YELLOW,
        )
        sys.exit(1)
    except Exception as e:
        print_colored(f"❌ Error running example: {e}", Fore.RED)
        sys.exit(1)


def main() -> None:
    """
    Main function to parse arguments and run the selected example.
    """
    # Show deprecation warning
    print_colored("\n⚠️ DEPRECATION NOTICE ⚠️", Fore.YELLOW)
    print_colored(
        "This script is deprecated and will be removed in a future release.",
        Fore.YELLOW,
    )
    print_colored(
        "Please use the official AgentConnect CLI tool instead:",
        Fore.YELLOW,
    )
    print_colored("  agentconnect --example <name> [--verbose]", Fore.CYAN)
    print_colored("", Fore.WHITE)
    
    parser = argparse.ArgumentParser(
        description="Run AgentConnect examples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available examples:
  chat      - Simple chat with an AI assistant
  multi     - Multi-agent e-commerce analysis
  research  - Research assistant with multiple agents
  data      - Data analysis and visualization assistant
  telegram  - Telegram bot with specialized agents

Examples:
  python run_example.py chat
  python run_example.py multi --enable-logging
  python run_example.py telegram --enable-logging
        """,
    )

    parser.add_argument(
        "example",
        choices=["chat", "multi", "research", "data", "telegram"],
        help="The example to run",
    )

    parser.add_argument(
        "--enable-logging", action="store_true", help="Enable detailed logging output"
    )

    args = parser.parse_args()

    # Print the example header
    example_descriptions = {
        "chat": "Simple Chat with AI Assistant",
        "multi": "Multi-Agent E-commerce Analysis",
        "research": "Research Assistant with Multiple Agents",
        "data": "Data Analysis and Visualization Assistant",
        "telegram": "Telegram Bot with Specialized Agents",
    }

    print_colored("\n" + "=" * 60, Fore.CYAN)
    print_colored(
        f"AgentConnect Example: {example_descriptions[args.example]}", Fore.CYAN
    )
    print_colored("=" * 60 + "\n", Fore.CYAN)

    # Check environment variables with example-specific requirements
    if not check_environment(args.example):
        sys.exit(1)

    try:
        # Run the selected example
        asyncio.run(run_example(args.example, args.enable_logging))
    except KeyboardInterrupt:
        print_colored("\n\n⚠️ Operation interrupted by user", Fore.YELLOW)
        sys.exit(0)


if __name__ == "__main__":
    main()
