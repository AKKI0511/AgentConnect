"""Handler Context: delivery facts plus verbs to call teammates mid-handling.

A handler receives ``(msg, ctx)``. ``msg`` is the delivered Message.
``ctx`` carries verified facts about this Delivery and the methods
to ask, tell, find, page history, or take a Ticket and answer later.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Optional

from agentconnect.core.message import Delivery, MailboxMessage, Message
from agentconnect.core.operations import AcceptedSendResult, TicketedSendResult

if TYPE_CHECKING:
    from agentconnect.agent.session import CollectMode, Session


class TicketHandle:
    """Answer a reply-expected Delivery after ``process_message`` returns.

    The Delivery stays leased until ``reply``, ``fail``, or ``decline``
    succeeds, or the lease expires and another Instance may take it.
    """

    def __init__(self, session: "Session", delivery: Delivery) -> None:
        """Hold the Session and Delivery this handle will finish."""
        self._session = session
        self._delivery = delivery
        self._done = False

    @property
    def lease_id(self) -> str:
        """Lease authorizing this attempt."""
        return self._delivery.lease_id

    @property
    def message_id(self) -> str:
        """Id of the delivered Message, and of its Ticket when one exists."""
        return self._delivery.message.id

    async def reply(self, content: Any = None) -> dict[str, Any]:
        """Complete the request with ``content`` (JSON). ``None`` is valid content."""
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
        """Fail the request with a safe error the requester can see.

        ``code`` is ``handler_failed`` unless the caller passes another
        well-known code. An Agent application code belongs in ``details``.
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
        """Decline a request, or finish an event."""
        self._ensure_open()
        result = await self._session.complete_delivery(self._delivery)
        self._done = True
        return result

    def _ensure_open(self) -> None:
        if self._done:
            raise RuntimeError("This Delivery has already been finished")


class Context:
    """Facts about the current Delivery, plus verbs to talk to the Team.

    When several Instances share one Membership they pull one Mailbox.
    Working state that lives only in this process is lost if another
    Instance handles the next turn. Use ``history`` (and ``get_history``
    for older turns) as the source of conversation state.
    """

    def __init__(
        self,
        session: "Session",
        delivery: Delivery,
        *,
        sender_did: str,
        origin: str,
        external: bool = False,
    ) -> None:
        """Attach delivery facts from one leased attempt."""
        self._session = session
        self._delivery = delivery
        self._ticket: Optional[TicketHandle] = None
        self.sender_did = sender_did
        self.origin = origin
        self.external = external

    @property
    def message(self) -> MailboxMessage:
        """The delivered Runtime Message."""
        return self._delivery.message

    @property
    def attempt(self) -> int:
        """Delivery attempt number. At-least-once handling can repeat work."""
        return self._delivery.attempt

    @property
    def lease_id(self) -> str:
        """Lease authorizing completion of this attempt."""
        return self._delivery.lease_id

    @property
    def deadline(self) -> Optional[str]:
        """Request deadline, or None for an event."""
        message = self._delivery.message
        return getattr(message, "deadline", None)

    @property
    def trace_id(self) -> str:
        """Causal id shared by this exchange."""
        return self._delivery.message.trace_id

    @property
    def thread_id(self) -> Optional[str]:
        """Thread grouping id, when the Message belongs to one."""
        return self._delivery.message.thread_id

    @property
    def history(self) -> list[Message]:
        """Bounded recent Thread window, excluding the delivered Message.

        Use this as conversation state. Older turns are on
        :meth:`get_history` when ``history_complete`` is False.
        """
        return list(self._delivery.history)

    @property
    def history_ids(self) -> Optional[list[str]]:
        """Earlier Message ids when this Session joined with ``delivery_history="ids"``.

        ``None`` when the Delivery carries Message bodies. Page those
        ids with :meth:`get_history` when you need the bodies.

            ctx.history_ids
            page = await ctx.get_history()
        """
        ids = self._delivery.history_ids
        if ids is None:
            return None
        return list(ids)

    @property
    def history_complete(self) -> bool:
        """True when ``history`` already contains every earlier retained Message."""
        return self._delivery.history_complete

    @property
    def ticket_taken(self) -> bool:
        """True after ``ticket()``; the Session will not auto-complete this Delivery."""
        return self._ticket is not None

    def ticket(self) -> TicketHandle:
        """Keep the Delivery leased and answer later.

        Return from ``process_message`` after calling this. Reply with
        ``handle.reply``, ``handle.fail``, or ``handle.decline``.
        """
        if self._ticket is None:
            self._ticket = TicketHandle(self._session, self._delivery)
        return self._ticket

    async def ask(
        self,
        recipient: str,
        content: Any,
        *,
        deadline_seconds: float = 30.0,
        collect: CollectMode = "wait",
        thread_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> TicketedSendResult:
        """Send a reply-expected request and collect the result.

        Same contract as :meth:`agentconnect.agent.base.BaseAgent.ask`.
        """
        return await self._session.ask(
            recipient,
            content,
            deadline_seconds=deadline_seconds,
            collect=collect,
            thread_id=thread_id,
            parent_id=parent_id,
            metadata=metadata,
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
        """Send an event.

        Same contract as :meth:`agentconnect.agent.base.BaseAgent.tell`.
        """
        return await self._session.tell(
            recipient,
            content,
            thread_id=thread_id,
            parent_id=parent_id,
            metadata=metadata,
        )

    async def find(
        self, query: str, *, limit: int | None = None, detail: str = "summary"
    ) -> dict[str, Any]:
        """Search this Team's Directory, excluding this Agent.

        found = await ctx.find("someone who can review a contract")
        peer = found["matches"][0]["address"]
        """
        return await self._session.find(query, limit=limit, detail=detail)

    async def get_profile(self, address: str) -> dict[str, Any]:
        """Return the Directory entry for ``address`` in this Team."""
        return await self._session.get_profile(address)

    async def get_history(
        self, *, before: Optional[str] = None, limit: int = 50
    ) -> dict[str, Any]:
        """Page older retained Thread history.

        Omit ``before`` for the newest page of this Delivery's Thread.
        Returns empty history when the Message has no ``thread_id``.
        """
        from agentconnect.core.operations import HistoryResult

        thread_id = self.thread_id
        if thread_id is None:
            return HistoryResult(messages=[], has_more=False)
        return await self._session.get_history(thread_id, before=before, limit=limit)
