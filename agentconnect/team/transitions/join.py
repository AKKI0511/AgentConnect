"""Atomic join: consume credentials and persist Membership plus Session together."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import agentconnect.team.auth as auth_mod
import agentconnect.team.sessions as sessions_mod
from agentconnect.team.auth import JOIN_UNAUTH_MESSAGE
from agentconnect.team.store.base import Store
from agentconnect.team.store.ops import Cas, Insert, SetAdd, StoreOp


@dataclass
class JoinPlan:
    """Inputs for one join acceptance transition."""

    member: dict[str, Any]
    created: bool
    member_version: Optional[int]
    session: dict[str, Any]
    old_session: Optional[dict[str, Any]]
    challenge_nonce: Optional[str]
    challenge_version: Optional[int]
    token_record: Optional[dict[str, Any]]
    token_version: Optional[int]


@dataclass
class JoinAccepted:
    """Committed join. Directory and process maps update after this returns."""

    member: dict[str, Any]
    session: dict[str, Any]
    created: bool
    old_session: Optional[dict[str, Any]]


class JoinConflict(Exception):
    """Join acceptance hit a named Runtime error."""

    def __init__(self, code: str, message: str) -> None:
        """Set the public ``code`` and ``message`` for this failure."""
        super().__init__(message)
        self.code = code
        self.message = message


def _plan_ops(plan: JoinPlan) -> list[StoreOp]:
    name = str(plan.member["name"])
    did = str(plan.member["agent_did"])
    membership_id = str(plan.member["membership_id"])
    ops: list[StoreOp] = []
    if plan.created:
        ops.extend(
            [
                Insert(f"member:{name}", plan.member),
                Insert(f"did:{did}", name),
                SetAdd("members", name),
            ]
        )
    else:
        version = plan.member_version
        if version is None:
            raise JoinConflict("internal", "reconnect is missing a Membership version")
        ops.append(Cas(f"member:{name}", version, plan.member))
    if plan.challenge_nonce is not None and plan.challenge_version is not None:
        ops.extend(
            auth_mod.consume_challenge_ops(plan.challenge_nonce, plan.challenge_version)
        )
    if plan.token_record is not None and plan.token_version is not None:
        ops.extend(
            auth_mod.token_join_ops(
                plan.token_record,
                plan.token_version,
                name=name,
                agent_did=did,
                membership_id=membership_id,
            )
        )
    if plan.old_session is not None:
        ops.extend(sessions_mod.drop_ops(plan.old_session))
    ops.extend(sessions_mod.put_ops(plan.session))
    return ops


async def commit_join(store: Store, plan: JoinPlan) -> JoinAccepted:
    """Commit join acceptance or raise ``JoinConflict``.

    Credential consumption, Membership insert or reuse, and Session insert
    commit together. A conflict or crash leaves either the full successful
    join or no join.
    """
    while True:
        ops = _plan_ops(plan)
        applied = await store.apply(ops)
        if applied.ok:
            return JoinAccepted(
                member=plan.member,
                session=plan.session,
                created=plan.created,
                old_session=plan.old_session,
            )
        if applied.reason == "exists":
            raise JoinConflict(
                "name_conflict",
                "Agent name and DID do not identify the same Membership",
            )
        if applied.reason == "cas":
            failed = ops[applied.op_index] if applied.op_index is not None else None
            key = getattr(failed, "key", "")
            if str(key).startswith((auth_mod.TOKEN_PREFIX, auth_mod.CHALLENGE_PREFIX)):
                raise JoinConflict("unauthorized", JOIN_UNAUTH_MESSAGE)
            if str(key).startswith("member:") and not plan.created:
                record = await store.get_record(f"member:{plan.member['name']}")
                if record is None or not isinstance(record.value, dict):
                    raise JoinConflict(
                        "name_conflict",
                        "Agent name and DID do not identify the same Membership",
                    )
                plan.member_version = record.version
                continue
            raise JoinConflict("unauthorized", JOIN_UNAUTH_MESSAGE)
        raise JoinConflict("internal", "join acceptance failed")
