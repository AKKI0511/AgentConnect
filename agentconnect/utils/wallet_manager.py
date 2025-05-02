"""
Wallet persistence utilities for the AgentConnect framework.

This module provides utility functions to manage wallet data persistence
for individual agents within the AgentConnect framework. It specifically facilitates the storage
and retrieval of wallet state to enable consistent wallet access across agent restarts.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

# Import dependencies directly since they're required
from cdp import WalletData

# Set up logging
logger = logging.getLogger(__name__)

# Default path for wallet data storage
DEFAULT_DATA_DIR = Path("data/agent_wallets")


def set_default_data_dir(data_dir: Union[str, Path]) -> Path:
    """
    Set the default directory for wallet data storage globally.

    Args:
        data_dir: Path to the directory where wallet data will be stored
                 Can be a string or Path object

    Returns:
        Path object pointing to the created directory

    Raises:
        IOError: If the directory can't be created
    """
    global DEFAULT_DATA_DIR
    try:
        # Convert to Path if it's a string
        data_dir_path = Path(data_dir) if isinstance(data_dir, str) else data_dir

        # Create directory if it doesn't exist
        data_dir_path.mkdir(parents=True, exist_ok=True)

        # Update the global default
        DEFAULT_DATA_DIR = data_dir_path

        logger.info(f"Set default wallet data directory to: {data_dir_path}")
        return data_dir_path
    except Exception as e:
        error_msg = f"Error setting default wallet data directory: {e}"
        logger.error(error_msg)
        raise IOError(error_msg)


def set_wallet_data_dir(data_dir: Union[str, Path]) -> Path:
    """
    Set a custom directory for wallet data storage.

    Args:
        data_dir: Path to the directory where wallet data will be stored
                 Can be a string or Path object

    Returns:
        Path object pointing to the created directory

    Raises:
        IOError: If the directory can't be created
    """
    try:
        # Convert to Path if it's a string
        data_dir_path = Path(data_dir) if isinstance(data_dir, str) else data_dir

        # Create directory if it doesn't exist
        data_dir_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Set wallet data directory to: {data_dir_path}")
        return data_dir_path
    except Exception as e:
        error_msg = f"Error setting wallet data directory: {e}"
        logger.error(error_msg)
        raise IOError(error_msg)


def save_wallet_data(
    agent_id: str,
    wallet_data: Union[WalletData, str, Dict],
    data_dir: Optional[Union[str, Path]] = None,
) -> None:
    """
    Persists the exported wallet data for an agent, allowing the agent to retain
    access to the same wallet across restarts.

    SECURITY NOTE: This default implementation stores wallet data unencrypted on disk,
    which is suitable for testing/demo but NOT secure for production environments
    holding real assets. Real-world applications should encrypt this data.

    Args:
        agent_id: String identifier for the agent.
        wallet_data: The wallet data to save. Can be a cdp.WalletData object,
                     a Dict representation, or a JSON string.
        data_dir: Optional custom directory for wallet data storage.
                 If None, uses the DEFAULT_DATA_DIR.

    Raises:
        IOError: If the data directory can't be created or the file can't be written.
    """
    # Determine the data directory to use
    data_dir_path = set_wallet_data_dir(data_dir) if data_dir else DEFAULT_DATA_DIR
    data_dir_path.mkdir(parents=True, exist_ok=True)

    # File path for this agent's wallet data
    file_path = data_dir_path / f"{agent_id}_wallet.json"

    try:
        # Convert wallet_data to JSON string based on its type
        if isinstance(wallet_data, str):
            # Assume it's valid JSON string
            json_data = wallet_data
        elif isinstance(wallet_data, Dict):
            # Convert dict to JSON string
            json_data = json.dumps(wallet_data)
        else:
            # Assume it's a WalletData object and serialize it
            json_data = json.dumps(wallet_data.to_dict())

        # Write to file
        with open(file_path, "w") as f:
            f.write(json_data)

        logger.debug(f"Saved wallet data for agent {agent_id} to {file_path}")

    except Exception as e:
        error_msg = f"Error saving wallet data for agent {agent_id}: {e}"
        logger.error(error_msg)
        raise IOError(error_msg)


def load_wallet_data(
    agent_id: str, data_dir: Optional[Union[str, Path]] = None
) -> Optional[str]:
    """
    Loads previously persisted wallet data for an agent.

    Args:
        agent_id: String identifier for the agent.
        data_dir: Optional custom directory for wallet data storage.
                 If None, uses the DEFAULT_DATA_DIR.

    Returns:
        The loaded wallet data as a JSON string if the file exists, otherwise None.

    Raises:
        IOError: If the file exists but can't be read properly.
    """
    # Determine the data directory to use
    data_dir_path = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    file_path = data_dir_path / f"{agent_id}_wallet.json"

    if not file_path.exists():
        logger.debug(f"No saved wallet data found for agent {agent_id} at {file_path}")
        return None

    try:
        with open(file_path, "r") as f:
            json_data = f.read()
        logger.debug(f"Loaded wallet data for agent {agent_id} from {file_path}")
        return json_data
    except FileNotFoundError:
        # Should not happen as we check existence above, but just in case
        logger.debug(f"No saved wallet data found for agent {agent_id}")
        return None
    except Exception as e:
        error_msg = f"Error loading wallet data for agent {agent_id}: {e}"
        logger.error(error_msg)
        # Log error but don't break agent initialization
        return None


def wallet_exists(agent_id: str, data_dir: Optional[Union[str, Path]] = None) -> bool:
    """
    Check if wallet data exists for a specific agent.

    Args:
        agent_id: String identifier for the agent.
        data_dir: Optional custom directory for wallet data storage.
                 If None, uses the DEFAULT_DATA_DIR.

    Returns:
        True if wallet data exists, False otherwise.
    """
    # Determine the data directory to use
    data_dir_path = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    file_path = data_dir_path / f"{agent_id}_wallet.json"

    exists = file_path.exists()
    if exists:
        logger.debug(f"Wallet data exists for agent {agent_id} at {file_path}")
    else:
        logger.debug(f"No wallet data found for agent {agent_id} at {file_path}")

    return exists


def get_all_wallets(data_dir: Optional[Union[str, Path]] = None) -> List[Dict]:
    """
    Get information about all wallet files in the specified directory.

    Args:
        data_dir: Optional custom directory for wallet data storage.
                 If None, uses the DEFAULT_DATA_DIR.

    Returns:
        List of dictionaries with wallet information (agent_id, file_path, etc.)
    """
    # Determine the data directory to use
    data_dir_path = Path(data_dir) if data_dir else DEFAULT_DATA_DIR

    if not data_dir_path.exists():
        logger.debug(f"Wallet data directory {data_dir_path} does not exist")
        return []

    wallets = []
    try:
        # Find all wallet JSON files
        for file_path in data_dir_path.glob("*_wallet.json"):
            # Extract agent_id from filename
            agent_id = file_path.stem.replace("_wallet", "")

            wallet_info = {
                "agent_id": agent_id,
                "file_path": str(file_path),
                "last_modified": file_path.stat().st_mtime,
            }

            # Try to read basic info without exposing sensitive data
            try:
                with open(file_path, "r") as f:
                    data = json.loads(f.read())

                if "wallet_id" in data:
                    wallet_info["wallet_id"] = data["wallet_id"]
                if "network_id" in data:
                    wallet_info["network_id"] = data["network_id"]
            except Exception as e:
                logger.error(f"Error reading wallet data for {agent_id}: {e}")

            wallets.append(wallet_info)

        logger.debug(f"Found {len(wallets)} wallet files in {data_dir_path}")
        return wallets
    except Exception as e:
        logger.error(f"Error listing wallets in {data_dir_path}: {e}")
        return []


def delete_wallet_data(
    agent_id: str, data_dir: Optional[Union[str, Path]] = None
) -> bool:
    """
    Delete wallet data for a specific agent.

    Args:
        agent_id: String identifier for the agent.
        data_dir: Optional custom directory for wallet data storage.
                 If None, uses the DEFAULT_DATA_DIR.

    Returns:
        True if wallet data was successfully deleted, False otherwise.
    """
    # Determine the data directory to use
    data_dir_path = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    file_path = data_dir_path / f"{agent_id}_wallet.json"

    if not file_path.exists():
        logger.debug(f"No wallet data to delete for agent {agent_id}")
        return False

    try:
        file_path.unlink()
        logger.info(f"Deleted wallet data for agent {agent_id} from {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error deleting wallet data for agent {agent_id}: {e}")
        return False
