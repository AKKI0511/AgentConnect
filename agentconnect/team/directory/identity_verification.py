"""
Agent identity verification utilities for the AgentConnect framework.

This module provides functions for verifying agent identities using
decentralized identifiers (DIDs) and cryptographic signatures.
"""

# Standard library imports
import logging

# Absolute imports from agentconnect package
from agentconnect.core.types import (
    AgentIdentity,
)

# Set up logging
logger = logging.getLogger(__name__)


async def verify_agent_identity(identity: AgentIdentity) -> bool:
    """
    Verify agent's DID and public key.

    Args:
        identity: Agent's decentralized identity

    Returns:
        True if the identity is verified, False otherwise
    """
    try:
        # Start verification (avoid logging DID material)
        method = "unknown"
        try:
            if identity.did.startswith("did:"):
                parts = identity.did.split(":")
                method = parts[1] if len(parts) > 1 else "unknown"
        except Exception:
            method = "unknown"

        logger.debug("Verifying agent identity via method=%s", method)

        # Verify DID format
        if not identity.did.startswith(("did:ethr:", "did:key:")):
            logger.warning("Invalid DID format")
            return False

        # Verify DID resolution
        if identity.did.startswith("did:ethr:"):
            return await verify_ethereum_did(identity)
        else:  # did:key
            return await verify_key_did(identity)

    except Exception as e:
        logger.error("Error verifying agent identity: %s", e)
        return False


async def verify_ethereum_did(identity: AgentIdentity) -> bool:
    """
    Verify Ethereum-based DID.

    Args:
        identity: Agent's Ethereum-based decentralized identity

    Returns:
        True if the identity is verified, False otherwise
    """
    try:
        eth_address = identity.did.split(":")[-1]

        if not eth_address.startswith("0x") or len(eth_address) != 42:
            logger.debug("Ethereum DID validation failed: invalid_format")
            return False

        # TODO: Implement full Ethereum DID verification
        return True

    except Exception as e:
        logger.error("Error verifying Ethereum DID: %s", e)
        return False


async def verify_key_did(identity: AgentIdentity) -> bool:
    """
    Verify key-based DID.

    Args:
        identity: Agent's key-based decentralized identity

    Returns:
        True if the identity is verified, False otherwise
    """
    try:
        # TODO: Implement full key-based DID verification
        return True
    except Exception as e:
        logger.error("Error verifying key-based DID: %s", e)
        return False
