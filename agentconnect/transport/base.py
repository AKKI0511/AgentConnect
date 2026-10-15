"""
Outbound transport Service Provider Interface (SPI).

This module defines a minimal interface for delivering messages to remote
agents without knowing the underlying protocol or transport. New
transports (HTTP, WS, Redis, NATS, Kafka) can be added by implementing
this interface without changing Runtime or agent code.

Precedence and separation of concerns:
- Addressing: `TransportTarget` is the single source of truth. Transports MUST NOT
  consult `Message.metadata` for addressing, URLs, inbox paths, or auth.
- Hints: `RouteContext` carries minimal, non-overriding protocol/transport hints
  (e.g., protocol/transport identifiers). It MUST NOT duplicate or override
  addressing. Use `TransportTarget` for all routing data.
- App semantics: `Message.metadata` contains application-level metadata. Transports
  MUST treat it as opaque and SHOULD NOT read it except for reserved, transport-
  neutral correlation keys (e.g., `request_id` for idempotency headers). Timeouts,
  TLS verification, retry budgets, etc., are constructor defaults on transports,
  not per-message values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Tuple

from agentconnect.transport.envelope import CollaborationMessage as Message
from agentconnect.transport.schemas import TransportTarget


@dataclass
class RouteContext:
    """Hints for protocol/transport selection and routing.

    - protocol_hint: e.g., 'agentconnect.http.v1', 'google.a2a.v1'
    - transport_hint: e.g., 'http', 'ws', 'redis', 'nats', 'kafka'
    """

    protocol_hint: str = "agentconnect.http.v1"
    transport_hint: str = "http"


class OutboundTransport(Protocol):
    """Outbound transport used by the gateway for remote delivery.

    Implementations should be stateless or lightweight; configuration is passed
    via constructor. All network activity must be async.

    Contract:
    - `send(message, target, route)` -> `(ok, immediate_response?, request_id?)`
    - `check(request_id, target, route)` -> `(status: 'completed'|'pending'|'not_found', response?)`

    See module docstring for precedence/ownership rules between `TransportTarget`,
    `RouteContext`, and `Message.metadata`.
    """

    async def send(
        self, message: Message, target: TransportTarget, ctx: RouteContext
    ) -> Tuple[bool, Optional[Message], Optional[str]]:
        """Send a message to a remote agent.

        Returns:
            (ok, immediate_response, request_id)

        - ok: whether the remote accepted the request
        - immediate_response: response message if completed synchronously, else None
        - request_id: correlation id recognized by the remote, if available
        """

    async def check(
        self, request_id: str, target: TransportTarget, ctx: RouteContext
    ) -> Tuple[str, Optional[Message]]:
        """Check the status of a previous request.

        Returns:
            (status, response)

        Where status in {'completed', 'pending', 'not_found'}.
        """
