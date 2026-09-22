"""Session-bound callables for frameworks that do not speak MCP.

A model calls tools. ``team_tools()`` is find, ask, tell, get_result,
get_history, and get_profile bound to this Agent's Session. Results are
JSON via :func:`~agentconnect.core.base.dump_public`. Wire them into
LangGraph, ADK, or any other tool loop. The Team MCP server is the other
door, for clients that speak MCP.

A developer registers a tool by passing a plain annotated function, or an
explicit :class:`Tool` when annotations cannot express the schema.

    class Researcher(BaseAgent):
        def __init__(self, name: str):
            super().__init__(name=name)
            self.tools = self.team_tools()

        async def handle(self, msg, ctx):
            found = await self.tools.find(query=str(msg.content))
            peer = found["matches"][0]["address"]
            ticket = await self.tools.ask(
                recipient=peer,
                content=msg.content,
            )
            if ticket["state"] == "completed":
                return ticket["content"]
            ctx.defer()
            return None

Callables look up the Session at call time, so ``self.team_tools()`` is safe
in ``__init__`` before ``join``. ``ask`` and ``tell`` share their argument
names with :meth:`~agentconnect.agent.base.BaseAgent.ask` and
:meth:`~agentconnect.agent.base.BaseAgent.tell`. Tools also accept
``idempotency_key`` and mint a Thread when ``thread_id`` is omitted.
"""

from __future__ import annotations

import inspect
import json
import re
import uuid
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Optional, Union, get_type_hints

from pydantic import Field, create_model
from typing_extensions import Annotated

from agentconnect.agent.errors import SessionError
from agentconnect.agent.session import Session
from agentconnect.core.base import dump_public, public_json_schema
from agentconnect.core.directory import FindRequest, GetProfileRequest
from agentconnect.core.operations import (
    AskToolRequest,
    GetHistoryRequest,
    GetResultRequest,
    TellToolRequest,
)
from agentconnect.core.primitives import CollectMode
from agentconnect.core.ticket import ticket_view

ToolHandler = Callable[..., Union[Any, Awaitable[Any]]]
ToolLike = Union["Tool", ToolHandler]

_FIND_PARAMS = public_json_schema(FindRequest)

_ASK_PARAMS = public_json_schema(AskToolRequest)
_TELL_PARAMS = public_json_schema(TellToolRequest)
_GET_RESULT_PARAMS = public_json_schema(GetResultRequest)
_GET_HISTORY_PARAMS = public_json_schema(GetHistoryRequest)
_GET_PROFILE_PARAMS = public_json_schema(GetProfileRequest)

_ASK_DESCRIPTION = (
    "Send work that needs a reply. Returns a TicketView. Keep ticket_id and "
    "pass it to get_result while the Ticket is open. Prefer this over tell "
    "when you need an answer; tell does not create a Ticket."
)

_TELL_DESCRIPTION = (
    "Send work that does not need a reply. Does not create a Ticket, so a "
    "caller that needed an answer gets none and no error from tell itself. "
    "Prefer ask when you need a reply."
)


@dataclass(frozen=True)
class Tool:
    """One function the model may call.

    Pass a plain annotated function to :meth:`from_callable` to derive the
    JSON Schema from the signature and docstring. Construct ``Tool``
    directly when annotations cannot express the schema.

        async def search_docs(query: str) -> str:
            \"\"\"Search internal docs.

            Args:
                query: The search text.
            \"\"\"
            return f"no hits for {query}"

        Tool.from_callable(search_docs)
    """

    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    params_model: Any = None

    @classmethod
    def from_callable(
        cls,
        fn: ToolHandler,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Tool:
        """Build a Tool from an annotated function and its docstring."""
        tool_name = name or getattr(fn, "__name__", "tool")
        doc = inspect.getdoc(fn) or ""
        tool_description = (
            description if description is not None else _description_from_doc(doc)
        )
        parameters, params_model = _parameters_from_callable(fn, doc)
        return cls(
            name=tool_name,
            description=tool_description or tool_name,
            parameters=parameters,
            handler=fn,
            params_model=params_model,
        )

    def openai_schema(self) -> dict[str, Any]:
        """Return the OpenAI/LiteLLM function-tool descriptor for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _ensure_tool(value: ToolLike) -> Tool:
    """Return ``value`` as a :class:`Tool`, deriving schema from a callable."""
    if isinstance(value, Tool):
        return value
    if callable(value):
        return Tool.from_callable(value)
    raise TypeError("tool must be a Tool or a callable")


async def _call_tool(tool: Tool, arguments: Mapping[str, Any] | str) -> str:
    """Call ``tool.handler`` once with the advertised names as keywords.

    A callable registered from annotations is validated with its Pydantic
    parameter model first, so a model annotation receives that model instance.
    """
    parsed = _parse_arguments(arguments)
    if tool.params_model is not None:
        validated = tool.params_model.model_validate(parsed)
        parsed = {
            name: getattr(validated, name) for name in tool.params_model.model_fields
        }
    result = tool.handler(**parsed)
    if inspect.isawaitable(result):
        result = await result
    return _stringify(result)


class TeamTools(Sequence[Tool]):
    """find, ask, tell, get_result, get_history, and get_profile for one Session.

    ``ask`` matches :meth:`~agentconnect.agent.base.BaseAgent.ask` and the
    MCP ``ask`` tool. Model-facing ask/get_result results are TicketView JSON.
    """

    def __init__(self, session_getter: Callable[[], Session]) -> None:
        """Bind to a getter so tools can be built before ``join``."""
        self._session_getter = session_getter
        self._items = (
            Tool(
                name="find",
                description=(
                    "Find teammates by describing the work you need. Returns ranked "
                    "matches. Omit limit to receive every other member, at most 100. "
                    "Use get_profile to read one match in full."
                ),
                parameters=_FIND_PARAMS,
                handler=self.find,
            ),
            Tool(
                name="ask",
                description=_ASK_DESCRIPTION,
                parameters=_ASK_PARAMS,
                handler=self.ask,
            ),
            Tool(
                name="tell",
                description=_TELL_DESCRIPTION,
                parameters=_TELL_PARAMS,
                handler=self.tell,
            ),
            Tool(
                name="get_result",
                description=(
                    "Return the current TicketView. Repeatable. Does not consume "
                    "the result. Pass ticket_id from ask."
                ),
                parameters=_GET_RESULT_PARAMS,
                handler=self.get_result,
            ),
            Tool(
                name="get_history",
                description=(
                    "Return one page of retained Thread history, newest page first."
                ),
                parameters=_GET_HISTORY_PARAMS,
                handler=self.get_history,
            ),
            Tool(
                name="get_profile",
                description=(
                    "Return one teammate's full Directory entry by Address. Prefer "
                    "this over find(detail=full) when you need one Profile."
                ),
                parameters=_GET_PROFILE_PARAMS,
                handler=self.get_profile,
            ),
        )

    def _session(self) -> Session:
        return self._session_getter()

    def __len__(self) -> int:
        """Return how many tools this sequence holds."""
        return len(self._items)

    def __getitem__(self, index: int) -> Tool:  # type: ignore[override]
        """Return the tool at ``index``."""
        return self._items[index]

    def __iter__(self) -> Iterator[Tool]:
        """Iterate the Session-bound tools."""
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
        return dump_public(
            await self._session().find(query, limit=limit, detail=detail)
        )

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
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send reply-expected work and return the current TicketView as JSON.

        Same argument names as :meth:`~agentconnect.agent.base.BaseAgent.ask`.
        ``collect="wait"`` uses the Runtime wait hold and may still return
        an ``open`` TicketView. Omit ``deadline_seconds`` to inherit a request
        parent or the Runtime work lifetime. Pass ``idempotency_key`` so a
        retry reuses the same Ticket. Changed keyed arguments raise
        ``id_conflict``.

            ticket = await tools.ask(
                recipient="writer",
                content={"task": "draft this"},
            )
            if ticket["state"] == "open":
                ticket = await tools.get_result(ticket["ticket_id"])
            if ticket["state"] == "completed":
                ticket["content"]
        """
        session = self._session()
        address = session.address
        if not address:
            raise SessionError("unauthorized", "Agent has not joined a Team")
        if collect not in {"wait", "ticket"}:
            raise SessionError(
                "invalid_request",
                "ask collect must be wait or ticket",
            )
        message_id = _message_id(
            "ask",
            address,
            idempotency_key=idempotency_key,
        )
        if thread_id is not None:
            send_thread = thread_id
        elif idempotency_key:
            send_thread = _thread_id("ask", address, idempotency_key)
        elif session.handling_delivery() is not None:
            send_thread = None
        else:
            send_thread = str(uuid.uuid4())
        recovered_deadline: Optional[str] = None
        recovered_before = False
        if idempotency_key:
            recovered = await _recover_keyed_ask(session, message_id, thread_id)
            if recovered is not None:
                send_thread, recovered_deadline = recovered
                recovered_before = True
                if deadline_seconds is None:
                    recovered_deadline = None
        try:
            ticket = await session.ask(
                recipient,
                content,
                deadline_seconds=deadline_seconds,
                collect=collect,
                thread_id=send_thread,
                parent_id=parent_id,
                metadata=metadata,
                message_id=message_id,
                deadline=recovered_deadline,
            )
        except SessionError as exc:
            if exc.code != "id_conflict" or not idempotency_key or recovered_before:
                raise
            recovered = await _recover_keyed_ask(session, message_id, thread_id)
            if recovered is None:
                raise
            send_thread, recovered_deadline = recovered
            if deadline_seconds is None:
                recovered_deadline = None
            ticket = await session.ask(
                recipient,
                content,
                deadline_seconds=deadline_seconds,
                collect=collect,
                thread_id=send_thread,
                parent_id=parent_id,
                metadata=metadata,
                message_id=message_id,
                deadline=recovered_deadline,
            )
        return dump_public(ticket_view(ticket))

    async def tell(
        self,
        recipient: str,
        content: Any,
        *,
        thread_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send work with no reply. No Ticket is created."""
        session = self._session()
        address = session.address
        if not address:
            raise SessionError("unauthorized", "Agent has not joined a Team")
        message_id = _message_id(
            "tell",
            address,
            idempotency_key=idempotency_key,
        )
        return dump_public(
            await session.tell(
                recipient,
                content,
                thread_id=thread_id,
                parent_id=parent_id,
                metadata=metadata,
                message_id=message_id,
            )
        )

    async def get_result(self, ticket_id: str) -> dict[str, Any]:
        """Return the current TicketView this Membership opened."""
        return dump_public(ticket_view(await self._session().get_result(ticket_id)))

    async def get_history(
        self,
        thread_id: str,
        *,
        before: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return one page of retained Thread history."""
        return dump_public(
            await self._session().get_history(thread_id, before=before, limit=limit)
        )

    async def get_profile(self, address: str) -> dict[str, Any]:
        """Return one Directory entry (Address, DID, and full Profile)."""
        return dump_public(await self._session().get_entry(address))


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


def _thread_id(kind: str, caller_address: str, idempotency_key: str) -> str:
    material = f"{kind}-thread|{caller_address}|{idempotency_key}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"agentconnect:{material}"))


async def _recover_keyed_ask(
    session: Session, message_id: str, supplied_thread: Optional[str]
) -> Optional[tuple[str, str]]:
    """Return stored Thread id and deadline for an accepted keyed ask."""
    try:
        ticket = await session.get_result(message_id)
    except SessionError as exc:
        if exc.code == "not_found":
            return None
        raise
    thread = supplied_thread or ticket.thread_id
    deadline = ticket.deadline
    if not isinstance(thread, str) or not isinstance(deadline, str):
        return None
    return thread, deadline


def _parse_arguments(arguments: Mapping[str, Any] | str) -> dict[str, Any]:
    if isinstance(arguments, Mapping):
        return dict(arguments)
    raw = arguments.strip() if arguments else ""
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("tool arguments must be a JSON object")
    return parsed


def _stringify(result: Any) -> str:
    if result is None:
        return "null"
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, default=str)
    except TypeError:
        return str(result)


def _description_from_doc(doc: str) -> str:
    if not doc:
        return ""
    parts: list[str] = []
    for line in doc.splitlines():
        stripped = line.strip()
        if not stripped:
            if parts:
                break
            continue
        if re.match(
            r"^(Args|Arguments|Parameters|Returns|Raises|Yields|Note|Notes|Example|Examples)\s*:",
            stripped,
            flags=re.IGNORECASE,
        ):
            break
        parts.append(stripped)
    return " ".join(parts).strip()


def _parse_args_section(doc: str) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    if not doc:
        return descriptions
    lines = doc.splitlines()
    i = 0
    while i < len(lines):
        if re.match(r"^(Args|Arguments|Parameters)\s*:\s*$", lines[i].strip()):
            i += 1
            break
        i += 1
    else:
        return descriptions
    current: str | None = None
    chunks: list[str] = []

    def _flush() -> None:
        nonlocal current, chunks
        if current is not None:
            descriptions[current] = " ".join(chunks).strip()
        current = None
        chunks = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if re.match(
            r"^(Returns|Raises|Yields|Note|Notes|Example|Examples)\s*:",
            stripped,
        ):
            break
        match = re.match(r"^(\w+)\s*:\s*(.*)$", stripped)
        if match:
            _flush()
            current = match.group(1)
            rest = match.group(2).strip()
            chunks = [rest] if rest else []
            i += 1
            continue
        if current is not None:
            chunks.append(stripped)
        i += 1
    _flush()
    return descriptions


def _parameters_from_callable(
    fn: ToolHandler, doc: str
) -> tuple[dict[str, Any], type[Any]]:
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"cannot read parameters for {fn!r}") from exc
    try:
        hints = get_type_hints(fn, include_extras=True)
    except Exception as exc:
        label = getattr(fn, "__name__", fn)
        raise ValueError(f"cannot read annotations for {label!r}: {exc}") from exc
    arg_docs = _parse_args_section(doc)
    fields: dict[str, Any] = {}
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
            inspect.Parameter.POSITIONAL_ONLY,
        ):
            raise ValueError(
                f"{getattr(fn, '__name__', 'tool')}.{name} cannot be advertised; "
                "tool arguments are keywords"
            )
        if param.annotation is inspect.Parameter.empty or name not in hints:
            raise ValueError(
                f"{getattr(fn, '__name__', 'tool')}.{name} needs a type annotation"
            )
        annotation = hints[name]
        if annotation is Any:
            raise ValueError(
                f"{getattr(fn, '__name__', 'tool')}.{name} needs a type other than Any"
            )
        description = arg_docs.get(name)
        if description:
            annotation = Annotated[annotation, Field(description=description)]
        if param.default is param.empty:
            fields[name] = (annotation, ...)
        else:
            fields[name] = (annotation, param.default)
    if not fields:
        model = create_model(f"{_model_name(fn)}_Params")
        return {"type": "object", "properties": {}}, model
    try:
        model = create_model(f"{_model_name(fn)}_Params", **fields)
        schema = model.model_json_schema()
    except Exception as exc:
        raise ValueError(
            f"cannot build a schema for {getattr(fn, '__name__', 'tool')}: {exc}"
        ) from exc
    return _parameters_schema(schema), model


def _model_name(fn: ToolHandler) -> str:
    name = getattr(fn, "__name__", "tool")
    if isinstance(name, str) and name.isidentifier():
        return name
    return "tool"


def _parameters_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Keep constraints and ``$ref`` targets. Do not inline references."""
    defs = dict(schema.get("$defs") or schema.get("definitions") or {})
    _require_resolvable_refs(schema, defs)
    properties = {
        key: _strip_titles(value)
        for key, value in dict(schema.get("properties") or {}).items()
    }
    out: dict[str, Any] = {"type": "object", "properties": properties}
    required = schema.get("required")
    if isinstance(required, list) and required:
        out["required"] = list(required)
    if defs:
        out["$defs"] = _strip_titles(defs)
    return out


def _require_resolvable_refs(node: Any, defs: Mapping[str, Any]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            if not ref.startswith("#/$defs/") and not ref.startswith("#/definitions/"):
                raise ValueError(f"unsupported schema reference {ref}")
            name = ref.rsplit("/", 1)[-1]
            if name not in defs:
                raise ValueError(f"unresolved schema reference {ref}")
        for value in node.values():
            _require_resolvable_refs(value, defs)
    elif isinstance(node, list):
        for item in node:
            _require_resolvable_refs(item, defs)


def _strip_titles(node: Any) -> Any:
    if isinstance(node, dict):
        return {
            key: _strip_titles(value) for key, value in node.items() if key != "title"
        }
    if isinstance(node, list):
        return [_strip_titles(item) for item in node]
    return node
