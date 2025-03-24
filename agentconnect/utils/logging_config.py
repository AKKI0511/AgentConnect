"""
Logging configuration for the AgentConnect framework.

This module provides a consistent logging setup across the framework,
including colored output, module-specific log levels, and integration
with LangGraph components.
"""

# Standard library imports
import logging
import sys
from enum import Enum
from typing import Dict, Optional

# Third-party imports
import colorama
from colorama import Fore, Style

# Initialize colorama for cross-platform color support
colorama.init()


class LogLevel(Enum):
    """
    Enum for log levels.

    Attributes:
        DEBUG: Debug log level
        INFO: Info log level
        WARNING: Warning log level
        ERROR: Error log level
    """

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter with colors for log messages.

    This formatter adds colors to log level names and logger names
    to improve readability in terminal output.

    Attributes:
        COLORS: Dictionary mapping log level names to color codes
    """

    COLORS = {
        "DEBUG": Fore.CYAN,
        "INFO": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "CRITICAL": Fore.RED + Style.BRIGHT,
    }

    def format(self, record):
        """
        Format a log record with colors.

        Args:
            record: Log record to format

        Returns:
            Formatted log message with colors
        """
        # Add color to the level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{Style.RESET_ALL}"

        # Add color to the logger name
        record.name = f"{Fore.BLUE}{record.name}{Style.RESET_ALL}"

        return super().format(record)


def setup_logging(
    level: LogLevel = LogLevel.INFO, module_levels: Optional[Dict[str, LogLevel]] = None
) -> None:
    """
    Configure logging with colors and per-module settings.

    Args:
        level: Default log level for all modules
        module_levels: Dict of module names and their specific log levels
    """
    # Convert module_levels to use actual log level values
    module_level_values = {}
    if module_levels:
        for module, log_level in module_levels.items():
            module_level_values[module] = log_level.value

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level.value)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level.value)

    # Create formatter
    formatter = ColoredFormatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set module-specific log levels
    if module_level_values:
        for module, log_level in module_level_values.items():
            logging.getLogger(module).setLevel(log_level)


def disable_all_logging() -> None:
    """
    Disable all logging output.

    This is useful for examples and tests where logging output is not needed.
    """
    logging.getLogger().setLevel(logging.CRITICAL + 1)


def get_module_levels_for_development() -> Dict[str, LogLevel]:
    """
    Get recommended log levels for development.

    Returns:
        Dictionary of module names and their recommended log levels for development
    """
    return {
        # AgentConnect modules
        "agentconnect": LogLevel.DEBUG,
        "agentconnect.agents": LogLevel.DEBUG,
        "agentconnect.core": LogLevel.INFO,
        "agentconnect.providers": LogLevel.INFO,
        "agentconnect.utils": LogLevel.DEBUG,
        # Third-party libraries
        "langchain": LogLevel.WARNING,
        "langchain_core": LogLevel.WARNING,
        "langchain_community": LogLevel.WARNING,
        "langgraph": LogLevel.INFO,
        # Other libraries
        "httpx": LogLevel.WARNING,
        "urllib3": LogLevel.WARNING,
    }


def setup_langgraph_logging(level: LogLevel = LogLevel.INFO) -> None:
    """
    Configure logging specifically for LangGraph components.

    Args:
        level: Log level for LangGraph components
    """
    # Set up basic logging
    setup_logging(
        level=LogLevel.WARNING,  # Default to WARNING for most modules
        module_levels={
            "langgraph": level,
            "langgraph.graph": level,
            "langgraph.graph.graph": level,
            "langgraph.pregel": level,
        },
    )

    # Suppress noisy warnings from httpx and urllib3
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
