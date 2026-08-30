"""Session-bound callables for frameworks that do not speak MCP.

A model calls tools. ``team_tools()`` is find, ask, tell, get_result, and
get_history bound to this Agent's Session. Wire them into LangGraph, ADK, or
any other tool loop. The Team MCP server is the other door, for clients that
speak MCP.

    class Researcher(BaseAgent):
        def __init__(self, name: str):
            super().__init__(name=name)
            self.tools = self.team_tools()

        async def process_message(self, msg, ctx):
            found = await self.tools.find(query=str(msg["content"]))
            peer = found["matches"][0]["address"]
            ticket = await self.tools.ask(
                recipient=peer,
                content=msg["content"],
                deadline_seconds=30,
                wait_seconds=10,
            )
            return ticket

Callables look up the Session at call time, so ``self.team_tools()`` is safe
in ``__init__`` before ``join``.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Optional

from agentconnect.agent.errors import SessionError
from agentconnect.agent.session import Session

_FIND_PARAMS = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Natural-language need, 1 to 1000 characters.",
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
            "description": "Maximum matches. Omit to receive every other member.",
        },
        "detail": {
            "type": "string",
            "enum": ["summary", "full"],
            "description": "summary (default) or full.",
        },
    },
    "required": ["query"],
}

_ASK_PARAMS = {
    "type": "object",
    "properties": {
        "recipient": {
            "type": "string",
            "description": "Local Address, for example writer.",
        },
        "content": {"description": "The work, text or JSON."},
        "deadline_seconds": {
            "type": "integer",
            "minimum": 1,
            "maximum": 86400,
            "description": "How long the recipient has.",
        },
        "wait_seconds": {
            "type": "integer",
            "minimum": 0,
            "maximum": 30,
            "description": "Local wait before returning the current Ticket. Default 0.",
        },
        "thread_id": {
            "type": "string",
            "description": "Continue this conversation. Omit to start a new one.",
        },
        "idempotency_key": {
            "type": "string",
            "minLength": 1,
            "maxLength": 200,
            "description": "Stable key so a retry does not create a second request.",
        },
    },
    "required": ["recipient", "content", "deadline_seconds"],
}

_TELL_PARAMS = {
    "type": "object",
    "properties": {
        "recipient": {
            "type": "string",
            "description": "Local Address, for example writer.",
        },
        "content": {"description": "The event, text or JSON."},
        "thread_id": {"type": "string", "description": "Continue this conversation."},
        "idempotency_key": {
            "type": "string",
            "minLength": 1,
            "maxLength": 200,
        },
    },
    "required": ["recipient", "content"],
}

_GET_RESULT_PARAMS = {
    "type": "object",
    "properties": {
        "ticket_id": {
            "type": "string",
            "description": "Ticket id from ask. Equal to the request Message id.",
        }
    },
    "required": ["ticket_id"],
}

_GET_HISTORY_PARAMS = {
    "type": "object",
    "properties": {
        "thread_id": {
            "type": "string",
            "description": "Conversation id from a Ticket.",
        },
        "before": {
            "type": "string",
            "description": "Oldest Message id already seen. Omit for the newest page.",
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": 200,
            "description": "Page size. Defaults to 50.",
        },
    },
    "required": ["thread_id"],
}


@dataclass(frozen=True)
class TeamTool:
    """One Session-bound callable with a JSON Schema the host can advertise.

    tools = agent.team_tools()
    ask = next(t for t in tools if t.name == "ask")
    ticket = await ask(
        recipient="writer", content="draft this", deadline_seconds=30
    )
    """

    name: str
    description: str
    parameters: dict[str, Any]
    coroutine: Callable[..., Awaitable[dict[str, Any]]]

    async def __call__(self, **kwargs: Any) -> dict[str, Any]:
        """Run this tool with the advertised parameter names."""
        return await self.coroutine(**kwargs)


class TeamTools(Sequence[TeamTool]):
    """find, ask, tell, get_result, and get_history bound to one Session.

    ``ask`` matches the MCP tool: ``collect=ticket``, a minted Thread when
    ``thread_id`` is omitted, and ``wait_seconds`` for a short local wait.
    """

    def __init__(self, session_getter: Callable[[], Session]) -> None:
        """Bind to a getter so tools can be built before ``join``."""
        self._session_getter = session_getter
        self._items = (
            TeamTool(
                name="find",
                description=(
                    "Find teammates by describing the work you need. Returns ranked "
                    "matches. Omit limit to receive every other member, at most 100."
                ),
                parameters=_FIND_PARAMS,
                coroutine=self.find,
            ),
            TeamTool(
                name="ask",
                description=(
                    "Send reply-expected work. Returns a Ticket. Keep ticket.id and "
                    "pass it to get_result if the Ticket is still open."
                ),
                parameters=_ASK_PARAMS,
                coroutine=self.ask,
            ),
            TeamTool(
                name="tell",
                description=(
                    "Send an event. No reply is expected and no Ticket is created."
                ),
                parameters=_TELL_PARAMS,
                coroutine=self.tell,
            ),
            TeamTool(
                name="get_result",
                description=(
                    "Return the current Ticket. Repeatable. Does not consume the result."
                ),
                parameters=_GET_RESULT_PARAMS,
                coroutine=self.get_result,
            ),
            TeamTool(
                name="get_history",
                description=(
                    "Return one page of retained Thread history, newest page first."
                ),
                parameters=_GET_HISTORY_PARAMS,
                coroutine=self.get_history,
            ),
        )

    def _session(self) -> Session:
        return self._session_getter()

    def __len__(self) -> int:
        """Return how many tools this sequence holds."""
        return len(self._items)

    def __getitem__(self, index: int) -> TeamTool:  # type: ignore[override]
        """Return the tool at ``index``."""
        return self._items[index]

    def __iter__(self) -> Iterator[TeamTool]:
        """Iterate the five Session-bound tools."""
        return iter(self._items)

    async def find(
        self,
        query: str,
        *,
        limit: int | None = None,
        detail: str = "summary",
    ) -> dict[str, Any]:
        """Search this Team's Directory, excluding this Agent.

        found = await tools.find(query="someone who can draft a summary")
        found["matches"][0]["address"]
        """
        return await self._session().find(query, limit=limit, detail=detail)

    async def ask(
        self,
        recipient: str,
        content: Any,
        deadline_seconds: int,
        wait_seconds: int = 0,
        thread_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send reply-expected work and return a Ticket.

        Same contract as the MCP ``ask`` tool. ``wait_seconds`` may hold for a
        terminal Ticket. An omitted ``thread_id`` starts a new conversation.

            ticket = await tools.ask(
                recipient="writer",
                content={"task": "draft this"},
                deadline_seconds=30,
                wait_seconds=10,
            )
        """
        session = self._session()
        address = session.address
        if not address:
            raise SessionError("unauthorized", "Agent has not joined a Team")
        message_id = _message_id(
            "ask",
            address,
            idempotency_key=idempotency_key,
        )
        send_thread = thread_id or str(uuid.uuid4())
        try:
            result = await session.ask(
                recipient,
                content,
                deadline_seconds=float(deadline_seconds),
                collect="ticket",
                thread_id=send_thread,
                message_id=message_id,
            )
        except SessionError as exc:
            if exc.code == "id_conflict" and idempotency_key:
                return await _wait_for_ticket(session, message_id, int(wait_seconds))
            raise
        ticket = result.get("ticket")
        if not isinstance(ticket, dict) or not isinstance(ticket.get("id"), str):
            raise SessionError("internal", "ask did not return a Ticket")
        if int(wait_seconds) <= 0:
            return ticket
        return await _wait_for_ticket(session, ticket["id"], int(wait_seconds))

    async def tell(
        self,
        recipient: str,
        content: Any,
        thread_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send an event. No Ticket is created."""
        session = self._session()
        address = session.address
        if not address:
            raise SessionError("unauthorized", "Agent has not joined a Team")
        message_id = _message_id(
            "tell",
            address,
            idempotency_key=idempotency_key,
        )
        try:
            return await session.tell(
                recipient,
                content,
                thread_id=thread_id,
                message_id=message_id,
            )
        except SessionError as exc:
            if exc.code == "id_conflict" and idempotency_key:
                return {
                    "status": "accepted",
                    "message": {"id": message_id, "kind": "event"},
                }
            raise

    async def get_result(self, ticket_id: str) -> dict[str, Any]:
        """Return the current Ticket this Agent opened."""
        return await self._session().get_result(ticket_id)

    async def get_history(
        self,
        thread_id: str,
        *,
        before: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return one page of retained Thread history."""
        return await self._session().get_history(thread_id, before=before, limit=limit)


def bind_team_tools(session: Session) -> TeamTools:
    """Return Team tools bound to an already-connected Session."""
    return TeamTools(lambda: session)


def _message_id(
    kind: str, caller_address: str, *, idempotency_key: Optional[str]
) -> str:
    if idempotency_key:
        material = f"{kind}|{caller_address}|{idempotency_key}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"agentconnect:{material}"))
    return str(uuid.uuid4())


async def _wait_for_ticket(
    session: Session, ticket_id: str, wait_seconds: int
) -> dict[str, Any]:
    deadline = time.monotonic() + float(wait_seconds)
    while True:
        ticket = await session.get_result(ticket_id)
        if ticket.get("state") != "open":
            return ticket
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return ticket
        await asyncio.sleep(min(0.05, remaining))
