"""
File-related utility functions for the Telegram agent.

This module contains helper functions for working with files in the Telegram agent,
including loading and saving group IDs and managing download directories.
"""

import os
import logging
from typing import Set

logger = logging.getLogger(__name__)


def ensure_download_directory(base_path: str) -> str:
    """
    Ensure the download directory exists and return its path.

    Args:
        base_path: Base path for downloads directory

    Returns:
        Path to downloads directory
    """
    downloads_dir = os.path.join(
        os.path.dirname(os.path.abspath(base_path)), "downloads"
    )
    if not os.path.exists(downloads_dir):
        os.makedirs(downloads_dir)

    return downloads_dir


def load_group_ids(groups_file: str) -> Set[int]:
    """
    Load group IDs from file on startup.

    Args:
        groups_file: Path to the file storing group IDs

    Returns:
        Set of group IDs
    """
    try:
        if not os.path.exists(groups_file):
            os.makedirs(os.path.dirname(os.path.abspath(groups_file)), exist_ok=True)
            with open(groups_file, "w") as file:
                file.write("")

        with open(groups_file, "r") as file:
            # Read each line, strip whitespace, and convert to int
            group_ids = {int(line.strip()) for line in file if line.strip()}

        return group_ids
    except FileNotFoundError:
        return set()
    except ValueError:
        logger.error("Error parsing group IDs from groups.txt. File may be corrupted.")
        return set()


def save_group_ids(groups_file: str, group_ids: Set[int]) -> bool:
    """
    Save group IDs to file.

    Args:
        groups_file: Path to the file storing group IDs
        group_ids: Set of group IDs to save

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(groups_file, "w") as file:
            for gid in group_ids:
                file.write(f"{gid}\n")
        return True
    except IOError as e:
        logger.error(f"Error saving group IDs to {groups_file}: {e}")
        return False
