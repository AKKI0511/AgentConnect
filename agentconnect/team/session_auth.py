"""Session resolution for HTTP and MCP at the Team trust boundary.

A Bearer token is the Session. Operator-without-token is allowed only when
hosting trust is explicit: in-process MCP, or a loopback HTTP peer with no
forwarded-client headers. Header presence is enough to refuse operator,
including empty values.

    from agentconnect.team.session_auth import session_token_for_request

    token = await session_token_for_request(
        team, headers, peer_host="127.0.0.1", in_process=False
    )
"""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping
from typing import Optional, Protocol

from agentconnect.team.errors import TeamError

_FORWARDED_EXACT = frozenset({"forwarded", "x-real-ip"})
_FORWARDED_PREFIX = "x-forwarded-"


class SessionRuntime(Protocol):
    """Runtime operations Session resolution needs. ``Team`` satisfies this."""

    async def ensure_operator_session(self) -> str:
        """Return a live Session token for the loopback operator."""

    async def require_live_session(self, session_token: str) -> str:
        """Return ``session_token`` if the Session is live. Does not renew it."""


def host_is_loopback(host: str) -> bool:
    """Return True when ``host`` is loopback, including IPv4-mapped IPv6."""
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    if addr.is_loopback:
        return True
    mapped = getattr(addr, "ipv4_mapped", None)
    return mapped is not None and mapped.is_loopback


def forwarded_client_headers(headers: Mapping[str, str] | None) -> bool:
    """Return True when a forwarded-client header is present, even if empty."""
    if headers is None:
        return False
    for key in headers:
        name = str(key).lower()
        if name in _FORWARDED_EXACT or name.startswith(_FORWARDED_PREFIX):
            return True
    return False


def authorization_header_present(headers: Mapping[str, str] | None) -> bool:
    """Return True when an Authorization header is present, even if empty."""
    if headers is None:
        return False
    for key in headers:
        if str(key).lower() == "authorization":
            return True
    return False


def allow_loopback_operator(
    *,
    headers: Mapping[str, str] | None,
    peer_host: str | None,
    in_process: bool,
) -> bool:
    """Return True when a missing Authorization header may mean operator.

    In-process MCP is trusted only when ``in_process`` is True and there is
    no HTTP peer. An HTTP request needs a loopback peer, no forwarded-client
    headers, and is never inferred from missing request context.
    """
    if forwarded_client_headers(headers):
        return False
    if peer_host is not None:
        return host_is_loopback(peer_host)
    return in_process


def bearer_token(headers: Mapping[str, str] | None) -> Optional[str]:
    """Return the Bearer token, or None if Authorization is absent.

    A present header that is empty or not ``Bearer <token>`` is unauthorized.
    """
    if headers is None or not authorization_header_present(headers):
        return None
    value: str | None = None
    for key, item in headers.items():
        if str(key).lower() == "authorization":
            value = str(item)
            break
    if value is None or not str(value).strip():
        raise TeamError("unauthorized", "Session is missing or invalid")
    raw = str(value).strip()
    scheme, _, rest = raw.partition(" ")
    if scheme.lower() != "bearer" or not rest.strip():
        raise TeamError("unauthorized", "Session is missing or invalid")
    return rest.strip()


async def session_token_for_request(
    runtime: SessionRuntime,
    headers: Mapping[str, str] | None,
    *,
    peer_host: str | None = None,
    in_process: bool = False,
) -> str:
    """Return the Session token for this HTTP or MCP call.

    A Bearer token is checked without renewing expiry. A missing header uses
    the operator Session only on an explicitly trusted local path.
    """
    token = bearer_token(headers)
    if token is not None:
        await runtime.require_live_session(token)
        return token
    if allow_loopback_operator(
        headers=headers, peer_host=peer_host, in_process=in_process
    ):
        return await runtime.ensure_operator_session()
    raise TeamError("unauthorized", "Session is missing or invalid")
