"""AgentConnect connects independent agents, each with its own harness, in one Team.

An Agent is an independent participant. A `Team` provides discovery,
messaging, and work tracking. Agents exchange Messages; a request asks
for work, and its `Ticket` tracks the result.

Subclass `BaseAgent` to connect an existing harness. Its `handle` method
receives a Message from another teammate and decides how to respond.
A returned value replies to a request; returning `None` declines a
request or finishes an event.

Examples:
    Assume `writer_agent` is an existing
    [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/quickstart/)
    agent configured to take text and produce a draft.

    ```python
    from agents import Runner

    from agentconnect import BaseAgent

    class Writer(BaseAgent):
        async def handle(self, message, ctx):
            if message.kind != "request":
                return None
            result = await Runner.run(writer_agent, input=message.content)
            return result.final_output
    ```

    In your async application, `team` is already started. `researcher`
    and `reviewer` are existing adapters for independent agents with
    their own harnesses. Join all three to the same Team, then ask the
    writer for a draft.

    ```python
    writer = Writer(name="writer")
    await writer.join(team)
    await researcher.join(team)
    await reviewer.join(team)

    ticket = await researcher.ask(
        "writer",
        "Draft a release note from these findings: search is faster, "
        "and request deadlines now appear in the activity log.",
    )
    if ticket.state == "completed":
        print(ticket.content)
    ```

Call `leave` on each adapter when its connection is no longer needed.
To let a model initiate collaboration, separately attach `team_tools`
to its harness or connect the harness through MCP.
"""

from typing import TYPE_CHECKING

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
    __version__: str
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

_version: str | None = None


def __getattr__(name: str) -> object:
    """Load Team and Agent types without importing the whole package tree."""
    global _version
    if name == "__version__":
        if _version is None:
            from importlib import metadata

            try:
                _version = metadata.version(__package__)
            except metadata.PackageNotFoundError:
                _version = "0"
        return _version
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    from importlib import import_module

    return getattr(import_module(module_name), attr)


def __dir__() -> list[str]:
    return sorted(__all__)
