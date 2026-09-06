"""Store backends used only by the Team Runtime.

Runtime transitions call :meth:`~agentconnect.team.store.base.Store.apply`
so a Message, Ticket, Thread append, and Mailbox item commit together.
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
