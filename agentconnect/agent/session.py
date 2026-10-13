"""Internal connection owned by `BaseAgent`.

`BaseAgent.join` starts this connection. It pulls work, maps handler
results, and reconnects with the same credential and `instance_id`.
Agent code uses `BaseAgent` and `Context`.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Mapping, Optional

from agentconnect.agent.context import Context
from agentconnect.agent.errors import SessionError
from agentconnect.core.directory import DirectoryEntry, FindResult
from agentconnect.core.identity import issue_identity_proof
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
from agentconnect.core.primitives import CollectMode, DeliveryHistoryForm
from agentconnect.core.spec import SPEC_VERSION
from agentconnect.core.ticket import Ticket, parse_ticket
from agentconnect.transport.agent_http import HttpRuntimeTransport
from agentconnect.transport.inprocess import InProcessTransport
from agentconnect.transport.runtime import TransportError

if TYPE_CHECKING:
    from agentconnect.agent.base import BaseAgent

logger = logging.getLogger(__name__)

HANDLER_FAILURE_MESSAGE = "The handler failed."
"""Text stored on a Ticket when `handle` raises.

`DeferredReply.fail` stores the caller-supplied message.
"""

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
        "unsupported_version",
        "name_conflict",
        "lease_expired",
        "ticket_closed",
    }
)
_DEFAULT_RECOVERY_SECONDS = 30.0
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
    """Return an HTTP transport for a URL, or in-process for a Team object.

    Args:
        target: A started `Team`, or a Runtime origin URL.

    Returns:
        The transport `Session` will use for that target.
    """
    if isinstance(target, str):
        return HttpRuntimeTransport(target)
    return InProcessTransport(target)


def deadline_rfc3339(seconds: float) -> str:
    """Return a future UTC timestamp the Runtime will accept.

    Args:
        seconds: Offset from now.

    Returns:
        An RFC 3339 UTC timestamp with a `Z` suffix.
    """
    instant = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return instant.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class Session:
    """One running copy of an Agent connected to a Team.

    `BaseAgent.join` constructs and starts this object. Construct it
    yourself only when you need to drive the transport without
    `BaseAgent`. `target` is a started `Team` (in-process) or a Runtime
    origin URL (HTTP).

    After `start`, the Session pulls Deliveries, runs `handle`, maps
    outcomes onto `reply` / `complete`, heartbeats, and reconnects when
    the Team comes back with the same `instance_id`. Call `close` (or
    `BaseAgent.leave`) to disconnect. Membership, Mailbox, and Tickets
    remain on the Team.

    Attributes:
        instance_id: Id of this running copy.
        agent_did: DID this copy joined with.
        max_in_flight: How many Deliveries this Session may hold at once,
            including deferred replies that still hold a lease.
        delivery_history: `"bodies"` or `"ids"` for earlier Thread turns
            on each Delivery.
        address: Qualified Address after join, otherwise `None`.
        team_name: Team this copy joined, otherwise `None`.
        session_token: Live Session token, otherwise `None`.
        limits: Runtime limits reported at join.
        persistence: `"volatile"` or `"durable"` after join.
        session_expires_at: When the Session token expires, otherwise
            `None`.
    """

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
        """Bind this copy to a Team object or a Runtime URL.

        Args:
            agent: The `BaseAgent` whose `handle` this Session will run.
            target: A started `Team`, or a Runtime origin such as
                `http://127.0.0.1:9000`.
            instance_id: Id of this running copy. Two copies must not
                share this value.
            agent_did: DID presented at join.
            profile: Discovery Profile mapping sent at join.
            max_in_flight: How many Deliveries this Session may hold at
                once, including deferred replies.
            delivery_history: `"bodies"` (default) puts earlier Messages
                on each Delivery. `"ids"` puts only their ids.
        """
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
        """True while this copy holds a live Session token.

        False after `close`, and while a reconnect has not yet joined
        again.
        """
        return self._connected and not self._stopped

    async def start(self) -> "Session":
        """Join the Team and start pull, heartbeat, events, and lease renew.

        Retries while the Team is not up yet. After a disconnect, the
        Session reconnects on its own with the same `instance_id`.

        Returns:
            This Session, connected.

        Raises:
            SessionError: Join was rejected. Branch on `code`
                (`unauthorized`, `name_conflict`, and other public
                codes).
        """
        await self._connect_with_retry()
        self._supervisor = asyncio.create_task(
            self._supervise(), name=f"session:{self.instance_id}"
        )
        return self

    async def close(self, *, disconnect: bool = True) -> None:
        """Stop pull, heartbeat, and renew. Optionally disconnect the Session.

        Membership, Mailbox, and Tickets remain on the Team. Open Tickets
        stay collectable after a later `join` with the same Membership.
        This does not remove the Agent from the Team.

        Args:
            disconnect: When True (default), send disconnect for the
                current Session token. When False, stop local tasks
                without that call.
        """
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

        `collect="wait"` (default) holds until the Ticket is terminal or
        the Runtime wait hold elapses, then returns the current Ticket.
        That Ticket may still be `open`. Ending the wait does not cancel
        accepted work. Read a completed reply as `ticket.response.content`
        after checking `ticket.state`. Collect later with `get_result`.

        `collect="ticket"` returns immediately with the current Ticket.

        Called from a handler, this send sets `parent_id` to the current
        Message when you omit it. An omitted deadline inherits that
        request's stamped cutoff. An explicit `deadline_seconds` becomes
        an absolute timestamp. The Runtime rejects a child that exceeds
        the parent. Outside `handle`, omitting `thread_id` leaves the
        request unthreaded. From a handler, omitting it continues the
        current Thread when `recipient` is the other party, and otherwise
        starts a new Thread.

        Args:
            recipient: Local name or same-Team qualified Address, for
                example `writer` or `writer@content-squad`.
            content: The work, as text or JSON.
            deadline_seconds: Work cutoff in seconds. Omit to inherit a
                request parent or the Runtime work lifetime. This is not
                how long this call waits.
            collect: `"wait"` (default) holds this call. `"ticket"`
                returns immediately. Neither cancels work.
            thread_id: Continue this conversation with the same
                recipient. Omit outside `handle` for an unthreaded
                request. From a handler, omit to inherit or start as
                described above.
            parent_id: Message this send answers. From a handler, omit
                to use the current Message.
            metadata: Optional JSON object stored on the Message.
            message_id: Client-proposed Message id. Generated when
                omitted. For a request this becomes `Ticket.id`.
            deadline: Absolute RFC 3339 cutoff. When set, it is used
                instead of `deadline_seconds`.
            handling: Delivery to inherit parent, Thread, and deadline
                from. From a handler this is the current Delivery.

        Returns:
            The current Ticket. It may still be `open` when a wait ends.

        Raises:
            SessionError: The Agent is not connected, `collect` is not
                `wait` or `ticket`, or the Runtime rejected the send.
                Branch on `code`.

        Examples:
            Wait, then read a completed reply:

            ```python
            ticket = await session.ask("writer", {"task": "draft this"})
            if ticket.state == "completed":
                print(ticket.response.content)
            ```

            Continue one conversation:

            ```python
            import uuid

            thread_id = str(uuid.uuid4())
            await session.ask("writer", "outline this", thread_id=thread_id)
            await session.ask("writer", "expand section 2", thread_id=thread_id)
            ```
        """
        if collect not in ("wait", "ticket"):
            raise SessionError("invalid_request", "collect must be wait or ticket")
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
        return result.ticket

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

        Acceptance means the Runtime queued the event, not that the
        recipient finished handling it. Called from a handler, this send
        sets `parent_id` to the current Message when you omit it.

        Args:
            recipient: Local name or same-Team qualified Address.
            content: The notice, as text or JSON.
            thread_id: Continue this conversation with a current
                participant. Omit for an unthreaded notice, or to inherit
                from the current Delivery.
            parent_id: Message this send answers. From a handler, omit
                to use the current Message.
            metadata: Optional JSON object stored on the Message.
            message_id: Client-proposed Message id. Generated when
                omitted.
            handling: Delivery to inherit parent and Thread from. From a
                handler this is the current Delivery.

        Returns:
            An acknowledgement that the event was accepted.

        Raises:
            SessionError: The Agent is not connected, or the Runtime
                rejected the send.

        Examples:
            ```python
            await session.tell("writer", {"note": "source changed"})
            ```
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

    async def find(self, query: str, *, limit: int | None = None) -> FindResult:
        """Search this Team's Directory, excluding this Agent.

        Light cards include Address, summary, Skill names, and Profile
        tags. Ranked matches are candidates, not proof of suitability.
        Call `get_entry` for one full Profile.

        Args:
            query: Natural-language description of the work.
            limit: Maximum matches from 1 to 100. Omit to receive every
                other member, at most 100.

        Returns:
            Ranked matches, best first.

        Raises:
            SessionError: The Agent is not connected.

        Examples:
            ```python
            found = await session.find("someone who can draft a summary")
            found.matches[0].address
            ```
        """
        return FindResult.model_validate(
            await self._call(
                "find",
                self._token(),
                query,
                limit=limit,
            )
        )

    async def get_entry(self, address: str) -> DirectoryEntry:
        """Return one Directory entry (Address, DID, and Profile).

        Args:
            address: Local name or same-Team qualified Address.

        Returns:
            The Directory record for that Membership.

        Raises:
            SessionError: The Agent is not connected, or no such member
                exists.

        Examples:
            ```python
            entry = await session.get_entry("writer")
            entry.profile.summary
            ```
        """
        return DirectoryEntry.model_validate(
            await self._call("get_profile", self._token(), address)
        )

    async def get_result(self, ticket_id: str) -> Ticket:
        """Return the current Ticket this Membership opened.

        Repeatable. Does not consume the result. If `state` is `open`,
        call again with the same id. Do not send another `ask`. The
        Ticket includes the request `trace_id`.

        Args:
            ticket_id: `Ticket.id` from `ask`, equal to the request
                Message id.

        Returns:
            The current Ticket, which may still be `open`.

        Raises:
            SessionError: The Agent is not connected, or this Membership
                did not open that Ticket.

        Examples:
            ```python
            pending = await session.ask("writer", "long job", collect="ticket")
            ticket = await session.get_result(pending.id)
            if ticket.state == "completed":
                ticket.response.content
            ```
        """
        return parse_ticket(await self._call("get_result", self._token(), ticket_id))

    async def get_history(
        self,
        thread_id: str,
        *,
        before: Optional[str] = None,
        limit: int = 50,
    ) -> HistoryResult:
        """Return one page of retained Thread history, ordered by `seq`.

        The newest page is first; turns inside a page are oldest to
        newest. Omit `before` for the newest page. A UUID that is not
        in the transcript, including one retention has removed, returns
        that newest page. Only a participant may read the Thread.

        Args:
            thread_id: Conversation id from a Ticket or Message.
            before: Return Messages older than this id. Prefer
                `next_before` from the previous page.
            limit: Page size from 1 to 200. Defaults to 50.

        Returns:
            One page. When `has_more` is true, pass `next_before` as
            the next `before`.

        Raises:
            SessionError: The Agent is not connected, or is not a
                participant.

        Examples:
            ```python
            page = await session.get_history(thread_id)
            if page.has_more:
                older = await session.get_history(
                    thread_id, before=page.next_before
                )
            ```
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

    async def complete_delivery(
        self, delivery: Delivery | Mapping[str, Any]
    ) -> dict[str, Any]:
        """Finish a Delivery without a response Message.

        Use this to decline a request, or to finish an event. Prefer
        `DeferredReply.decline` from a handler. A declined Ticket is not
        a failure.

        Args:
            delivery: The leased Delivery, or a mapping with `lease_id`.

        Returns:
            The Runtime acknowledgement for this complete.

        Raises:
            SessionError: The Session is not connected, the lease
                expired, or the Ticket is already closed.
        """
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
        delivery: Delivery | Mapping[str, Any],
        *,
        outcome: str,
        content: Any = None,
        error: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Finish a leased reply-expected Delivery.

        Prefer `DeferredReply.reply` or `DeferredReply.fail` from a
        handler. `outcome="completed"` stores `content` as the reply.
        Any other `outcome` stores a failure. `None` is valid content.

        Args:
            delivery: The leased Delivery, or a mapping with `lease_id`.
            outcome: `"completed"` to reply, or another value to fail.
            content: Reply body when `outcome` is `"completed"`.
            error: Failure object when `outcome` is not `"completed"`.
                When omitted, the stored error is `handler_failed` with
                message `failed`. Uncaught `handle` exceptions store
                `The handler failed.` instead.

        Returns:
            The Runtime acknowledgement for this reply.

        Raises:
            SessionError: The Session is not connected, the lease
                expired, or the Ticket is already closed.
        """
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
        """Return the Delivery this Session is handling in this task, if any.

        `None` when this task is not inside `handle` for this Session.
        Tool helpers use this to inherit parent and Thread from the
        current Delivery.
        """
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
            body["identity_proof"] = issue_identity_proof(
                self._agent.identity, challenge
            )
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
                result = await self._agent.handle(message, ctx)
            except Exception as exc:
                logger.exception(
                    "handler failed address=%s message_id=%s",
                    self.address,
                    message.id,
                )
                await self._fail_or_complete(parsed, exc)
                return
            if ctx._deferred is not None:
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
                    # asyncio.timeout keeps reconnect on this task. wait_for()
                    # on 3.11 wraps it in a new Task, so current_task() inside
                    # _reconnect is not the handler and _abandon_sdk_handlers
                    # cancels the caller.
                    async with asyncio.timeout(self._foreground_recovery_seconds()):
                        await self._reconnect()
                except TimeoutError:
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
