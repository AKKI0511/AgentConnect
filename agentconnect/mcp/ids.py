"""Message and Thread ids for MCP ``ask`` / ``tell``.

When the caller supplies ``idempotency_key``, UUID5 is taken over the
caller and that key so a retry collapses. An omitted Thread on a keyed
``ask`` uses a second UUID5 so the generated conversation id is stable
across retries. When the key is omitted, ids are fresh UUIDs. Two
clients sending the same arguments therefore open two Tickets.

    message_id_for_tool("ask", "researcher@content-squad")
    message_id_for_tool(
        "ask",
        "researcher@content-squad",
        idempotency_key="draft-1",
    )
    thread_id_for_tool(
        "ask",
        "researcher@content-squad",
        idempotency_key="draft-1",
    )
"""

from __future__ import annotations

import uuid
from typing import Optional


def message_id_for_tool(
    kind: str,
    caller_address: str,
    *,
    idempotency_key: Optional[str] = None,
) -> str:
    """Return a Message id for one MCP ``ask`` or ``tell``.

    ``kind`` is ``ask`` or ``tell``.
    """
    if idempotency_key:
        material = f"{kind}|{caller_address}|{idempotency_key}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"agentconnect:{material}"))
    return str(uuid.uuid4())


def thread_id_for_tool(
    kind: str,
    caller_address: str,
    *,
    idempotency_key: str,
) -> str:
    """Return a stable Thread id for a keyed ``ask`` that omitted ``thread_id``."""
    material = f"{kind}-thread|{caller_address}|{idempotency_key}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"agentconnect:{material}"))
