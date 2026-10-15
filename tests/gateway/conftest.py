"""Duck-typed collaboration facade for inbox tests.

Gateway inbound still talks to ingest_remote_message and a response tracker.
Those operations move to the Team Runtime in a later milestone. Tests here
cover inbox HTTP rules, not Agent delivery.
"""

from __future__ import annotations

from typing import Any, Optional

from agentconnect.transport.envelope import CollaborationMessage as Message


class Tracker:
    def __init__(self) -> None:
        self.status = "pending"
        self.message: Optional[Message] = None

    async def check(self, request_id: str) -> tuple[str, Optional[Message]]:
        return self.status, self.message


class InboxFacade:
    def __init__(self, registry: Any) -> None:
        self.registry = registry
        self.response_tracker = Tracker()
        self.ingested: list[Message] = []

    async def ingest_remote_message(self, message: Message) -> str:
        request_id = (message.metadata or {}).get("request_id")
        if not request_id:
            raise ValueError("Missing request_id")
        self.ingested.append(message)
        return request_id

    async def stop(self) -> None:
        return None

    async def register_agent(self, agent: Any) -> bool:
        return True
