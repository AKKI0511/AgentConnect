"""Verify an Index registration identity.

v0.5 Index records use Ed25519 ``did:key``. Other DID methods are refused
until a consumer ships with verification rules.
"""

from __future__ import annotations

import logging

from agentconnect.core.identity import AgentIdentity

logger = logging.getLogger(__name__)


async def verify_agent_identity(identity: AgentIdentity) -> bool:
    """Return True when ``identity.did`` is the Ed25519 ``did:key`` for its public key.

    Args:
        identity: Keypair and DID presented with an Index registration.

    Returns:
        True when the DID is ``did:key`` and matches the public key.
    """
    if not identity.did.startswith("did:key:"):
        logger.warning("Index identity must be a did:key")
        return False
    try:
        return identity.matches_did()
    except Exception as exc:
        logger.error("Error verifying key-based DID: %s", exc)
        return False
