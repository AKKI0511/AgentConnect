"""Agent Session: join, pull work, map handler outcomes, reconnect.

A Session talks to a Runtime through a transport. Embedded Teams use
in-process calls. A URL uses HTTP POST plus an SSE work hint. Agent code
does not change between them.

``instance_id`` is generated once per running copy unless the caller
supplies a stable value. Re-joining with that same id replaces this
copy's Session. Two copies must not share an ``instance_id``.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Literal, Mapping, Optional

from agentconnect.agent.context import Context
from agentconnect.agent.errors import SessionError
from agentconnect.core.directory import DirectoryEntry, FindResult
from agentconnect.core.message import Delivery, parse_delivery
from agentconnect.core.operations import (
    AcceptedSendResult,
    HeartbeatResult,
    HistoryResult,
    JoinResult,
    RenewResult,
    TicketedSendResult,
    parse_history_result,
    parse_join_result,
    parse_lease_result,
    parse_send_result,
)
from agentconnect.core.primitives import DeliveryHistoryForm
from agentconnect.core.spec import SPEC_VERSION
from agentconnect.core.ticket import Ticket, parse_ticket
from agentconnect.transport.agent_http import HttpRuntimeTransport
from agentconnect.transport.inprocess import InProcessTransport
from agentconnect.transport.runtime import TransportError

if TYPE_CHECKING:
    from agentconnect.agent.base import BaseAgent

logger = logging.getLogger(__name__)

HANDLER_FAILURE_MESSAGE = "The handler failed."

_RETRY_JOIN_CODES = frozenset({"unavailable"})
_RECONNECT_CODES = frozenset({"unauthorized", "unavailable"})
_NO_RECONNECT_CODES = frozenset(
    {
        "busy",
        "wait_limit",
        "id_conflict",
        "invalid_request",
        "invalid_address",
        "address_outside_team",
        "forbidden",
        "not_found",
        "payload_too_large",
        "unsupported_collect_mode",
        "unsupported_version",
        "name_conflict",
        "lease_expired",
        "ticket_closed",
    }
)
_DEFAULT_RECOVERY_SECONDS = 30.0
CollectMode = Literal["wait", "ticket", "callback", "stream"]
_handling: ContextVar[Optional[tuple[Any, Delivery]]] = ContextVar(
    "agentconnect_handling", default=None
)


@dataclass
class _TrackedLease:
    """One Delivery this Session still owes a finish or renew for."""

    delivery: Delivery
    lease_expires_at: str
    task: Optional[asyncio.Task] = None


def _local_name(address: str) -> str:
    """Return the Agent name from a local or qualified Address."""
    return str(address).split("@", 1)[0]


def _parse_deadline(value: str) -> Optional[datetime]:
    """Parse a Runtime timestamp, or None when the form is unusable."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _lease_id_of(delivery: Any) -> str:
    """Return the lease id from a Delivery model or mapping."""
    if isinstance(delivery, Mapping):
        return str(delivery["lease_id"])
    return str(delivery.lease_id)


def _should_reconnect(exc: TransportError) -> bool:
    """Reconnect on lost Session or unreachable Runtime, not on busy Mailboxes."""
    if exc.code in _NO_RECONNECT_CODES:
        return False
    return exc.code in _RECONNECT_CODES


def bind_transport(target: Any) -> Any:
    """Return an HTTP transport for a URL, or in-process for a Team object."""
    if isinstance(target, str):
        return HttpRuntimeTransport(target)
    return InProcessTransport(target)


def deadline_rfc3339(seconds: float) -> str:
    """Return a future UTC timestamp the Runtime will accept."""
    instant = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return instant.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class Session:
    """One running copy of an Agent connected to a Team."""

    def __init__(
        self,
        agent: "BaseAgent",
        target: Any,
        *,
        instance_id: str,
        agent_did: str,
        profile: Mapping[str, Any],
        max_in_flight: int,
        delivery_history: DeliveryHistoryForm = "bodies",
    ) -> None:
        """Bind this copy to a Team object or a Runtime URL."""
        self._agent = agent
        self._target = target
        self.instance_id = instance_id
        self.agent_did = agent_did
        self._profile = dict(profile)
        self.max_in_flight = max_in_flight
        self.delivery_history = delivery_history
        self._transport = bind_transport(target)
        self.session_token: Optional[str] = None
        self.address: Optional[str] = None
        self.team_name: Optional[str] = None
        self.limits: dict[str, int | float] = {}
        self.persistence: Optional[str] = None
        self.session_expires_at: Optional[str] = None
        self._connected = False
        self._stopped = False
        self._wake = asyncio.Event()
        self._supervisor: Optional[asyncio.Task] = None
        self._inflight: set[asyncio.Task] = set()
        self._active: dict[str, _TrackedLease] = {}
        self._capacity = asyncio.Event()
        self._renew_wake = asyncio.Event()
        self._reconnect_lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        """True while this copy holds a live Session token."""
        return self._connected and not self._stopped

    async def start(self) -> "Session":
        """Join (retrying until the Team is up) and start pull, heartbeat, and events."""
        await self._connect_with_retry()
        self._supervisor = asyncio.create_task(
            self._supervise(), name=f"session:{self.instance_id}"
        )
        return self

    async def close(self, *, disconnect: bool = True) -> None:
        """Stop the supervisor. Disconnect the Session when ``disconnect`` is True."""
        self._stopped = True
        self._connected = False
        self._wake.set()
        self._renew_wake.set()
        current = asyncio.current_task()
        for task in list(self._inflight):
            if task is not current:
                task.cancel()
        self._active.clear()
        self._capacity.set()
        if self._supervisor is not None and self._supervisor is not current:
            self._supervisor.cancel()
        pending = [task for task in self._inflight if task is not current]
        if self._supervisor is not None and self._supervisor is not current:
            pending.append(self._supervisor)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._inflight.clear()
        self._supervisor = None
        token = self.session_token
        self.session_token = None
        if disconnect and token:
            try:
                await self._transport.disconnect(token)
            except TransportError:
                pass
        await self._transport.close()

    async def ask(
        self,
        recipient: str,
        content: Any,
        *,
        deadline_seconds: Optional[float] = None,
        collect: CollectMode = "wait",
        thread_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        message_id: Optional[str] = None,
        deadline: Optional[str] = None,
        handling: Optional[Delivery] = None,
    ) -> Ticket:
        """Send a reply-expected request.

        ``collect="wait"`` (default) holds until the Ticket is terminal or
        the Runtime wait hold elapses, then returns the current Ticket.
        That Ticket may still be ``open``. Collect the rest with
        ``get_result``. Ending the wait does not end accepted work.

        ``collect="ticket"`` returns immediately with the current Ticket.

        Called from a handler, this send inherits the current Message as
        ``parent_id``. An omitted deadline inherits that request's stamped
        cutoff. An explicit ``deadline_seconds`` becomes an absolute
        timestamp; the Runtime rejects a child that exceeds the parent.
        A new Thread starts when ``recipient`` is not the other party in
        the current Thread.

            thread_id = str(uuid.uuid4())
            await session.ask("writer", "outline this", thread_id=thread_id)
            await session.ask("writer", "expand section 2", thread_id=thread_id)
        """
        thread_id, parent_id, deadline_value = self._child_send_fields(
            recipient,
            thread_id=thread_id,
            parent_id=parent_id,
            deadline=deadline,
            deadline_seconds=deadline_seconds,
            handling=handling,
        )
        body: dict[str, Any] = {
            "id": message_id or str(uuid.uuid4()),
            "recipient": recipient,
            "kind": "request",
            "content": content,
            "collect": collect,
        }
        if deadline_value:
            body["deadline"] = deadline_value
        if thread_id is not None:
            body["thread_id"] = thread_id
        if parent_id is not None:
            body["parent_id"] = parent_id
        if metadata is not None:
            body["metadata"] = dict(metadata)
        result = parse_send_result(await self._call("send", self._token(), body))
        if not isinstance(result, TicketedSendResult):
            raise SessionError("internal", "request send did not return a Ticket")
        ticket = result.ticket
        object.__setattr__(ticket, "_client_trace_id", result.message.trace_id)
        return ticket

    async def tell(
        self,
        recipient: str,
        content: Any,
        *,
        thread_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        message_id: Optional[str] = None,
        handling: Optional[Delivery] = None,
    ) -> AcceptedSendResult:
        """Send an event. No Ticket is created.

        await session.tell("writer", {"note": "source changed"})
        """
        thread_id, parent_id, _deadline = self._child_send_fields(
            recipient,
            thread_id=thread_id,
            parent_id=parent_id,
            deadline=None,
            deadline_seconds=None,
            event=True,
            handling=handling,
        )
        body: dict[str, Any] = {
            "id": message_id or str(uuid.uuid4()),
            "recipient": recipient,
            "kind": "event",
            "content": content,
        }
        if thread_id is not None:
            body["thread_id"] = thread_id
        if parent_id is not None:
            body["parent_id"] = parent_id
        if metadata is not None:
            body["metadata"] = dict(metadata)
        result = parse_send_result(await self._call("send", self._token(), body))
        if not isinstance(result, AcceptedSendResult):
            raise SessionError("internal", "event send did not return accepted")
        return result

    async def find(
        self, query: str, *, limit: int | None = None, detail: str = "summary"
    ) -> FindResult:
        """Search this Team's Directory.

        found = await session.find("someone who can draft a summary")
        """
        return FindResult.model_validate(
            await self._call(
                "find",
                self._token(),
                query,
                limit=limit,
                detail=detail,
            )
        )

    async def get_profile(self, address: str) -> DirectoryEntry:
        """Return one Directory entry."""
        return DirectoryEntry.model_validate(
            await self._call("get_profile", self._token(), address)
        )

    async def get_result(self, ticket_id: str) -> Ticket:
        """Return the current Ticket owned by this Membership."""
        return parse_ticket(await self._call("get_result", self._token(), ticket_id))

    async def get_history(
        self,
        thread_id: str,
        *,
        before: Optional[str] = None,
        limit: int = 50,
    ) -> HistoryResult:
        """Return one page of retained Thread history, ordered by ``seq``.

        Omit ``before`` for the newest page. A UUID that is not in the
        transcript returns that newest page.
        """
        return parse_history_result(
            await self._call(
                "get_history",
                self._token(),
                thread_id,
                before=before,
                limit=limit,
            )
        )

    async def complete_delivery(self, delivery: Mapping[str, Any]) -> dict[str, Any]:
        """Finish a Delivery without a response Message."""
        lease_id = _lease_id_of(delivery)
        try:
            result = await self._call("complete", self._token(), lease_id)
        except SessionError as exc:
            if exc.code in {"lease_expired", "ticket_closed", "not_found"}:
                self._release_local_lease(lease_id)
            raise
        self._release_local_lease(lease_id)
        return result

    async def reply_delivery(
        self,
        delivery: Mapping[str, Any],
        *,
        outcome: str,
        content: Any = None,
        error: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Finish a leased reply-expected Delivery."""
        lease_id = _lease_id_of(delivery)
        body: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "lease_id": lease_id,
            "outcome": outcome,
        }
        if outcome == "completed":
            body["content"] = content
        else:
            body["error"] = dict(
                error or {"code": "handler_failed", "message": "failed"}
            )
        try:
            result = await self._call("reply", self._token(), body)
        except SessionError as exc:
            if exc.code in {"lease_expired", "ticket_closed", "not_found"}:
                self._release_local_lease(lease_id)
            raise
        self._release_local_lease(lease_id)
        return result

    def handling_delivery(self) -> Optional[Delivery]:
        """Return the Delivery this Session is handling in this task, if any."""
        current = _handling.get()
        if current is None:
            return None
        owner, delivery = current
        if owner is not self:
            return None
        return delivery

    def _track(self, delivery: Delivery) -> None:
        """Count ``delivery`` against ``max_in_flight`` until it is finished."""
        self._active[delivery.lease_id] = _TrackedLease(
            delivery, delivery.lease_expires_at
        )
        self._renew_wake.set()

    def _release_local_lease(self, lease_id: str) -> None:
        """Drop local tracking for a finished or dead lease."""
        if lease_id in self._active:
            del self._active[lease_id]
            self._capacity.set()

    def _cancel_tracked(self, lease_id: str) -> None:
        """Stop SDK-managed handling and abandoned renewal for ``lease_id``."""
        tracked = self._active.get(lease_id)
        task = tracked.task if tracked is not None else None
        self._release_local_lease(lease_id)
        if task is not None and not task.done():
            task.cancel()

    def _occupied(self) -> int:
        """Count each distinct Delivery obligation once.

        A deferred reply lives in ``_active`` after its handler task has
        finished. A cancelled handler can already be gone from ``_active``
        while its task is still unwinding in ``_inflight``. Those are two
        slots. A running handler that appears in both is one slot.
        """
        counted_tasks = {
            tracked.task
            for tracked in self._active.values()
            if tracked.task is not None
        }
        extra = sum(
            1
            for task in self._inflight
            if not task.done() and task not in counted_tasks
        )
        return len(self._active) + extra

    def _room(self) -> int:
        """Return how many more Deliveries this Session may lease."""
        return max(0, self.max_in_flight - self._occupied())

    def _child_send_fields(
        self,
        recipient: str,
        *,
        thread_id: Optional[str],
        parent_id: Optional[str],
        deadline: Optional[str],
        deadline_seconds: Optional[float],
        event: bool = False,
        handling: Optional[Delivery] = None,
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Fill parent, Thread, and deadline from the originating Delivery."""
        origin = handling if handling is not None else self.handling_delivery()
        if parent_id is None and origin is not None:
            parent_id = origin.message.id
        if thread_id is None and origin is not None:
            message = origin.message
            current_thread = getattr(message, "thread_id", None)
            if current_thread and _local_name(recipient) == _local_name(
                str(message.sender)
            ):
                thread_id = str(current_thread)
            else:
                thread_id = str(uuid.uuid4())
        if event:
            return thread_id, parent_id, None
        if deadline is not None:
            return thread_id, parent_id, deadline
        if deadline_seconds is not None:
            return thread_id, parent_id, deadline_rfc3339(deadline_seconds)
        return thread_id, parent_id, None

    def _token(self) -> str:
        token = self.session_token
        if not token:
            raise SessionError("unauthorized", "Agent is not connected to a Team")
        return token

    def _join_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "spec_version": SPEC_VERSION,
            "name": self._agent._agent_name,
            "agent_did": self.agent_did,
            "profile": dict(self._profile),
            "instance_id": self.instance_id,
            "max_in_flight": self.max_in_flight,
        }
        if self.delivery_history != "bodies":
            body["delivery_history"] = self.delivery_history
        return body

    async def _connect_with_retry(self) -> None:
        delay = 0.05
        while not self._stopped:
            try:
                body = self._join_body()
                await self._attach_join_credentials(body)
                result = await self._transport.join(body)
                if self._stopped:
                    parsed = parse_join_result(result)
                    if parsed.session_token:
                        try:
                            await self._transport.disconnect(parsed.session_token)
                        except TransportError:
                            pass
                    return
                self._apply_join(result)
                return
            except TransportError as exc:
                if exc.code in _RETRY_JOIN_CODES or exc.retryable:
                    logger.debug(
                        "join retry name=%s code=%s",
                        self._agent._agent_name,
                        exc.code,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 2.0)
                    continue
                raise SessionError.from_transport(exc) from exc

    async def _attach_join_credentials(self, body: dict[str, Any]) -> None:
        """Add join_token and identity_proof when this join is authenticated."""
        token = getattr(self._agent, "join_token", None)
        target_is_url = isinstance(self._target, str)
        require = bool(getattr(self._target, "require_join_auth", False))
        if not (target_is_url or token or require):
            return
        challenge_fn = getattr(self._transport, "join_challenge", None)
        if challenge_fn is None:
            return
        challenge = await challenge_fn()
        try:
            body["identity_proof"] = self._agent.prove_join(challenge)
        except ValueError as exc:
            raise SessionError(
                "unauthorized", "Join credentials are missing or invalid"
            ) from exc
        if token:
            body["join_token"] = token

    def _apply_join(self, result: Mapping[str, Any] | JoinResult) -> None:
        parsed = parse_join_result(result)
        self.session_token = parsed.session_token
        self.address = parsed.address
        self.team_name = parsed.team_name
        self.instance_id = parsed.instance_id
        self.limits = parsed.limits.to_public_dict()
        self.persistence = parsed.persistence
        self.session_expires_at = parsed.session_expires_at
        self._connected = True
        self._active.clear()
        self._capacity.set()
        self._wake.set()
        configure = getattr(self._transport, "configure_wait_hold", None)
        if callable(configure):
            configure(float(parsed.limits.wait_hold_seconds))
        logger.info(
            "joined team=%s address=%s instance=%s",
            self.team_name,
            self.address,
            self.instance_id,
        )

    async def _supervise(self) -> None:
        heartbeat = asyncio.create_task(self._heartbeat_loop(), name="heartbeat")
        events = asyncio.create_task(self._events_loop(), name="events")
        pull = asyncio.create_task(self._pull_loop(), name="pull")
        renew = asyncio.create_task(self._renew_loop(), name="renew")
        try:
            await asyncio.gather(heartbeat, events, pull, renew)
        except asyncio.CancelledError:
            raise
        finally:
            for task in (heartbeat, events, pull, renew):
                task.cancel()
            await asyncio.gather(heartbeat, events, pull, renew, return_exceptions=True)

    async def _heartbeat_loop(self) -> None:
        while not self._stopped:
            interval = self._heartbeat_interval()
            try:
                await asyncio.sleep(interval)
                if self._stopped or not self.session_token:
                    continue
                result = HeartbeatResult.model_validate(
                    await self._transport.heartbeat(self.session_token)
                )
                self.session_expires_at = result.session_expires_at
            except asyncio.CancelledError:
                raise
            except TransportError as exc:
                if self._stopped:
                    return
                if _should_reconnect(exc):
                    await self._reconnect()
                    continue
                logger.warning(
                    "heartbeat failed address=%s code=%s", self.address, exc.code
                )
            except Exception:
                if self._stopped:
                    return
                logger.debug("heartbeat error address=%s", self.address, exc_info=True)
                await self._reconnect()

    def _heartbeat_interval(self) -> float:
        expires = self.session_expires_at
        if not expires:
            return min(60.0, max(0.05, self._agent._session_ttl_hint / 3))
        try:
            instant = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            remaining = (instant - datetime.now(timezone.utc)).total_seconds()
            return min(60.0, max(0.05, remaining / 3))
        except ValueError:
            return 60.0

    def _renew_interval(self) -> float:
        """Sleep until the soonest tracked lease should be renewed."""
        if not self._active:
            return 1.0
        now = datetime.now(timezone.utc)
        soonest: Optional[float] = None
        for tracked in self._active.values():
            instant = _parse_deadline(tracked.lease_expires_at)
            if instant is None:
                continue
            remaining = (instant - now).total_seconds()
            if soonest is None or remaining < soonest:
                soonest = remaining
        if soonest is None:
            return 1.0
        return max(0.05, min(soonest / 3.0, 20.0))

    async def _renew_loop(self) -> None:
        while not self._stopped:
            interval = self._renew_interval()
            try:
                self._renew_wake.clear()
                try:
                    await asyncio.wait_for(self._renew_wake.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    pass
                if self._stopped or not self.session_token:
                    continue
                for lease_id in list(self._active):
                    try:
                        result = RenewResult.model_validate(
                            await self._transport.renew(self.session_token, lease_id)
                        )
                    except TransportError as exc:
                        if self._stopped:
                            return
                        if exc.code in {"lease_expired", "not_found", "ticket_closed"}:
                            self._cancel_tracked(lease_id)
                            continue
                        if _should_reconnect(exc):
                            await self._reconnect()
                            break
                        logger.warning(
                            "renew failed address=%s code=%s",
                            self.address,
                            exc.code,
                        )
                        continue
                    tracked = self._active.get(lease_id)
                    if tracked is not None:
                        tracked.lease_expires_at = result.lease_expires_at
            except asyncio.CancelledError:
                raise
            except Exception:
                if self._stopped:
                    return
                logger.debug("renew error address=%s", self.address, exc_info=True)

    async def _events_loop(self) -> None:
        while not self._stopped:
            token = self.session_token
            if not token:
                await asyncio.sleep(0.05)
                continue
            try:
                async for event in self._transport.events(token):
                    if self._stopped:
                        return
                    if not isinstance(event, dict):
                        continue
                    if event.get("type") == "work_available":
                        self._wake.set()
            except asyncio.CancelledError:
                raise
            except TransportError as exc:
                if self._stopped:
                    return
                if _should_reconnect(exc):
                    await self._reconnect()
                    continue
                await asyncio.sleep(0.2)
            except Exception:
                if self._stopped:
                    return
                logger.debug(
                    "event stream error address=%s", self.address, exc_info=True
                )
                await asyncio.sleep(0.2)

    async def _pull_loop(self) -> None:
        while not self._stopped:
            if not self.session_token:
                await asyncio.sleep(0.05)
                continue
            room = self._room()
            if room <= 0:
                self._capacity.clear()
                if self._room() > 0:
                    continue
                try:
                    await asyncio.wait_for(self._capacity.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
                continue
            try:
                leased = parse_lease_result(
                    await self._transport.lease(self.session_token, room)
                )
            except TransportError as exc:
                if self._stopped:
                    return
                if _should_reconnect(exc):
                    await self._reconnect()
                    continue
                logger.warning(
                    "lease failed address=%s code=%s", self.address, exc.code
                )
                await asyncio.sleep(0.2)
                continue
            deliveries = leased.deliveries
            if not deliveries:
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
                self._wake.clear()
                continue
            for delivery in deliveries:
                parsed = parse_delivery(delivery)
                self._track(parsed)
                task = asyncio.create_task(
                    self._handle(parsed), name=f"delivery:{parsed.lease_id}"
                )
                tracked = self._active.get(parsed.lease_id)
                if tracked is not None:
                    tracked.task = task
                self._inflight.add(task)
                task.add_done_callback(self._on_handler_done)

    async def _reconnect(self) -> None:
        if self._stopped:
            return
        async with self._reconnect_lock:
            if self._stopped:
                return
            if self.session_token and self._connected:
                try:
                    result = HeartbeatResult.model_validate(
                        await self._transport.heartbeat(self.session_token)
                    )
                    self.session_expires_at = result.session_expires_at
                    return
                except TransportError:
                    self._connected = False
            logger.info(
                "reconnecting address=%s instance=%s", self.address, self.instance_id
            )
            await self._abandon_sdk_handlers()
            if isinstance(self._target, str):
                try:
                    await self._transport.close()
                except Exception:
                    pass
                self._transport = bind_transport(self._target)
            try:
                await self._connect_with_retry()
            except SessionError:
                logger.warning("reconnect failed address=%s", self.address)
                await asyncio.sleep(0.2)

    async def _abandon_sdk_handlers(self) -> None:
        """Cancel other SDK-managed handlers and stop abandoned renewal.

        Do not cancel or await the calling task. A handler operation that
        triggered this recovery is waiting for it to finish.
        """
        current = asyncio.current_task()
        tasks: list[asyncio.Task] = []
        seen: set[asyncio.Task] = set()
        for tracked in list(self._active.values()):
            task = tracked.task
            if task is None or task.done() or task is current:
                continue
            task.cancel()
            tasks.append(task)
            seen.add(task)
        for task in list(self._inflight):
            if task.done() or task is current or task in seen:
                continue
            task.cancel()
            tasks.append(task)
        self._active.clear()
        self._capacity.set()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _on_handler_done(self, task: asyncio.Task) -> None:
        """Drop a finished handler task and wake pull when a slot is free."""
        self._inflight.discard(task)
        if self._room() > 0:
            self._capacity.set()

    async def _handle(self, delivery: Any) -> None:
        parsed = parse_delivery(delivery)
        message = parsed.message
        token = _handling.set((self, parsed))
        try:
            ctx = await self._build_context(parsed)
            try:
                result = await _invoke_handler(self._agent, message, ctx)
            except Exception as exc:
                logger.exception(
                    "handler failed address=%s message_id=%s",
                    self.address,
                    message.id,
                )
                await self._fail_or_complete(parsed, exc)
                return
            if ctx.ticket_taken:
                return
            await self._finish_handler(parsed, result)
        except asyncio.CancelledError:
            self._release_local_lease(parsed.lease_id)
            raise
        finally:
            _handling.reset(token)

    async def _build_context(self, delivery: Any) -> Context:
        from agentconnect.core.message import Delivery as DeliveryModel

        parsed = (
            delivery
            if isinstance(delivery, DeliveryModel)
            else parse_delivery(delivery)
        )
        return Context(self, parsed)

    async def _finish_handler(self, delivery: Any, result: Any) -> None:
        from agentconnect.core.message import is_reply_expected

        reply_expected = is_reply_expected(delivery.message)
        content = _handler_content(result)
        try:
            if reply_expected:
                if content is _DECLINED:
                    await self.complete_delivery(delivery)
                else:
                    await self.reply_delivery(
                        delivery, outcome="completed", content=content
                    )
            else:
                await self.complete_delivery(delivery)
        except SessionError as exc:
            if exc.code == "payload_too_large" and reply_expected:
                try:
                    await self.reply_delivery(
                        delivery,
                        outcome="failed",
                        error={
                            "code": "handler_failed",
                            "message": HANDLER_FAILURE_MESSAGE,
                        },
                    )
                except SessionError as finish_exc:
                    logger.warning(
                        "fail delivery failed address=%s code=%s",
                        self.address,
                        finish_exc.code,
                    )
                return
            logger.warning(
                "finish delivery failed address=%s code=%s", self.address, exc.code
            )

    async def _fail_or_complete(self, delivery: Any, exc: BaseException) -> None:
        from agentconnect.core.message import is_reply_expected

        reply_expected = is_reply_expected(delivery.message)
        del exc
        try:
            if reply_expected:
                await self.reply_delivery(
                    delivery,
                    outcome="failed",
                    error={
                        "code": "handler_failed",
                        "message": HANDLER_FAILURE_MESSAGE,
                    },
                )
            else:
                await self.complete_delivery(delivery)
        except SessionError as finish_exc:
            logger.warning(
                "fail delivery failed address=%s code=%s",
                self.address,
                finish_exc.code,
            )

    async def _invoke(self, op: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        method = getattr(self._transport, op)
        return await method(*args, **kwargs)

    async def _call(self, op: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return await self._invoke(op, *args, **kwargs)
        except TransportError as exc:
            if _should_reconnect(exc):
                try:
                    await asyncio.wait_for(
                        self._reconnect(),
                        timeout=self._foreground_recovery_seconds(),
                    )
                except asyncio.TimeoutError:
                    raise SessionError(
                        "unavailable",
                        "Session recovery timed out; the Runtime may already have accepted the operation",
                        retryable=True,
                    ) from exc
                if self._connected and self.session_token:
                    retry_args = (self._token(), *args[1:])
                    try:
                        return await self._invoke(op, *retry_args, **kwargs)
                    except TransportError as retry_exc:
                        raise SessionError.from_transport(retry_exc) from retry_exc
            raise SessionError.from_transport(exc) from exc

    def _foreground_recovery_seconds(self) -> float:
        timeout = getattr(self._transport, "_timeout", _DEFAULT_RECOVERY_SECONDS)
        try:
            value = float(timeout)
        except (TypeError, ValueError):
            return _DEFAULT_RECOVERY_SECONDS
        if value <= 0:
            return _DEFAULT_RECOVERY_SECONDS
        return value


_DECLINED = object()


def _handler_content(result: Any) -> Any:
    """Map a handler return value onto reply content, or _DECLINED."""
    if result is None:
        return _DECLINED
    content_attr = getattr(result, "content", None)
    kind_attr = getattr(result, "kind", None)
    if content_attr is not None and kind_attr is not None:
        return content_attr
    return result


async def _invoke_handler(agent: "BaseAgent", message: Any, ctx: Context) -> Any:
    method = agent.process_message
    if _accepts_ctx(method):
        return await method(message, ctx)
    return await method(message)


def _accepts_ctx(method: Any) -> bool:
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return True
    params = [
        param
        for param in signature.parameters.values()
        if param.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.KEYWORD_ONLY,
        )
        and param.name != "self"
    ]
    if any(param.kind == inspect.Parameter.VAR_POSITIONAL for param in params):
        return True
    names = [param.name for param in params]
    return "ctx" in names or len(params) >= 2
