import logging
import sys
from typing import Optional
from enum import Enum
import colorama
from colorama import Fore, Style

# Initialize colorama for cross-platform color support
colorama.init()


class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors"""

    COLORS = {
        "DEBUG": Fore.CYAN,
        "INFO": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "CRITICAL": Fore.RED + Style.BRIGHT,
    }

    def format(self, record):
        # Add color to the level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{Style.RESET_ALL}"

        # Add color to the logger name
        record.name = f"{Fore.BLUE}{record.name}{Style.RESET_ALL}"

        return super().format(record)


def setup_logging(
    level: LogLevel = LogLevel.INFO, module_levels: Optional[dict] = None
) -> None:
    """
    Configure logging with colors and per-module settings

    Args:
        level: Default log level for all modules
        module_levels: Dict of module names and their specific log levels
    """
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)

    # Create colored formatter
    formatter = ColoredFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level.value)

    # Remove existing handlers
    root_logger.handlers = []
    root_logger.addHandler(console_handler)

    # Set specific levels for modules if provided
    if module_levels:
        for module, level in module_levels.items():
            logging.getLogger(module).setLevel(level.value)
