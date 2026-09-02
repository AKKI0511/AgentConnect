"""Collaboration envelope used by the unreleased gateway HTTP stack.

This is not the public Runtime Message. Gateway inbound and outbound HTTP
carry a signed envelope with ``sender_id`` / ``receiver_id``. The Team
Runtime Message lives in ``agentconnect.core.message``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from agentconnect.core.identity import AgentIdentity
from agentconnect.core.kinds import MessageKind

__all__ = ["CollaborationMessage", "ProtocolVersion"]


class ProtocolVersion(str, Enum):
    """Legacy version label on the collaboration envelope."""

    V1_0 = "1.0"
    V1_1 = "1.1"


@dataclass
class CollaborationMessage:
    """Signed collaboration envelope for gateway HTTP."""

    id: str
    sender_id: str
    receiver_id: str
    content: str
    kind: MessageKind
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    protocol_version: ProtocolVersion = ProtocolVersion.V1_0
    signature: Optional[str] = None

    @classmethod
    def create(
        cls,
        sender_id: str,
        receiver_id: str,
        content: str,
        sender_identity: AgentIdentity,
        kind: MessageKind = MessageKind.EVENT,
        metadata: Optional[Dict[str, Any]] = None,
        control: Optional[str] = None,
    ) -> "CollaborationMessage":
        """Create and sign an envelope."""
        metadata = dict(metadata or {})
        if control:
            metadata["control"] = control
        msg = cls(
            id=str(uuid4()),
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
            kind=kind,
            timestamp=datetime.now(),
            metadata=metadata,
            protocol_version=ProtocolVersion.V1_0,
        )
        msg.sign(sender_identity)
        return msg

    def sign(self, identity: AgentIdentity) -> None:
        """Sign the envelope with the sender's Ed25519 key."""
        self.signature = identity.sign_message(self._get_signable_content())

    def _get_signable_content(self) -> str:
        """Return the string the signature covers."""
        return (
            f"{self.id}:{self.sender_id}:{self.receiver_id}:"
            f"{self.content}:{self.timestamp.isoformat()}"
        )

    def to_wire_dict(self) -> dict[str, Any]:
        """JSON-ready envelope body."""
        kind = self.kind.value if isinstance(self.kind, MessageKind) else str(self.kind)
        version = (
            self.protocol_version.value
            if isinstance(self.protocol_version, ProtocolVersion)
            else str(self.protocol_version)
        )
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "content": self.content,
            "kind": kind,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata or {}),
            "protocol_version": version,
            "signature": self.signature,
        }

    @classmethod
    def from_wire_dict(cls, data: Dict[str, Any]) -> "CollaborationMessage":
        """Parse an envelope body posted to the inbox."""
        raw_kind = data.get("kind") or MessageKind.EVENT
        kind = (
            MessageKind(raw_kind) if not isinstance(raw_kind, MessageKind) else raw_kind
        )
        raw_ts = data.get("timestamp")
        if isinstance(raw_ts, datetime):
            timestamp = raw_ts
        elif isinstance(raw_ts, str):
            timestamp = datetime.fromisoformat(raw_ts)
        else:
            timestamp = datetime.now()
        raw_version = data.get("protocol_version") or ProtocolVersion.V1_0
        try:
            version = (
                raw_version
                if isinstance(raw_version, ProtocolVersion)
                else ProtocolVersion(raw_version)
            )
        except ValueError:
            version = ProtocolVersion.V1_0
        metadata = data.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        return cls(
            id=str(data.get("id") or uuid4()),
            sender_id=str(data.get("sender_id") or ""),
            receiver_id=str(data.get("receiver_id") or ""),
            content="" if data.get("content") is None else str(data.get("content")),
            kind=kind,
            timestamp=timestamp,
            metadata=dict(metadata),
            protocol_version=version,
            signature=data.get("signature"),
        )
