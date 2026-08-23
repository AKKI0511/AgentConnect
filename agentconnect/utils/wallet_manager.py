"""
Wallet persistence utilities for the AgentConnect framework.

This module provides utility functions to manage wallet data persistence
for individual agents within the AgentConnect framework. It specifically facilitates the storage
and retrieval of wallet state to enable consistent wallet access across agent restarts.

Note:
- The wallet directory is configured via YAML using ``payments.wallet_data_dir``.
- Legacy runtime setter utilities ``set_wallet_data_dir`` and ``set_default_data_dir`` are
  deprecated no-ops retained only for compatibility and are ignored at runtime.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agentconnect.config import settings as global_settings

# Set up logging
logger = logging.getLogger(__name__)

# Default path for wallet data storage (driven by configuration)
DEFAULT_DATA_DIR = Path(global_settings.payments.wallet_data_dir)


def set_default_data_dir(data_dir: Union[str, Path]) -> Path:
    """
    [DEPRECATED] Set the default directory for wallet data storage globally.

    NOTE: This function is now a no-op. Wallet directory is controlled by
    YAML configuration (payments.wallet_data_dir) and runtime setters are ignored.

    Args:
        data_dir: Path to the directory where wallet data will be stored
                 Can be a string or Path object (IGNORED)

    Returns:
        Path object pointing to the DEFAULT_DATA_DIR (from YAML config)
    """
    logger.warning(
        "set_default_data_dir() is deprecated and ignored. Wallet directory is controlled by YAML configuration (payments.wallet_data_dir). Using configured directory: %s",
        DEFAULT_DATA_DIR,
    )
    return DEFAULT_DATA_DIR


def set_wallet_data_dir(data_dir: Union[str, Path]) -> Path:
    """
    [DEPRECATED] Set a custom directory for wallet data storage.

    NOTE: This function is now a no-op. Wallet directory is controlled by
    YAML configuration (payments.wallet_data_dir) and runtime setters are ignored.

    Args:
        data_dir: Path to the directory where wallet data will be stored
                 Can be a string or Path object (IGNORED)

    Returns:
        Path object pointing to the DEFAULT_DATA_DIR (from YAML config)
    """
    logger.warning(
        "set_wallet_data_dir() is deprecated and ignored. Wallet directory is controlled by YAML configuration (payments.wallet_data_dir). Using configured directory: %s",
        DEFAULT_DATA_DIR,
    )
    return DEFAULT_DATA_DIR


def save_wallet_data(
    agent_id: str,
    wallet_data: Union[Any, str, Dict],
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
        wallet_data: The wallet data to save. Can be a cdp.WalletData object, a Dict representation, or a JSON string.
        data_dir: Optional custom directory for wallet data storage. If None, uses the DEFAULT_DATA_DIR.

    Raises:
        IOError: If the data directory can't be created or the file can't be written.
    """
    # Check if data_dir was provided
    if data_dir is not None:
        data_dir_path = Path(data_dir) if isinstance(data_dir, str) else data_dir
    else:
        data_dir_path = DEFAULT_DATA_DIR
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

    except Exception as e:
        logger.exception("Error saving wallet data for agent %s", agent_id)
        raise IOError(f"Error saving wallet data for agent {agent_id}: {e}")


def load_wallet_data(
    agent_id: str, data_dir: Optional[Union[str, Path]] = None
) -> Optional[str]:
    """
    Loads previously persisted wallet data for an agent.

    Args:
        agent_id: String identifier for the agent.
        data_dir: Optional custom directory for wallet data storage. If None, uses the DEFAULT_DATA_DIR.

    Returns:
        The loaded wallet data as a JSON string if the file exists, otherwise None.

    Raises:
        IOError: If the file exists but can't be read properly.
    """
    # Check if data_dir was provided
    if data_dir is not None:
        data_dir_path = Path(data_dir) if isinstance(data_dir, str) else data_dir
    else:
        data_dir_path = DEFAULT_DATA_DIR

    file_path = data_dir_path / f"{agent_id}_wallet.json"

    if not file_path.exists():
        return None

    try:
        with open(file_path, "r") as f:
            json_data = f.read()
        return json_data
    except FileNotFoundError:
        # Should not happen as we check existence above, but just in case
        return None
    except Exception:
        logger.exception("Error loading wallet data for agent %s", agent_id)
        # Log error but don't break agent initialization
        return None


def wallet_exists(agent_id: str, data_dir: Optional[Union[str, Path]] = None) -> bool:
    """
    Check if wallet data exists for a specific agent.

    Args:
        agent_id: String identifier for the agent.
        data_dir: Optional custom directory for wallet data storage. If None, uses the DEFAULT_DATA_DIR.

    Returns:
        True if wallet data exists, False otherwise.
    """
    # Check if data_dir was provided
    if data_dir is not None:
        data_dir_path = Path(data_dir) if isinstance(data_dir, str) else data_dir
    else:
        data_dir_path = DEFAULT_DATA_DIR

    file_path = data_dir_path / f"{agent_id}_wallet.json"

    exists = file_path.exists()
    return exists


def get_all_wallets(data_dir: Optional[Union[str, Path]] = None) -> List[Dict]:
    """
    Get information about all wallet files in the specified directory.

    Args:
        data_dir: Optional custom directory for wallet data storage. If None, uses the DEFAULT_DATA_DIR.

    Returns:
        List of dictionaries with wallet information (agent_id, file_path, etc.)
    """
    # Check if data_dir was provided
    if data_dir is not None:
        data_dir_path = Path(data_dir) if isinstance(data_dir, str) else data_dir
    else:
        data_dir_path = DEFAULT_DATA_DIR

    if not data_dir_path.exists():
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
            except Exception:
                logger.error(
                    "Error reading wallet data for %s", agent_id, exc_info=True
                )

            wallets.append(wallet_info)

        return wallets
    except Exception:
        logger.error("Error listing wallets in %s", data_dir_path, exc_info=True)
        return []


def delete_wallet_data(
    agent_id: str, data_dir: Optional[Union[str, Path]] = None
) -> bool:
    """
    Delete wallet data for a specific agent.

    Args:
        agent_id: String identifier for the agent.
        data_dir: Optional custom directory for wallet data storage. If None, uses the DEFAULT_DATA_DIR.

    Returns:
        True if wallet data was successfully deleted, False otherwise.
    """
    # Check if data_dir was provided
    if data_dir is not None:
        data_dir_path = Path(data_dir) if isinstance(data_dir, str) else data_dir
    else:
        data_dir_path = DEFAULT_DATA_DIR

    file_path = data_dir_path / f"{agent_id}_wallet.json"

    if not file_path.exists():
        return False

    try:
        file_path.unlink()
        return True
    except Exception:
        logger.error("Error deleting wallet data for agent %s", agent_id, exc_info=True)
        return False
