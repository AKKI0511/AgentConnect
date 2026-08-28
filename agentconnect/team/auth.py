"""Join tokens, challenges, and credential checks for a Team Runtime.

A join token is an opaque value the Runtime issues and verifies. Its
encoding is not public. A network join also requires an identity proof
JWT from :mod:`agentconnect.core.identity`.

    issued = await team.issue_join_token(name="writer", agent_did=writer.agent_did)
    await writer.join(url, join_token=issued["token"])

Failed credential checks raise ``unauthorized`` with one generic message.
"""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any, Mapping, NoReturn, NotRequired, Optional, TypedDict

from agentconnect.core.identity import (
    AgentIdentity,
    issue_membership_attestation,
    verify_identity_proof,
)
from agentconnect.team.codec import format_timestamp, parse_timestamp, utc_now
from agentconnect.team.errors import TeamError
from agentconnect.team.store.base import Store

JOIN_UNAUTH_MESSAGE = "Join credentials are missing or invalid"

CHALLENGES_SET = "join_challenges"
TOKENS_SET = "join_tokens"
TOKEN_PREFIX = "join_token:"
CHALLENGE_PREFIX = "join_challenge:"
TOKEN_SESSIONS_PREFIX = "join_token_sessions:"


class JoinToken(TypedDict):
    """Operator view of a join token the Runtime just issued.

    ``token`` is the secret the Agent sends as ``join_token``. Keep it out
    of logs and Message content.
    """

    token: str
    expires_at: str
    single_use: bool
    agent_did: NotRequired[str]
    name: NotRequired[str]


def join_unauthorized() -> NoReturn:
    """Fail a join without saying which credential check failed."""
    raise TeamError("unauthorized", JOIN_UNAUTH_MESSAGE)


def _as_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


async def create_join_challenge(
    store: Store,
    team_name: str,
    *,
    ttl_seconds: float,
    now=None,
) -> dict[str, str]:
    """Mint a one-time join challenge and persist it."""
    instant = now or utc_now()
    nonce = secrets.token_urlsafe(24)
    expires = instant + timedelta(seconds=float(ttl_seconds))
    record = {
        "nonce": nonce,
        "audience": f"agentconnect:{team_name}",
        "expires_at": format_timestamp(expires),
    }
    await store.put(f"{CHALLENGE_PREFIX}{nonce}", record)
    await store.set_add(CHALLENGES_SET, nonce)
    return {
        "nonce": nonce,
        "audience": record["audience"],
        "expires_at": record["expires_at"],
    }


async def load_challenge(store: Store, nonce: str) -> Optional[dict[str, Any]]:
    """Return the stored challenge for ``nonce``, or None."""
    if not isinstance(nonce, str) or not nonce:
        return None
    record = await store.get(f"{CHALLENGE_PREFIX}{nonce}")
    return record if isinstance(record, dict) else None


async def consume_challenge(store: Store, nonce: str) -> None:
    """Delete ``nonce`` so it cannot authenticate another join."""
    await store.delete(f"{CHALLENGE_PREFIX}{nonce}")
    await store.set_remove(CHALLENGES_SET, nonce)


async def issue_join_token(
    store: Store,
    team_name: str,
    *,
    agent_did: Optional[str] = None,
    name: Optional[str] = None,
    ttl_seconds: float,
    single_use: bool = False,
    now=None,
) -> JoinToken:
    """Issue an opaque join token scoped to this Team."""
    instant = now or utc_now()
    token = secrets.token_urlsafe(32)
    expires = instant + timedelta(seconds=float(ttl_seconds))
    record: dict[str, Any] = {
        "token": token,
        "team": team_name,
        "expires_at": format_timestamp(expires),
        "single_use": bool(single_use),
        "used": False,
        "revoked": False,
    }
    if agent_did:
        record["agent_did"] = agent_did
    if name:
        record["name"] = name
    await store.put(f"{TOKEN_PREFIX}{token}", record)
    await store.set_add(TOKENS_SET, token)
    issued: JoinToken = {
        "token": token,
        "expires_at": record["expires_at"],
        "single_use": bool(single_use),
    }
    if agent_did:
        issued["agent_did"] = agent_did
    if name:
        issued["name"] = name
    return issued


async def load_join_token(store: Store, token: str) -> Optional[dict[str, Any]]:
    """Return the stored join-token record, or None."""
    if not isinstance(token, str) or not token:
        return None
    record = await store.get(f"{TOKEN_PREFIX}{token}")
    return record if isinstance(record, dict) else None


async def mark_join_token_used(store: Store, record: Mapping[str, Any]) -> None:
    """Mark a single-use token as consumed."""
    updated = dict(record)
    updated["used"] = True
    await store.put(f"{TOKEN_PREFIX}{updated['token']}", updated)


async def revoke_join_token_record(
    store: Store, token: str
) -> Optional[dict[str, Any]]:
    """Mark ``token`` revoked. Returns the record if it existed."""
    record = await load_join_token(store, token)
    if record is None:
        return None
    record = dict(record)
    record["revoked"] = True
    await store.put(f"{TOKEN_PREFIX}{token}", record)
    return record


async def bind_session_to_token(
    store: Store, join_token: str, session_token: str
) -> None:
    """Record that ``session_token`` was created from ``join_token``."""
    await store.set_add(f"{TOKEN_SESSIONS_PREFIX}{join_token}", session_token)


async def unbind_session_from_token(
    store: Store, join_token: str, session_token: str
) -> None:
    """Drop the session mapping when a Session is deleted."""
    await store.set_remove(f"{TOKEN_SESSIONS_PREFIX}{join_token}", session_token)


async def sessions_for_join_token(store: Store, join_token: str) -> list[str]:
    """Return Session tokens created from ``join_token``."""
    return await store.set_members(f"{TOKEN_SESSIONS_PREFIX}{join_token}")


async def tokens_bound_to_member(
    store: Store, *, name: Optional[str], agent_did: Optional[str]
) -> list[str]:
    """Return join tokens bound to this name or DID."""
    found: list[str] = []
    for token in await store.set_members(TOKENS_SET):
        record = await load_join_token(store, token)
        if record is None or record.get("revoked"):
            continue
        if name and record.get("name") == name:
            found.append(token)
            continue
        if agent_did and record.get("agent_did") == agent_did:
            found.append(token)
    return found


def token_is_usable(record: Mapping[str, Any], *, now=None) -> bool:
    """Return True when the token is unexpired, unrevoked, and not consumed."""
    if record.get("revoked"):
        return False
    if record.get("single_use") and record.get("used"):
        return False
    instant = now or utc_now()
    try:
        expires = parse_timestamp(str(record["expires_at"]))
    except (KeyError, ValueError, TypeError):
        return False
    return expires > instant


def token_matches_join(record: Mapping[str, Any], *, agent_did: str, name: str) -> bool:
    """Return True when bound DID/name (if any) match this join."""
    bound_did = record.get("agent_did")
    bound_name = record.get("name")
    if isinstance(bound_did, str) and bound_did != agent_did:
        return False
    if isinstance(bound_name, str) and bound_name != name:
        return False
    return True


async def authenticate_join(
    store: Store,
    *,
    team_name: str,
    agent_did: str,
    name: str,
    join_token: Optional[str],
    identity_proof: Optional[str],
    require_auth: bool,
    now=None,
) -> Optional[dict[str, Any]]:
    """Verify join credentials.

    Returns the join-token record when a token was used, otherwise None.
    Raises ``unauthorized`` with :data:`JOIN_UNAUTH_MESSAGE` on any failure.
    """
    token_value = _as_optional_str(join_token)
    proof_value = _as_optional_str(identity_proof)
    if require_auth and (not token_value or not proof_value):
        join_unauthorized()
    if not token_value and not proof_value:
        return None

    token_record: Optional[dict[str, Any]] = None
    if token_value:
        token_record = await load_join_token(store, token_value)
        instant = now or utc_now()
        if (
            token_record is None
            or token_record.get("team") not in {None, team_name}
            or not token_is_usable(token_record, now=instant)
            or not token_matches_join(token_record, agent_did=agent_did, name=name)
        ):
            join_unauthorized()

    if proof_value:
        try:
            payload = split_proof_nonce(proof_value)
        except ValueError:
            join_unauthorized()
        nonce = payload.get("nonce")
        if not isinstance(nonce, str):
            join_unauthorized()
        challenge = await load_challenge(store, nonce)
        instant = now or utc_now()
        if challenge is None:
            join_unauthorized()
        try:
            expires = parse_timestamp(str(challenge["expires_at"]))
        except (KeyError, ValueError, TypeError):
            join_unauthorized()
        if expires <= instant:
            join_unauthorized()
        if challenge.get("audience") != f"agentconnect:{team_name}":
            join_unauthorized()
        try:
            verify_identity_proof(
                proof_value,
                agent_did=agent_did,
                challenge=challenge,
                now=instant,
            )
        except ValueError:
            join_unauthorized()
        await consume_challenge(store, nonce)
    elif require_auth:
        join_unauthorized()

    return token_record


def split_proof_nonce(token: str) -> dict[str, Any]:
    """Read unverified JWT payload so the challenge can be loaded."""
    from agentconnect.core.identity import split_jwt

    _, payload, _, _ = split_jwt(token)
    return payload


def mint_member_attestation(
    team_identity: AgentIdentity,
    *,
    agent_did: str,
    name: str,
    address: str,
    team_name: str,
    now=None,
) -> Optional[str]:
    """Mint a membership attestation, or None when the DID is not Ed25519."""
    try:
        return issue_membership_attestation(
            team_identity,
            agent_did=agent_did,
            name=name,
            address=address,
            team_name=team_name,
            now=now,
        )
    except ValueError:
        return None


async def sweep_join_state(store: Store, now=None) -> None:
    """Drop expired challenges and expired join tokens."""
    instant = now or utc_now()
    for nonce in list(await store.set_members(CHALLENGES_SET)):
        record = await load_challenge(store, nonce)
        if record is None:
            await store.set_remove(CHALLENGES_SET, nonce)
            continue
        try:
            expires = parse_timestamp(str(record["expires_at"]))
        except (KeyError, ValueError, TypeError):
            await consume_challenge(store, nonce)
            continue
        if expires <= instant:
            await consume_challenge(store, nonce)
    for token in list(await store.set_members(TOKENS_SET)):
        record = await load_join_token(store, token)
        if record is None:
            await store.set_remove(TOKENS_SET, token)
            continue
        try:
            expires = parse_timestamp(str(record["expires_at"]))
        except (KeyError, ValueError, TypeError):
            await store.delete(f"{TOKEN_PREFIX}{token}")
            await store.set_remove(TOKENS_SET, token)
            continue
        if expires <= instant:
            await store.delete(f"{TOKEN_PREFIX}{token}")
            await store.set_remove(TOKENS_SET, token)
            await store.delete(f"{TOKEN_SESSIONS_PREFIX}{token}")
