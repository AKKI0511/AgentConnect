import logging
import os
import sys
import json
from typing import Any, Dict
from logging.handlers import RotatingFileHandler

# Constants
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5

# Default logging configuration
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_LOG_DIR = "logs"


def setup_logger(name: str = None, level: str = None) -> logging.Logger:
    """Set up and configure logger

    Args:
        name (str, optional): Logger name. Defaults to root logger.
        level (str, optional): Log level. Defaults to INFO.

    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), DEFAULT_LOG_DIR)
    os.makedirs(log_dir, exist_ok=True)

    # Get or create logger
    logger = logging.getLogger(name)

    # Return existing logger if already configured
    if logger.hasHandlers():
        return logger

    # Set log level - ensure it defaults to INFO if invalid
    try:
        log_level = getattr(logging, (level or DEFAULT_LOG_LEVEL).upper())
    except AttributeError:
        log_level = logging.INFO

    logger.setLevel(log_level)

    # Create formatters and handlers
    formatter = logging.Formatter(DEFAULT_LOG_FORMAT)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    if name:
        log_file = os.path.join(log_dir, f"{name.lower().replace('.', '_')}.log")
        file_handler = RotatingFileHandler(
            log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to avoid double logging
    logger.propagate = False

    return logger


class WebSocketLogger:
    """Specialized logger for WebSocket events"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def log_connection(self, client_id: str, details: Dict[str, Any] = None):
        """Log WebSocket connection"""
        self.logger.info(
            "WebSocket connection established - "
            f"Client: {client_id} - "
            f"Details: {json.dumps(details or {})}"
        )

    def log_disconnection(self, client_id: str, code: int = None, reason: str = None):
        """Log WebSocket disconnection"""
        self.logger.info(
            "WebSocket connection closed - "
            f"Client: {client_id} - "
            f"Code: {code} - "
            f"Reason: {reason or 'No reason provided'}"
        )

    def log_message(self, client_id: str, message_type: str, content: Any):
        """Log WebSocket message"""
        self.logger.debug(
            "WebSocket message - "
            f"Client: {client_id} - "
            f"Type: {message_type} - "
            f"Content: {json.dumps(content)}"
        )

    def log_error(self, client_id: str, error: Exception, context: str = None):
        """Log WebSocket error"""
        self.logger.error(
            "WebSocket error - "
            f"Client: {client_id} - "
            f"Error: {str(error)} - "
            f"Context: {context or 'No context'}"
        )

    def log_auth(self, client_id: str, success: bool, details: str = None):
        """Log WebSocket authentication"""
        level = logging.INFO if success else logging.WARNING
        self.logger.log(
            level,
            "WebSocket authentication - "
            f"Client: {client_id} - "
            f"Status: {'Success' if success else 'Failed'} - "
            f"Details: {details or 'No details'}",
        )


def get_logger(name: str = None) -> logging.Logger:
    """Get or create a logger with the given name

    Args:
        name (str, optional): Logger name. Defaults to root logger.

    Returns:
        logging.Logger: Logger instance
    """
    return setup_logger(name)


# Create WebSocket logger instance
ws_logger = WebSocketLogger(get_logger("websocket"))


def log_request(
    logger: logging.Logger, method: str, path: str, status_code: int, duration: float
):
    """
    Log an API request with its details.

    Args:
        logger: The logger instance to use
        method: HTTP method (GET, POST, etc.)
        path: Request path
        status_code: HTTP status code
        duration: Request duration in seconds
    """
    logger.info(
        f"Request: {method} {path} - Status: {status_code} - Duration: {duration:.3f}s"
    )


def log_websocket(
    logger: logging.Logger, event_type: str, client_id: str, details: str = None
):
    """
    Log WebSocket events.

    Args:
        logger: The logger instance to use
        event_type: Type of WebSocket event (connect, disconnect, message)
        client_id: ID of the client
        details: Additional event details (optional)
    """
    message = f"WebSocket {event_type} - Client: {client_id}"
    if details:
        message += f" - Details: {details}"
    logger.info(message)
