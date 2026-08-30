"""Message ids for MCP ``ask`` / ``tell`` idempotency.

When the caller supplies ``idempotency_key``, UUID5 is taken over the caller
and that key. When it does not, the MCP JSON-RPC request id is included so a
second distinct tool call with the same arguments opens a new Ticket, while a
retry of the same JSON-RPC request does not.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from agentconnect.team.codec import canonical_json


def message_id_for_tool(
    kind: str,
    caller_address: str,
    *,
    idempotency_key: Optional[str] = None,
    recipient: str = "",
    thread_id: Optional[str] = None,
    content: Any = None,
    request_id: Optional[str] = None,
) -> str:
    """Return a UUID5 Message id for one MCP ``ask`` or ``tell``.

    ``kind`` is ``ask`` or ``tell``. ``thread_id`` is the argument as the
    caller sent it. An omitted Thread is hashed as empty even if the server
    later mints one for the send.
    """
    if idempotency_key:
        material = f"{kind}|{caller_address}|{idempotency_key}"
    else:
        thread_part = thread_id or ""
        body = canonical_json(content)
        rpc = request_id if request_id else str(uuid.uuid4())
        material = f"{kind}|{caller_address}|{recipient}|{thread_part}|{body}|{rpc}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"agentconnect:{material}"))
