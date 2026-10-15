from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from agentconnect.core.base import JsonObject

from pydantic import BaseModel, ConfigDict


class InboxResponse(BaseModel):
    """Wire response envelope for HTTP inbox endpoints.

    Fields:
        status: One of 'completed', 'pending', 'accepted', 'not_found'
        response: Optional response message as a wire dict
        request_id: Correlation id for asynchronous processing
    """

    model_config = ConfigDict(extra="ignore")
    status: Literal["completed", "pending", "accepted", "not_found"]
    response: Optional[JsonObject] = None
    request_id: Optional[str] = None


@dataclass
class HTTPRouteOptions:
    """HTTP route options for inbox servers.

    These are server-side knobs and not used by the outbound transport.
    """

    require_auth: bool = False
    auth_header_name: str = "Authorization"
    auth_token_env_var: str = "AGENTCONNECT_INBOX_BEARER_TOKEN"


@dataclass
class TransportTarget:
    """Target agent info for outbound communication.

    Attributes:
        agent_id: Receiver agent identifier
        url: Base URL of the remote agent
        inbox_path: Path to the inbox endpoint (e.g., '/agentconnect/collaboration')
        public_key: Optional receiver public key hint
    """

    agent_id: str
    url: str
    inbox_path: str
    public_key: Optional[str] = None


# Reserved metadata keys used internally by the hub. Routing/auth MUST NOT be stored here.
RESERVED_METADATA_KEYS = {
    "verified_by",
    "response_to",
    "request_id",
    "original_sender",
    "collaboration_chain",
}


def sanitize_metadata(
    metadata: JsonObject,
    drop_reserved: bool = True,
    size_limit: Optional[int] = None,
) -> JsonObject:
    """Sanitize metadata to remove reserved keys and enforce size limit.

    Args:
        metadata: Metadata dict to sanitize
        drop_reserved: Whether to remove reserved keys used internally by the hub
        size_limit: Optional max encoded size in bytes for the resulting metadata

    Returns:
        A sanitized metadata dict suitable for inclusion in messages
    """
    metadata = dict(metadata or {})
    if drop_reserved:
        for k in list(metadata.keys()):
            if k in RESERVED_METADATA_KEYS:
                metadata.pop(k, None)
    if size_limit is not None:
        import json

        encoded = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode()
        if len(encoded) > size_limit:
            # Truncate by removing keys until within limit (best effort)
            for k in list(metadata.keys()):
                metadata.pop(k)
                encoded = json.dumps(
                    metadata, sort_keys=True, separators=(",", ":")
                ).encode()
                if len(encoded) <= size_limit:
                    break
    return metadata
