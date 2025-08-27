#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AgentConnect CLI - Command Line Interface for AgentConnect

This module provides command-line functionality for the AgentConnect framework,
allowing users to run examples, demos, and access utility functions through
a simple command-line interface.

Usage:
    agentconnect --version
    agentconnect --example chat
    agentconnect --example multi
    agentconnect --example research
    agentconnect --example data
    agentconnect --example telegram
    agentconnect --example agent_economy
    agentconnect --demo        # UI compatibility under development (Windows only)
    agentconnect --check-env
    agentconnect config init   # Generate example configuration file
    agentconnect config show   # Show current configuration
    agentconnect config validate <file.yaml>  # Validate configuration file
    agentconnect --help

Available examples:
    chat         - Simple chat with an AI assistant
    multi        - Multi-agent e-commerce analysis
    research     - Research assistant with multiple agents
    data         - Data analysis and visualization assistant
    telegram     - Modular multi-agent system with Telegram integration
    agent_economy - Autonomous workflow with agent payments system

Note: The demo UI is currently under development and only supported on Windows.
      For the best experience, please use the examples instead.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from agentconnect import __version__

# Configure logging
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """
    Configure logging for the CLI with colorful output.

    Args:
        verbose: Whether to enable verbose (DEBUG) logging
    """
    # Guard against duplicate setup
    root_logger = logging.getLogger()
    if getattr(root_logger, "_agentconnect_cli_configured", False):
        return

    if not verbose:
        # Ensure warnings/errors print without changing library loggers
        if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(
                logging.Formatter("%(levelname)s - %(message)s")
            )
            root_logger.addHandler(console_handler)
        # Do not set levels; keep defaults (WARNING and above emitted)
        root_logger._agentconnect_cli_configured = True  # type: ignore[attr-defined]
        return
    try:
        from colorama import init as colorama_init, Fore, Style

        colorama_init()
        COLORAMA_AVAILABLE = True
    except ImportError:
        COLORAMA_AVAILABLE = False

    class MultiColorFormatter(logging.Formatter):
        """
        A formatter that colors the log output based on the log level.
        """

        # Assign a different color to each log field for maximum clarity
        FIELD_COLORS = {
            "asctime": Fore.WHITE + Style.DIM,
            "name": Fore.MAGENTA,
        }
        LEVEL_COLORS = {
            logging.DEBUG: Fore.CYAN,
            logging.INFO: Fore.GREEN,
            logging.WARNING: Fore.YELLOW,
            logging.ERROR: Fore.RED,
            logging.CRITICAL: Fore.MAGENTA + Style.BRIGHT,
        }
        RESET = Style.RESET_ALL

        def format(self, record):
            """
            Format the log record.
            """
            # Use the base formatter to get the raw message
            base_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            msg = logging.Formatter(base_format).format(record)
            if not COLORAMA_AVAILABLE:
                return msg

            # Split the formatted message into its fields
            try:
                asctime, name, levelname, message = msg.split(" - ", 3)
            except Exception:
                # Fallback: color whole line by level if parsing fails
                color = self.LEVEL_COLORS.get(record.levelno, "")
                return f"{color}{msg}{self.RESET}"

            # Color each field
            asctime_col = self.FIELD_COLORS["asctime"] + asctime + self.RESET
            name_col = self.FIELD_COLORS["name"] + name + self.RESET
            level_col = self.LEVEL_COLORS[record.levelno] + levelname + self.RESET
            message_col = message + self.RESET

            return f"{asctime_col} - {name_col} - {level_col} - {message_col}"

    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Configure root logger
    root_logger = logging.getLogger()

    # Create console handler if not already present
    console_handler = None
    for h in root_logger.handlers:
        if isinstance(h, logging.StreamHandler):
            console_handler = h
            break
    if console_handler is None:
        console_handler = logging.StreamHandler()

    console_handler.setFormatter(MultiColorFormatter(log_format))

    # Add handler (only once)
    if console_handler not in root_logger.handlers:
        root_logger.addHandler(console_handler)

    # Elevate only the CLI module logger when verbose
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    root_logger._agentconnect_cli_configured = True  # type: ignore[attr-defined]


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Parse command line arguments.

    Args:
        args: Command line arguments. Defaults to sys.argv[1:].

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="AgentConnect - A framework for connecting and managing AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available examples:
  chat         - Simple chat with an AI assistant
  multi        - Multi-agent e-commerce analysis
  research     - Research assistant with multiple agents
  data         - Data analysis and visualization assistant
  telegram     - Modular multi-agent system with Telegram integration
  agent_economy - Autonomous workflow with agent payments system

Configuration commands:
  agentconnect config init              - Generate example agentconnect.yaml
  agentconnect config show              - Show current merged configuration
  agentconnect config validate <file>   - Validate configuration file

Examples:
  agentconnect --example chat
  agentconnect --example multi --verbose
  agentconnect --check-env
  agentconnect config init
        """,
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Config subcommand
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_subparsers = config_parser.add_subparsers(
        dest="config_action", help="Configuration actions"
    )

    # Config init
    config_subparsers.add_parser(
        "init", help="Generate example agentconnect.yaml configuration file"
    )

    # Config show
    config_subparsers.add_parser("show", help="Show current merged configuration")

    # Config validate
    validate_parser = config_subparsers.add_parser(
        "validate", help="Validate configuration file"
    )
    validate_parser.add_argument("file", help="Path to configuration file to validate")

    parser.add_argument(
        "--version", "-v", action="store_true", help="Show version and exit"
    )

    parser.add_argument(
        "--example",
        "-e",
        choices=[
            "chat",
            "multi",
            "research",
            "data",
            "telegram",
            "workflow",
            "agent_economy",
        ],
        help="Run a specific example: chat (simple AI assistant), multi (multi-agent ecommerce analysis), research (research assistant), data (data analysis assistant), telegram (modular multi-agent system with Telegram integration), agent_economy (autonomous workflow with payments), or workflow (legacy name, same as agent_economy)",
    )

    parser.add_argument(
        "--demo",
        "-d",
        action="store_true",
        help="Run the demo application (UI compatibility under development)",
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    parser.add_argument(
        "--check-env", action="store_true", help="Check environment configuration"
    )

    return parser.parse_args(args)


async def run_example(example_name: str, verbose: bool = False) -> None:
    """
    Run a specific example.

    Args:
        example_name: Name of the example to run
        verbose: Whether to enable verbose logging
    """
    logger.info("Running example: %s", example_name)

    # Check for research dependencies when running telegram example
    if example_name == "telegram":
        try:
            import arxiv  # noqa: F401
            import wikipedia  # noqa: F401
        except ImportError:
            logger.warning(
                "Research dependencies are missing for the multi-agent system"
            )
            logger.info("To install the required dependencies:")
            logger.info("  poetry install --with research")
            logger.info("  or: pip install arxiv wikipedia")
            logger.info(
                "The example will run, but research capabilities will be limited"
            )

    # Check for workflow dependencies
    if example_name in ["workflow", "agent_economy"]:
        try:
            from langchain_community.tools.tavily_search import (  # noqa: F401
                TavilySearchResults,  # noqa: F401
            )
            from langchain_community.tools.requests.tool import (  # noqa: F401
                RequestsGetTool,  # noqa: F401
            )
            from langchain_community.utilities import TextRequestsWrapper  # noqa: F401
            from colorama import init, Fore, Style  # noqa: F401
        except ImportError:
            logger.warning("Dependencies are missing for the agent economy demo")
            logger.info("To install the required dependencies:")
            logger.info("  poetry install --with research")
            logger.info(
                "  or: pip install langchain-community colorama tavily-python python-dotenv"
            )
            logger.info("Please install the missing dependencies and try again")
            sys.exit(1)

    try:
        if example_name == "chat":
            from examples import run_chat_example

            await run_chat_example(enable_logging=verbose)
        elif example_name == "multi":
            from examples import run_ecommerce_analysis_demo

            await run_ecommerce_analysis_demo(enable_logging=verbose)
        elif example_name == "research":
            from examples import run_research_assistant_demo

            await run_research_assistant_demo(enable_logging=verbose)
        elif example_name == "data":
            from examples import run_data_analysis_assistant_demo

            await run_data_analysis_assistant_demo(enable_logging=verbose)
        elif example_name == "telegram":
            from examples import run_telegram_assistant

            await run_telegram_assistant(enable_logging=verbose)
        elif example_name in ["workflow", "agent_economy"]:
            from examples.autonomous_workflow.run_workflow_demo import (
                main as run_workflow_demo,
            )

            await run_workflow_demo(enable_logging=verbose)
        else:
            logger.error("Unknown example: %s", example_name)
    except ImportError:
        logger.error("Error importing example", exc_info=True)
        logger.info("Make sure you have installed the required dependencies.")
        logger.info("Try: poetry install --with demo,research")
        sys.exit(1)
    except Exception:
        logger.exception("Error running example %s", example_name)
        sys.exit(1)


def run_demo() -> None:
    """Run the demo application."""
    logger.info("Starting demo application")
    logger.warning(
        "Note: UI compatibility is currently under development. Some features may not work as expected."
    )

    try:
        # Check if we're in a compatible environment
        logger.error("Demo UI is currently under development.")
        sys.exit(1)

        # from demos.run_demo import main as run_demo_main
        # run_demo_main()
    except ImportError:
        logger.error("Error importing demo", exc_info=True)
        logger.info("The demo UI is still under development.")
        logger.info("In the meantime, you can try our examples:")
        logger.info("  agentconnect --example chat")
        logger.info("  agentconnect --example multi")
        sys.exit(1)
    except Exception:
        logger.exception("Error running demo")
        logger.info(
            "The demo UI encountered an error. You can try our examples instead:"
        )
        logger.info("  agentconnect --example chat")
        logger.info("  agentconnect --example multi")
        sys.exit(1)


def check_environment() -> None:
    """
    Check that the environment is properly configured.

    Verifies API keys, dependencies, and other configuration requirements.
    At least one LLM provider API key must be set to use the framework.
    """
    logger.info("Checking environment configuration...")

    # Check for LLM API keys
    llm_api_keys = {
        "OPENAI_API_KEY": "OpenAI",
        "ANTHROPIC_API_KEY": "Anthropic",
        "GOOGLE_API_KEY": "Google",
        "GROQ_API_KEY": "Groq",
    }

    available_providers = []
    for env_var, provider_name in llm_api_keys.items():
        if os.environ.get(env_var):
            available_providers.append(provider_name)

    if not available_providers:
        logger.warning("No LLM provider API keys found. At least one is required.")
        logger.info("Set at least one of these environment variables:")
        for env_var, provider_name in llm_api_keys.items():
            logger.info("  - %s (for %s)", env_var, provider_name)
    else:
        logger.info("Available LLM providers: %s", ", ".join(available_providers))

    # Check for other required environment variables
    other_required_vars = []  # Add any other required env vars here
    if other_required_vars:
        missing_vars = [var for var in other_required_vars if not os.environ.get(var)]
        if missing_vars:
            logger.warning("Missing environment variables: %s", ", ".join(missing_vars))
            logger.info("Please set these variables in your .env file or environment")
        else:
            logger.info("All required environment variables are set")

    # Check for optional environment variables
    optional_vars = ["LANGSMITH_API_KEY", "TAVILY_API_KEY", "TELEGRAM_BOT_TOKEN"]
    missing_optional = [var for var in optional_vars if not os.environ.get(var)]

    if missing_optional:
        logger.info(
            "Optional environment variables not set: %s" % ", ".join(missing_optional)
        )

    # Check for research dependencies
    try:
        # Try to import research dependencies
        logger.debug("Checking for research dependencies...")
        try:
            import arxiv  # noqa: F401
            import wikipedia  # noqa: F401

            logger.info("Research dependencies (arxiv, wikipedia) are available")
        except ImportError:
            logger.warning("Research dependencies are missing. To install:")
            logger.info("poetry install --with research")
            logger.info("or: pip install arxiv wikipedia")
    except Exception:
        logger.debug("Error checking research dependencies", exc_info=True)

    # Check Python version
    python_version = sys.version_info
    if python_version.major < 3 or (
        python_version.major == 3 and python_version.minor < 11
    ):
        logger.warning(
            "Python version %s.%s may not be supported",
            python_version.major,
            python_version.minor,
        )
        logger.info("AgentConnect recommends Python 3.11 or newer")
    else:
        logger.info(
            "Python version %s.%s is supported",
            python_version.major,
            python_version.minor,
        )

    # Check for dotenv file
    dotenv_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(dotenv_path):
        logger.info(".env file found")
    else:
        logger.warning(".env file not found in current directory")
        logger.info("Consider creating a .env file for storing environment variables")

    logger.info("Environment check completed")


def handle_config_command(action: str, file_path: Optional[str] = None) -> None:
    """
    Handle configuration commands.

    Args:
        action: The config action (init, show, validate)
        file_path: Optional file path for validate action
    """
    try:
        from agentconnect.config import settings
        from agentconnect.config.loaders import (
            save_example_config,
            validate_config_file,
        )
        import json
    except ImportError:
        logger.error("Failed to import configuration modules", exc_info=True)
        sys.exit(1)

    if action == "init":
        # Generate example configuration file
        try:
            output_path = Path.cwd() / "agentconnect.yaml"
            if output_path.exists():
                response = input(
                    "File %s already exists. Overwrite? (y/N): " % output_path
                )
                if response.lower() not in ["y", "yes"]:
                    logger.info("Configuration generation cancelled")
                    return

            save_example_config(output_path)
            print(f"✅ Example configuration saved to: {output_path}")
            print("📝 Edit this file to customize your AgentConnect configuration")
            print("🔗 See documentation: agentconnect/config/README.md")

        except Exception:
            logger.error("Failed to generate configuration file", exc_info=True)
            sys.exit(1)

    elif action == "show":
        # Show current merged configuration
        try:
            print("Current AgentConnect Configuration:")
            print("=" * 50)

            # Convert to dict and pretty print
            config_dict = settings.model_dump_yaml_safe()

            # Try to use PyYAML for better formatting
            try:
                import yaml

                print(yaml.dump(config_dict, default_flow_style=False, sort_keys=True))
            except ImportError:
                # Fallback to JSON if PyYAML not available
                print(json.dumps(config_dict, indent=2, sort_keys=True))

        except Exception:
            logger.error("Failed to show configuration", exc_info=True)
            sys.exit(1)

    elif action == "validate":
        # Validate configuration file
        if not file_path:
            logger.error("File path is required for validate action")
            sys.exit(1)

        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error("Configuration file not found: %s", file_path)
                sys.exit(1)

            if validate_config_file(file_path_obj):
                print("✅ Configuration file %s is valid" % file_path)
            else:
                print("❌ Configuration file %s is invalid" % file_path)
                sys.exit(1)

        except Exception:
            logger.error("Failed to validate configuration file", exc_info=True)
            sys.exit(1)

    else:
        logger.error("Unknown config action: %s", action)
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    args = parse_args()

    # Set up logging first
    setup_logging(args.verbose)

    logger.debug("AgentConnect CLI starting")

    try:
        if args.version:
            print("AgentConnect v%s" % __version__)
            return

        if args.check_env:
            check_environment()
            return

        if args.command == "config":
            if args.config_action:
                file_path = getattr(args, "file", None)
                handle_config_command(args.config_action, file_path)
            else:
                print(
                    "No config action specified. Use 'agentconnect config --help' for available actions."
                )
            return

        if args.example:
            asyncio.run(run_example(args.example, args.verbose))
        elif args.demo:
            run_demo()
        else:
            print("No command specified. Use --help for available commands.")
    except KeyboardInterrupt:
        logger.info("Operation interrupted by user")
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception:
        logger.exception("Unexpected error")
        sys.exit(1)

    logger.debug("AgentConnect CLI completed successfully")


if __name__ == "__main__":
    main()
