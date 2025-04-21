"""
Payment utility functions for AgentConnect.

This module provides helper functions for setting up payment capabilities in agents.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, Union, Tuple

from agentconnect.utils import wallet_manager

logger = logging.getLogger(__name__)


def verify_payment_environment() -> bool:
    """
    Verify that all required environment variables for payments are set.

    Returns:
        True if environment is properly configured, False otherwise
    """
    # Check required environment variables
    api_key_name = os.getenv("CDP_API_KEY_NAME")
    api_key_private = os.getenv("CDP_API_KEY_PRIVATE_KEY")

    if not api_key_name:
        logger.error("CDP_API_KEY_NAME environment variable is not set")
        return False

    if not api_key_private:
        logger.error("CDP_API_KEY_PRIVATE_KEY environment variable is not set")
        return False

    network_id = os.getenv("CDP_NETWORK_ID", "base-sepolia")
    logger.info(f"Payment environment verified: Using network {network_id}")
    return True


def validate_cdp_environment() -> Tuple[bool, str]:
    """
    Validate that the Coinbase Developer Platform environment is properly configured.

    Returns:
        Tuple of (valid: bool, message: str)
    """
    try:
        # Ensure .env file is loaded
        from dotenv import load_dotenv

        load_dotenv()

        # Verify environment variables
        if not verify_payment_environment():
            return False, "Required environment variables are missing"

        # Check if CDP packages are installed
        try:
            import cdp  # noqa: F401
        except ImportError:
            return (
                False,
                "CDP SDK not installed. Install it with: pip install cdp-sdk",
            )

        try:
            import coinbase_agentkit  # noqa: F401
        except ImportError:
            return (
                False,
                "AgentKit not installed. Install it with: pip install coinbase-agentkit",
            )

        try:
            import coinbase_agentkit_langchain  # noqa: F401
        except ImportError:
            return (
                False,
                "AgentKit LangChain integration not installed. Install it with: pip install coinbase-agentkit-langchain",
            )

        return True, "CDP environment is properly configured"
    except Exception as e:
        return False, f"Unexpected error validating CDP environment: {e}"


def get_wallet_metadata(
    agent_id: str, wallet_data_dir: Optional[Union[str, Path]] = None
) -> Optional[Dict[str, Any]]:
    """
    Get wallet metadata for an agent if it exists.

    Args:
        agent_id: The ID of the agent
        wallet_data_dir: Optional custom directory for wallet data storage

    Returns:
        Dictionary with wallet metadata if it exists, None otherwise
    """
    if not wallet_manager.wallet_exists(agent_id, wallet_data_dir):
        logger.debug(f"No wallet metadata found for agent {agent_id}")
        return None

    try:
        wallet_json = wallet_manager.load_wallet_data(agent_id, wallet_data_dir)
        if not wallet_json:
            logger.warning(f"Invalid wallet data found for agent {agent_id}")
            return None

        # Parse the JSON into a dictionary
        wallet_data = json.loads(wallet_json)

        # Extract relevant metadata
        metadata = {
            "wallet_id": wallet_data.get("wallet_id", "Unknown"),
            "network_id": wallet_data.get("network_id", "Unknown"),
            "has_seed": "seed" in wallet_data,
        }

        # Don't include sensitive data like seed
        logger.debug(f"Retrieved wallet metadata for agent {agent_id}")
        return metadata
    except Exception as e:
        logger.error(f"Error retrieving wallet metadata for agent {agent_id}: {e}")
        return None


def backup_wallet_data(
    agent_id: str,
    data_dir: Optional[Union[str, Path]] = None,
    backup_dir: Optional[Union[str, Path]] = None,
) -> Optional[str]:
    """
    Create a backup of wallet data for an agent.

    Args:
        agent_id: The ID of the agent
        data_dir: Optional custom directory for wallet data storage
        backup_dir: Optional directory for storing backups
                   If None, creates a backup directory under data_dir

    Returns:
        Path to the backup file if successful, None otherwise
    """
    if not wallet_manager.wallet_exists(agent_id, data_dir):
        logger.warning(f"No wallet data found for agent {agent_id} to backup")
        return None

    try:
        # Determine the source directory and file
        data_dir_path = Path(data_dir) if data_dir else wallet_manager.DEFAULT_DATA_DIR
        source_file = data_dir_path / f"{agent_id}_wallet.json"

        # Determine the backup directory
        if backup_dir:
            backup_dir_path = Path(backup_dir)
        else:
            backup_dir_path = data_dir_path / "backups"

        # Create backup directory if it doesn't exist
        backup_dir_path.mkdir(parents=True, exist_ok=True)

        # Create a timestamped filename for the backup
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup_file = backup_dir_path / f"{agent_id}_wallet_{timestamp}.json"

        # Read the original wallet data
        with open(source_file, "r") as f:
            wallet_data = f.read()

        # Write to the backup file
        with open(backup_file, "w") as f:
            f.write(wallet_data)

        logger.info(f"Backed up wallet data for agent {agent_id} to {backup_file}")
        return str(backup_file)
    except Exception as e:
        logger.error(f"Error backing up wallet data for agent {agent_id}: {e}")
        return None


def check_agent_payment_readiness(agent) -> Dict[str, Any]:
    """
    Check if an agent is ready for payments.

    Args:
        agent: The agent to check

    Returns:
        A dictionary with status information
    """
    status = {
        "payments_enabled": getattr(agent, "enable_payments", False),
        "wallet_provider_available": hasattr(agent, "wallet_provider")
        and agent.wallet_provider is not None,
        "agent_kit_available": hasattr(agent, "agent_kit")
        and agent.agent_kit is not None,
        "payment_address": (
            getattr(agent.metadata, "payment_address", None)
            if hasattr(agent, "metadata")
            else None
        ),
        "ready": False,
    }

    # Check overall readiness
    status["ready"] = (
        status["payments_enabled"]
        and status["wallet_provider_available"]
        and status["agent_kit_available"]
        and status["payment_address"] is not None
    )

    logger.info(f"Agent payment readiness check: {json.dumps(status)}")
    return status
