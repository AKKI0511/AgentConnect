#!/usr/bin/env python
"""
AgentConnect Examples Runner

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

Examples:
    python run_example.py chat
    python run_example.py multi --enable-logging
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


def check_environment() -> bool:
    """
    Check if necessary environment variables are set.

    Returns:
        bool: True if at least one LLM API key is available
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
    parser = argparse.ArgumentParser(
        description="Run AgentConnect examples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available examples:
  chat      - Simple chat with an AI assistant
  multi     - Multi-agent e-commerce analysis
  research  - Research assistant with multiple agents
  data      - Data analysis and visualization assistant

Examples:
  python run_example.py chat
  python run_example.py multi --enable-logging
        """,
    )

    parser.add_argument(
        "example",
        choices=["chat", "multi", "research", "data"],
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
    }

    print_colored("\n" + "=" * 60, Fore.CYAN)
    print_colored(
        f"AgentConnect Example: {example_descriptions[args.example]}", Fore.CYAN
    )
    print_colored("=" * 60 + "\n", Fore.CYAN)

    # Check environment variables
    if not check_environment():
        sys.exit(1)

    try:
        # Run the selected example
        asyncio.run(run_example(args.example, args.enable_logging))
    except KeyboardInterrupt:
        print_colored("\n\n⚠️ Operation interrupted by user", Fore.YELLOW)
        sys.exit(0)


if __name__ == "__main__":
    main()
