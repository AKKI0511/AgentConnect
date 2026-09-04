"""Team runtime: routing, mailboxes, tickets, threads, and directory.

The public type is :class:`~agentconnect.team.runtime.Team`. Start a Team,
join as a member, then talk through ``BaseAgent``. Token-taking methods on
``Team`` are the Session transport.
"""

from agentconnect.team.errors import TeamError
from agentconnect.team.http import create_runtime_app
from agentconnect.team.runtime import Team
from agentconnect.team.auth import JoinToken
from agentconnect.team.store import MemoryStore, RedisStore, Store, StoreRecord

__all__ = [
    "Team",
    "TeamError",
    "JoinToken",
    "Store",
    "StoreRecord",
    "MemoryStore",
    "RedisStore",
    "create_runtime_app",
]
