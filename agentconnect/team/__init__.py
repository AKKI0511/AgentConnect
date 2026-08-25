"""Team runtime: routing, mailboxes, tickets, threads, and directory."""

from typing import Any

__all__ = ["CommunicationHub"]


def __getattr__(name: str) -> Any:
    if name == "CommunicationHub":
        from agentconnect.team.runtime import CommunicationHub

        return CommunicationHub
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
