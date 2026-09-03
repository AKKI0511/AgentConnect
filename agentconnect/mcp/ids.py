"""Message ids for MCP ``ask`` / ``tell``.

When the caller supplies ``idempotency_key``, UUID5 is taken over the
caller and that key so a retry collapses. When it does not, the id is
a fresh UUID. Two clients sending the same arguments therefore open two
Tickets.
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

        message_id_for_tool("ask", "researcher@content-squad")
        message_id_for_tool(
            "ask",
            "researcher@content-squad",
            idempotency_key="draft-1",
        )
    """
    if idempotency_key:
        material = f"{kind}|{caller_address}|{idempotency_key}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"agentconnect:{material}"))
    return str(uuid.uuid4())
