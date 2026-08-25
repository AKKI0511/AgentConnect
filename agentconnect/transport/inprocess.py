"""In-process delivery endpoint.

The Runtime talks to this protocol, never to ``BaseAgent``. That keeps
``team/`` from importing ``agent/``. Mailbox pull replaces this in a later
milestone.
"""

from __future__ import annotations

from typing import Any, Dict, List, Protocol

from agentconnect.core.identity import AgentIdentity
from agentconnect.core.message import Message
from agentconnect.core.profile import AgentProfile
from agentconnect.core.types import InteractionMode


class InProcessAgent(Protocol):
    """Attributes the in-process Runtime uses to deliver a Message."""

    agent_id: str
    identity: AgentIdentity
    profile: AgentProfile
    interaction_modes: List[InteractionMode]
    hub: Any
    registry: Any
    active_conversations: Dict[str, Any]

    async def receive_message(self, message: Message) -> None:
        """Queue an inbound Message."""

    async def verify_identity(self) -> bool:
        """Return True when the Agent identity is verified."""

    def end_conversation(self, agent_id: str) -> None:
        """Drop conversation state with another Agent."""
