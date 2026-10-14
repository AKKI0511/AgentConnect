"""Storage backends for a Team.

Pass `store="memory"` or a Redis URL to `Team`. Memory ends when the
process stops. Redis keeps memberships, mailboxes, open Tickets, and
Thread history for the next `start` of this Team. Use one Runtime for
a Team's stored state. Redis requires `agentconnect[redis]`.

A custom backend subclasses `Store`. `apply` commits every operation in
the call, or leaves the store unchanged.
"""

from agentconnect.team.store.base import Store, StoreRecord
from agentconnect.team.store.memory import MemoryStore
from agentconnect.team.store.ops import (
    ApplyResult,
    Cas,
    DecrementFloor,
    Delete,
    DeleteIfVersion,
    IncrementIfBelow,
    IndexAdd,
    IndexAddIfCardBelow,
    IndexRemove,
    Insert,
    Put,
    SetAdd,
    SetRemove,
    StoreOp,
)
from agentconnect.team.store.redis import RedisStore

__all__ = [
    "Store",
    "StoreRecord",
    "MemoryStore",
    "RedisStore",
    "ApplyResult",
    "StoreOp",
    "Insert",
    "Cas",
    "Put",
    "Delete",
    "DeleteIfVersion",
    "SetAdd",
    "SetRemove",
    "IndexAdd",
    "IndexRemove",
    "IndexAddIfCardBelow",
    "IncrementIfBelow",
    "DecrementFloor",
]
