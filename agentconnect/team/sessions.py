"""Session persist ops shared by join acceptance and Runtime Session writes."""

from __future__ import annotations

from typing import Any

import agentconnect.team.auth as auth_mod
import agentconnect.team.expiry as expiry_mod
from agentconnect.team.codec import timestamp_score
from agentconnect.team.store.ops import (
    Delete,
    IndexAdd,
    IndexRemove,
    Put,
    SetAdd,
    SetRemove,
    StoreOp,
)


def member_sessions_key(name: str) -> str:
    """Return the store set of Session tokens for Membership ``name``."""
    return f"sessions:{name}"


def put_ops(session: dict[str, Any]) -> list[StoreOp]:
    """Writes that insert or replace one Session document and its indexes."""
    token = str(session["token"])
    name = str(session["membership_name"])
    ops: list[StoreOp] = [
        Put(f"session:{token}", session),
        Put(f"instance:{name}:{session['instance_id']}", token),
        SetAdd(member_sessions_key(name), token),
        IndexAdd(
            expiry_mod.SESSIONS,
            timestamp_score(session["expires_at"]),
            token,
        ),
    ]
    join_token = session.get("join_token")
    if isinstance(join_token, str) and join_token:
        ops.append(SetAdd(f"{auth_mod.TOKEN_SESSIONS_PREFIX}{join_token}", token))
    return ops


def drop_ops(session: dict[str, Any]) -> list[StoreOp]:
    """Writes that delete one Session document and its indexes."""
    token = str(session["token"])
    name = str(session["membership_name"])
    ops: list[StoreOp] = [
        Delete(f"session:{token}"),
        Delete(f"instance:{name}:{session['instance_id']}"),
        SetRemove(member_sessions_key(name), token),
        IndexRemove(expiry_mod.SESSIONS, token),
    ]
    join_token = session.get("join_token")
    if isinstance(join_token, str) and join_token:
        ops.append(SetRemove(f"{auth_mod.TOKEN_SESSIONS_PREFIX}{join_token}", token))
    return ops
