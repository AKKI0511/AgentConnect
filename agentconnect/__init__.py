"""
AgentConnect is a runtime for Teams of independent AI agents.

Install the embedded core, then add extras for serving, Redis, CLI, MCP,
and model helpers:

    pip install agentconnect
    pip install 'agentconnect[serve]'
    pip install 'agentconnect[aiagent]'

    from agentconnect import AgentProfile, BaseAgent, Context, MailboxMessage, Skill, Team

    class Writer(BaseAgent):
        profile = AgentProfile(
            summary="Writes short drafts from notes.",
            skills=[
                Skill(
                    name="drafting",
                    description="Turn notes into a two-paragraph draft.",
                )
            ],
        )

        async def handle(self, msg: MailboxMessage, ctx: Context) -> str | None:
            if msg.kind != "request":
                return None
            return f"Draft complete for {msg.content!r}."

    team = await Team("content-squad").start()
    await Writer(name="writer").join(team)
"""

from importlib import metadata
from typing import TYPE_CHECKING, Any

try:
    __version__ = metadata.version(__package__)
except metadata.PackageNotFoundError:  # running from source without install
    __version__ = "0"

# Only the version is imported by default; names below load on attribute access.
__all__ = [
    "__version__",
    "AgentIdentity",
    "AgentProfile",
    "BaseAgent",
    "Context",
    "MailboxMessage",
    "Message",
    "SessionError",
    "Skill",
    "Team",
    "TeamError",
    "Ticket",
]

import logging

# Attach a NullHandler to the package logger to avoid "No handler" warnings
# and ensure the library never emits logs unless the application configures logging.
logging.getLogger("agentconnect").addHandler(logging.NullHandler())

if TYPE_CHECKING:
    from agentconnect.agent.base import BaseAgent
    from agentconnect.agent.context import Context
    from agentconnect.agent.errors import SessionError
    from agentconnect.core.identity import AgentIdentity
    from agentconnect.core.message import MailboxMessage, Message
    from agentconnect.core.profile import AgentProfile, Skill
    from agentconnect.core.ticket import Ticket
    from agentconnect.team.errors import TeamError
    from agentconnect.team.runtime import Team

_LAZY_EXPORTS = {
    "BaseAgent": ("agentconnect.agent.base", "BaseAgent"),
    "Context": ("agentconnect.agent.context", "Context"),
    "MailboxMessage": ("agentconnect.core.message", "MailboxMessage"),
    "Message": ("agentconnect.core.message", "Message"),
    "SessionError": ("agentconnect.agent.errors", "SessionError"),
    "Team": ("agentconnect.team.runtime", "Team"),
    "TeamError": ("agentconnect.team.errors", "TeamError"),
    "AgentIdentity": ("agentconnect.core.identity", "AgentIdentity"),
    "AgentProfile": ("agentconnect.core.profile", "AgentProfile"),
    "Skill": ("agentconnect.core.profile", "Skill"),
    "Ticket": ("agentconnect.core.ticket", "Ticket"),
}


def __getattr__(name: str) -> Any:
    """Load Team and Agent types without importing the whole package tree."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    from importlib import import_module

    return getattr(import_module(module_name), attr)


def __dir__() -> list[str]:
    return sorted(__all__)
