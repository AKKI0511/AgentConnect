"""Delivery context and handles for replies sent after `handle` returns."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Optional

from agentconnect.core.message import Delivery, MailboxMessage, Message
from agentconnect.core.operations import AcceptedSendResult, HistoryResult
from agentconnect.core.primitives import CollectMode
from agentconnect.core.ticket import Ticket

if TYPE_CHECKING:
    from agentconnect.agent.session import Session


class DeferredReply:
    """Handle that finishes one request after `handle` returns.

    Obtain it from `Context.defer`, then finish once with `reply`,
    `fail`, or `decline`. The Delivery remains leased and counts
    toward `max_in_flight`. The lease is renewed until completion,
    the request deadline, a disconnect, or revocation by the Team.
    If it expires, another running copy may handle the Delivery.
    """

    def __init__(self, session: "Session", delivery: Delivery) -> None:
        """Bind one leased Delivery. Call `Context.defer` instead."""
        self._session = session
        self._delivery = delivery
        self._done = False

    @property
    def lease_id(self) -> str:
        """Lease that authorizes this attempt."""
        return self._delivery.lease_id

    @property
    def message_id(self) -> str:
        """Id of the delivered Message. For a request, this is also the Ticket id."""
        return self._delivery.message.id

    async def reply(self, content: Any = None) -> dict[str, Any]:
        """Complete the request with `content`.

        `None` is a valid reply body.

        Args:
            content: Reply body, as text or JSON. Defaults to `None`.

        Returns:
            The Team acknowledgement for this reply.

        Raises:
            RuntimeError: This handle already finished the Delivery.
            SessionError: The Session is disconnected, the lease expired,
                or the Ticket is already closed.
        """
        self._ensure_open()
        result = await self._session.reply_delivery(
            self._delivery, outcome="completed", content=content
        )
        self._done = True
        return result

    async def fail(
        self,
        message: str,
        *,
        code: str = "handler_failed",
        details: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Fail the request with a message the requester can read.

        The Ticket error code is `handler_failed`. This call stores
        `message` as the error text. A different `code` is stored under
        `details`, and the public code stays `handler_failed`. Put an
        application-specific code in `details` as well. An exception
        raised from `handle` stores `The handler failed.` instead of
        the exception text.

        Args:
            message: Text the requester can read.
            code: Extra code stored in `details` when it is not
                `handler_failed`.
            details: JSON object stored on the error. Omit to store none.

        Returns:
            The Team acknowledgement for this failed reply.

        Raises:
            RuntimeError: This handle already finished the Delivery.
            SessionError: The Session is disconnected, the lease expired,
                or the Ticket is already closed.
        """
        self._ensure_open()
        extra = dict(details or {})
        error: dict[str, Any] = {"code": "handler_failed", "message": message}
        if code != "handler_failed":
            extra.setdefault("code", code)
        if extra:
            error["details"] = extra
        result = await self._session.reply_delivery(
            self._delivery,
            outcome="failed",
            error=error,
        )
        self._done = True
        return result

    async def decline(self) -> dict[str, Any]:
        """Decline a request, or finish an event without a reply.

        A declined Ticket is a finished result. It is not a failure, and
        it has no reply body.

        Returns:
            The Team acknowledgement for this completion.

        Raises:
            RuntimeError: This handle already finished the Delivery.
            SessionError: The Session is disconnected, the lease expired,
                or the Ticket is already closed.
        """
        self._ensure_open()
        result = await self._session.complete_delivery(self._delivery)
        self._done = True
        return result

    def _ensure_open(self) -> None:
        """Reject a second finish on this handle."""
        if self._done:
            raise RuntimeError("This Delivery has already been finished")


class Context:
    """Inspect the incoming Message and contact teammates while handling it.

    `handle` receives this object. Use `sender` to identify the teammate,
    `history` to read recent conversation Messages, and `ask` or `tell`
    to send related work. `get_history` reads older conversation turns.
    """

    def __init__(
        self,
        session: "Session",
        delivery: Delivery,
    ) -> None:
        """Attach one leased Delivery. The Session builds this for `handle`."""
        self._session = session
        self._delivery = delivery
        self._deferred: Optional[DeferredReply] = None

    @property
    def sender(self) -> str:
        """Address of the Membership that sent this Message."""
        return str(self._delivery.message.sender)

    @property
    def sender_did(self) -> str:
        """DID of the sender, recorded when the Team accepted the Message.

        A later leave, or another Agent reusing the Address, leaves this
        value unchanged.
        """
        return str(self._delivery.message.sender_did)

    @property
    def message(self) -> MailboxMessage:
        """The delivered request or event."""
        return self._delivery.message

    @property
    def attempt(self) -> int:
        """Delivery attempt number. The first attempt is 1.

        At-least-once delivery can run `handle` more than once for the
        same Message.
        """
        return self._delivery.attempt

    @property
    def lease_id(self) -> str:
        """Lease that authorizes completion of this attempt."""
        return self._delivery.lease_id

    @property
    def deadline(self) -> Optional[str]:
        """Request deadline as an RFC 3339 timestamp. `None` for an event."""
        message = self._delivery.message
        return getattr(message, "deadline", None)

    @property
    def trace_id(self) -> str:
        """Id shared by this Message and Messages sent while handling it."""
        return self._delivery.message.trace_id

    @property
    def thread_id(self) -> Optional[str]:
        """Thread id when the Message belongs to a conversation. Otherwise `None`."""
        return self._delivery.message.thread_id

    @property
    def history(self) -> list[Message]:
        """Recent Thread Messages, excluding the Message being handled.

        The list is ordered by `seq`. Use it as the conversation state.
        When `history_complete` is false, page older turns with
        `get_history`. After `join` with `delivery_history="ids"`, this
        list is empty and `history_ids` holds the earlier ids.
        """
        return list(self._delivery.history)

    @property
    def history_ids(self) -> Optional[list[str]]:
        """Earlier Message ids when this Session joined with `delivery_history="ids"`.

        `None` when the Delivery already carries Message bodies. Call
        `get_history` for those bodies.
        """
        ids = self._delivery.history_ids
        if ids is None:
            return None
        return list(ids)

    @property
    def history_complete(self) -> bool:
        """True when `history` already holds every earlier retained Message."""
        return self._delivery.history_complete

    def defer(self) -> DeferredReply:
        """Keep this Delivery leased and answer after `handle` returns.

        Return from `handle` after this call; its return value is ignored.
        Give the returned `DeferredReply` to your existing completion
        workflow, which must finish it with `reply`, `fail`, or `decline`.

        Returns:
            The handle for this Delivery. Another `defer` call returns the same object.

        Examples:
            Within an existing request handler, `ctx` is the incoming
            delivery's Context. Save the handle for your completion workflow.

            ```python
            pending = ctx.defer()
            ```

            In that workflow's async completion callback, `pending` is
            the saved handle and `draft` is the finished result.

            ```python
            await pending.reply(draft)
            ```
        """
        if self._deferred is None:
            self._deferred = DeferredReply(self._session, self._delivery)
        return self._deferred

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
    ) -> Ticket:
        """Send a request from `handle` and return a `Ticket`.

        The returned Ticket may still be `open`. Accepted work keeps
        running after this call returns.

        Read `content` only when `state` is `completed`. Call
        `BaseAgent.get_result` with `id` while `state` is `open`.
        An open child does not finish the incoming request. Returning
        `None` from `handle` declines it. Use `defer` if your handler
        must return before it can reply.

        Args:
            recipient: Local name or same-Team Address, such as `writer`
                or `writer@content-squad`.
            content: The work, as text or JSON.
            deadline_seconds: Work cutoff in seconds. This does not change
                how long `collect="wait"` waits. Omit it to inherit the
                parent request deadline. The Team rejects a later child
                deadline.
            collect: `wait` waits until the Ticket is terminal or
                `wait_hold_seconds` elapses. `ticket` returns the current
                Ticket without waiting.
            thread_id: Thread to continue with the same recipient. Omit it
                to continue the current Thread when `recipient` is the
                sender and this Message has a `thread_id`. Otherwise a
                new Thread starts.
            parent_id: Message this request answers. Omit it to use the
                current Message id.
            metadata: JSON object stored on the Message. Omit to store none.

        Returns:
            The current Ticket. It can still be `open`.

        Raises:
            SessionError: The Agent has not joined, or the Team rejected
                the send. Read `code`.

        Examples:
            Within an existing handler, `ctx` belongs to the incoming
            request and `draft` is text to review. This fragment inspects
            a child Ticket; the handler still needs to finish its
            incoming request.

            ```python
            ticket = await ctx.ask(
                "editor",
                {"task": "Check for unsupported claims.", "draft": draft},
                collect="ticket",
            )
            if ticket.state == "completed":
                print(ticket.content)
            ```
        """
        return await self._session.ask(
            recipient,
            content,
            deadline_seconds=deadline_seconds,
            collect=collect,
            thread_id=thread_id,
            parent_id=parent_id,
            metadata=metadata,
            handling=self._delivery,
        )

    async def tell(
        self,
        recipient: str,
        content: Any,
        *,
        thread_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> AcceptedSendResult:
        """Send a notice from `handle`. No Ticket is created.

        Acceptance means the Team queued the event. It does not mean the
        recipient finished handling it. Omit `parent_id` to use the
        current Message id. Omit `thread_id` to continue or start a
        Thread by the same rule as `ask`.

        Args:
            recipient: Local name or same-Team Address.
            content: The notice, as text or JSON.
            thread_id: Thread to continue with a current participant.
                Omit it to continue or start a Thread by the same rule
                as `ask`.
            parent_id: Message this notice answers. Omit it to use the
                current Message id.
            metadata: JSON object stored on the Message. Omit to store none.

        Returns:
            An acknowledgement that the Team accepted the event.

        Raises:
            SessionError: The Agent has not joined, or the Team rejected
                the send. Read `code`.
        """
        return await self._session.tell(
            recipient,
            content,
            thread_id=thread_id,
            parent_id=parent_id,
            metadata=metadata,
            handling=self._delivery,
        )

    async def get_history(
        self, *, before: Optional[str] = None, limit: int = 50
    ) -> HistoryResult:
        """Return one page of this Delivery's Thread history.

        The first page is the newest. Messages inside a page run from
        oldest to newest. Omit `before` for that newest page. A `before`
        id missing from the transcript returns that same page. The result
        is empty when this Message has no `thread_id`.

        Args:
            before: Return Messages older than this id. Use `next_before`
                from the previous page.
            limit: Page size, from 1 to 200. Defaults to 50.

        Returns:
            One page. Pass `next_before` as `before` when `has_more` is true.

        Raises:
            SessionError: The Agent has not joined, or is not a participant.
        """
        thread_id = self.thread_id
        if thread_id is None:
            return HistoryResult(messages=[], has_more=False)
        return await self._session.get_history(thread_id, before=before, limit=limit)
