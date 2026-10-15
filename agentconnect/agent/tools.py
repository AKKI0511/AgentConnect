"""Describe Python callables and Team operations for attachment to a harness."""

from __future__ import annotations

import inspect
import json
import re
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Optional, Union, get_type_hints, overload

from pydantic import BaseModel, ConfigDict, Field, create_model
from pydantic.json_schema import JsonSchemaValue
from typing_extensions import Annotated

from agentconnect.agent.errors import SessionError
from agentconnect.agent.session import Session
from agentconnect.core.base import (
    JsonObject,
    JsonValue,
    dump_public,
    parse_schema,
    public_json_schema,
)
from agentconnect.core.directory import (
    GetProfilesRequest,
    GetProfilesResult,
    ProfileFound,
    ProfileMiss,
)
from agentconnect.core.error import ErrorObject
from agentconnect.core.operations import (
    history_view,
    tell_view,
)
from agentconnect.core.primitives import CollectMode
from agentconnect.core.team_tools import TEAM_TOOL_SPECS
from agentconnect.core.ticket import ticket_view

ToolHandler = Callable[..., object]
ToolLike = Union["Tool", ToolHandler]

_ITEM_ERROR_CODES = frozenset({"not_found", "forbidden", "address_outside_team"})

KEYED_ID_CONFLICT_MESSAGE = (
    "The same idempotency_key was used with different arguments. "
    "Retry the identical call unchanged, or use a new key only for new work. "
    "Do not drop the key after an uncertain accept; that can duplicate work."
)


@dataclass(frozen=True)
class Tool:
    """A callable exposed to a harness, with its argument schema.

    Pass a plain annotated function to `from_callable` to derive the
    JSON Schema from the signature and docstring. Construct `Tool`
    directly when annotations cannot express the schema.

    Attributes:
        name: Tool name advertised to the host.
        description: Text the host shows for this tool.
        parameters: JSON Schema object for keyword arguments.
        handler: Callable invoked with those keywords.
        params_model: Optional Pydantic model used to validate arguments.
    """

    name: str
    description: str
    parameters: JsonSchemaValue
    handler: ToolHandler
    params_model: type[BaseModel] | None = None

    @classmethod
    def from_callable(
        cls,
        fn: ToolHandler,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Tool:
        """Build a Tool from an annotated function and its docstring.

        Parameter descriptions come from the function's `Args` section.
        The first paragraph of the docstring becomes `description` unless
        you pass one.

        Args:
            fn: Async or sync callable. Each advertised argument needs a
                type annotation other than `Any`. Keyword-only and
                positional-or-keyword arguments are supported.
            name: Tool name. Defaults to `fn.__name__`.
            description: Tool description. Defaults to the docstring
                summary.

        Returns:
            A `Tool` whose `parameters` schema matches the signature.

        Raises:
            ValueError: The signature cannot be advertised (`*args`,
                `**kwargs`, positional-only, missing annotation, or
                `Any`).
        """
        tool_name = name or getattr(fn, "__name__", "tool")
        if not isinstance(tool_name, str):
            raise ValueError("tool name must be a string")
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

    def openai_schema(self) -> dict[str, object]:
        """Return the OpenAI function-tool descriptor for this tool.

        Returns:
            A mapping with `type` `"function"` and a `function` object holding `name`, `description`, and `parameters`.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _ensure_tool(value: ToolLike) -> Tool:
    """Return ``value`` as a `Tool`, deriving schema from a callable."""
    if isinstance(value, Tool):
        return value
    if callable(value):
        return Tool.from_callable(value)
    raise TypeError("tool must be a Tool or a callable")


async def _call_tool(tool: Tool, arguments: Mapping[str, object] | str) -> str:
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
    """The six Team tool descriptors for one Agent.

    `BaseAgent.team_tools` returns this sequence. Iterate it and pass it
    to a harness. Each `Tool.handler` returns JSON. `ask` and
    `get_result` include `ticket_id`. An `open` result has no `content`.
    A completed result has `content`.
    """

    def __init__(self, session_getter: Callable[[], Session]) -> None:
        """Bind handlers to the Agent connection `team_tools` supplies.

        Args:
            session_getter: Zero-argument callable that returns the
                Agent's connection. `BaseAgent.team_tools` supplies this.
                Handlers fail until that connection exists.
        """
        self._session_getter = session_getter
        handlers: dict[str, ToolHandler] = {
            "find": self._find,
            "ask": self._ask,
            "tell": self._tell,
            "get_result": self._get_result,
            "get_history": self._get_history,
            "get_profiles": self._get_profiles,
        }
        self._items = tuple(
            Tool(
                name=spec.name,
                description=spec.description,
                parameters=public_json_schema(spec.input_model),
                handler=handlers[spec.name],
            )
            for spec in TEAM_TOOL_SPECS
        )

    def _session(self) -> Session:
        return self._session_getter()

    def __len__(self) -> int:
        """Return how many Session-bound tools this sequence holds."""
        return len(self._items)

    @overload
    def __getitem__(self, index: int) -> Tool: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[Tool, ...]: ...

    def __getitem__(self, index: int | slice) -> Tool | tuple[Tool, ...]:
        """Return the `Tool` at `index` in catalog order."""
        return self._items[index]

    def __iter__(self) -> Iterator[Tool]:
        """Iterate the six Session-bound tools in catalog order."""
        return iter(self._items)

    async def _find(
        self,
        query: str,
        *,
        limit: int | None = None,
    ) -> JsonObject:
        """Search this Team's Directory, excluding this Agent.

        Light cards include Address, summary, Skill names, and Profile
        tags. Ranked matches are candidates, not proof of suitability.
        Call `get_profiles` for full Profiles.

        Args:
            query: Natural-language description of the work.
            limit: Maximum matches from 1 to 100. Omit to receive every
                other member, at most 100.

        Returns:
            JSON with a `matches` list, best first.

        Raises:
            SessionError: The Agent has not joined.
        """
        return dump_public(await self._session().find(query, limit=limit))

    async def _ask(
        self,
        recipient: str,
        content: JsonValue,
        *,
        deadline_seconds: Optional[float] = None,
        collect: CollectMode = "wait",
        thread_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Mapping[str, JsonValue]] = None,
        idempotency_key: Optional[str] = None,
    ) -> JsonObject:
        """Send a reply-expected request and return TicketView JSON.

        `collect="wait"` (default) holds until the Ticket is terminal or
        the Runtime wait hold elapses, then returns the current view.
        That view may still be `open`. Ending the wait does not cancel
        accepted work. `collect="ticket"` returns immediately. Branch on
        `state`. Keep `ticket_id` and call `get_result`. Do not send
        another `ask` to collect. A completed view has `content`.

        Pass `idempotency_key` so a retry reuses the same Ticket. Changed
        keyed arguments raise `id_conflict`. When `thread_id` is omitted,
        a key selects a stable Thread, a call from `handle` inherits, and
        a call outside `handle` starts a new Thread.

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
                recipient. Omit to mint, inherit, or key as described
                above.
            parent_id: Message this send answers. From a handler, omit
                to use the current Message.
            metadata: Optional JSON object stored on the Message.
            idempotency_key: Reuse the same Ticket on retry. Use a new
                key only for new work.

        Returns:
            TicketView JSON. An `open` view has `ticket_id` and no
            `content`. A completed view has `content`.

        Raises:
            SessionError: The Agent has not joined, `collect` is not
                `wait` or `ticket`, keyed arguments conflict, or the
                Runtime rejected the send. Branch on `code`.
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
            if exc.code != "id_conflict" or not idempotency_key:
                raise
            if not recovered_before:
                recovered = await _recover_keyed_ask(session, message_id, thread_id)
                if recovered is not None:
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
            raise SessionError(
                "id_conflict",
                KEYED_ID_CONFLICT_MESSAGE,
                details={"argument": "idempotency_key"},
                retryable=exc.retryable,
            ) from exc
        return dump_public(ticket_view(ticket))

    async def _tell(
        self,
        recipient: str,
        content: JsonValue,
        *,
        thread_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Mapping[str, JsonValue]] = None,
        idempotency_key: Optional[str] = None,
    ) -> JsonObject:
        """Send an event. No Ticket is created.

        Acceptance means the Runtime queued the event, not that the
        recipient finished handling it. Pass `idempotency_key` so a retry
        reuses the same Message. Changed keyed arguments raise
        `id_conflict`.

        Args:
            recipient: Local name or same-Team qualified Address.
            content: The notice, as text or JSON.
            thread_id: Continue this conversation with a current
                participant. Omit outside `handle` for an unthreaded
                notice. From `handle`, omit to inherit or start a
                Thread the same way as `ask`.
            parent_id: Message this send answers. From a handler, omit
                to use the current Message.
            metadata: Optional JSON object stored on the Message.
            idempotency_key: Reuse the same Message on retry. Use a new
                key only for new work.

        Returns:
            JSON with `status` `"accepted"` and `thread_id` when the
            event is threaded.

        Raises:
            SessionError: The Agent has not joined, keyed arguments
                conflict, or the Runtime rejected the send.
        """
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
            result = await session.tell(
                recipient,
                content,
                thread_id=thread_id,
                parent_id=parent_id,
                metadata=metadata,
                message_id=message_id,
            )
        except SessionError as exc:
            if exc.code == "id_conflict" and idempotency_key:
                raise SessionError(
                    "id_conflict",
                    KEYED_ID_CONFLICT_MESSAGE,
                    details={"argument": "idempotency_key"},
                    retryable=exc.retryable,
                ) from exc
            raise
        return dump_public(tell_view(result))

    async def _get_result(self, ticket_id: str) -> JsonObject:
        """Return the current TicketView this Membership opened.

        Repeatable. Does not consume the result. If `state` is `open`,
        call again with the same `ticket_id`. Do not send another `ask`.

        Args:
            ticket_id: `ticket_id` from `ask`, equal to the request
                Message id.

        Returns:
            TicketView JSON, which may still be `open`.

        Raises:
            SessionError: The Agent has not joined, or this Membership
                did not open that Ticket.
        """
        return dump_public(ticket_view(await self._session().get_result(ticket_id)))

    async def _get_history(
        self,
        thread_id: str,
        *,
        before: Optional[str] = None,
        limit: int = 50,
    ) -> JsonObject:
        """Return one page of retained Thread history as JSON.

        The newest page is first; turns inside a page are oldest to
        newest. Omit `before` for the newest page. When `has_more` is
        true, pass `next_before` as the next `before`. Only a participant
        may read the Thread.

        Args:
            thread_id: Conversation id from a TicketView or Message.
            before: Return turns older than this id. Prefer
                `next_before` from the previous page.
            limit: Page size from 1 to 200. Defaults to 50.

        Returns:
            JSON with `messages`, `has_more`, and `next_before` when
            more pages remain.

        Raises:
            SessionError: The Agent has not joined, or is not a
                participant.
        """
        return dump_public(
            history_view(
                await self._session().get_history(thread_id, before=before, limit=limit)
            )
        )

    async def _get_profiles(self, addresses: list[str]) -> JsonObject:
        """Return selected teammate Profiles by Address.

        Duplicate Addresses are read once. A missing member appears as a
        per-item error. Other Profiles still return.

        Args:
            addresses: Member Addresses to read, 1 to 20.

        Returns:
            JSON with an `items` list. Each item is `status` `"ok"` with
            a Profile, or `status` `"error"` with an error object.

        Raises:
            SessionError: The Agent has not joined, `addresses` is
                invalid, or the Session is unauthorized.
        """
        try:
            parsed = parse_schema(GetProfilesRequest, {"addresses": addresses})
        except ValueError as exc:
            raise SessionError("invalid_request", str(exc)) from exc
        items: list[ProfileFound | ProfileMiss] = []
        session = self._session()
        for requested in parsed.unique_requested():
            try:
                entry = await session.get_entry(requested)
                items.append(
                    ProfileFound(
                        status="ok",
                        address=entry.address,
                        profile=entry.profile,
                    )
                )
            except SessionError as exc:
                if exc.code == "unauthorized":
                    raise
                if exc.code not in _ITEM_ERROR_CODES:
                    raise
                payload: JsonObject = {
                    "code": exc.code,
                    "message": exc.message,
                }
                if exc.details is not None:
                    payload["details"] = exc.details
                if exc.retryable is not None:
                    payload["retryable"] = exc.retryable
                items.append(
                    ProfileMiss(
                        status="error",
                        address=requested,
                        error=ErrorObject.model_validate(payload),
                    )
                )
        return dump_public(GetProfilesResult(items=items))


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
    if thread is None:
        return None
    return thread, deadline


def _parse_arguments(arguments: Mapping[str, object] | str) -> dict[str, object]:
    if isinstance(arguments, Mapping):
        return dict(arguments)
    raw = arguments.strip() if arguments else ""
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("tool arguments must be a JSON object")
    return parsed


def _stringify(result: object) -> str:
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
) -> tuple[JsonSchemaValue, type[BaseModel]]:
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
    config = ConfigDict(extra="forbid")
    params_model: type[BaseModel]
    if not fields:
        return {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }, create_model(f"{_model_name(fn)}_Params", __config__=config)
    try:
        params_model = create_model(
            f"{_model_name(fn)}_Params", __config__=config, **fields
        )
        schema = params_model.model_json_schema()
    except Exception as exc:
        raise ValueError(
            f"cannot build a schema for {getattr(fn, '__name__', 'tool')}: {exc}"
        ) from exc
    return _parameters_schema(schema), params_model


def _model_name(fn: ToolHandler) -> str:
    name = getattr(fn, "__name__", "tool")
    if isinstance(name, str) and name.isidentifier():
        return name
    return "tool"


def _parameters_schema(schema: JsonSchemaValue) -> dict[str, object]:
    """Keep constraints and ``$ref`` targets. Do not inline references."""
    defs = dict(schema.get("$defs") or schema.get("definitions") or {})
    _require_resolvable_refs(schema, defs)
    properties = {
        key: _strip_titles(value)
        for key, value in dict(schema.get("properties") or {}).items()
    }
    out: JsonSchemaValue = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    required = schema.get("required")
    if isinstance(required, list) and required:
        out["required"] = list(required)
    if defs:
        out["$defs"] = _strip_titles(defs)
    return out


def _require_resolvable_refs(node: object, defs: Mapping[str, object]) -> None:
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


def _strip_titles(node: object) -> object:
    if isinstance(node, dict):
        return {
            key: _strip_titles(value) for key, value in node.items() if key != "title"
        }
    if isinstance(node, list):
        return [_strip_titles(item) for item in node]
    return node
