"""Team runtime: routing, mailboxes, tickets, threads, and directory.

The public type is :class:`~agentconnect.team.runtime.Team`. Start a Team,
join as a member, then send and pull work. The Runtime never holds Agent
objects.
"""

from agentconnect.team.errors import TeamError
from agentconnect.team.runtime import Team
from agentconnect.team.store import MemoryStore, RedisStore, Store

__all__ = ["Team", "TeamError", "Store", "MemoryStore", "RedisStore"]
