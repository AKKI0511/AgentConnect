"""Run a model call until it stops asking for tools.

[`run_tool_loop`][agentconnect.prebuilt.loop.run_tool_loop] returns the
model's text. If the model is still calling tools when `max_rounds`
ends, it raises
[`ToolLoopExhausted`][agentconnect.prebuilt.loop.ToolLoopExhausted]. A tool
exception is reported back to the model as error JSON, and the loop
continues. The messages you passed are not changed, and tool results
are not written to a Team thread.

Pass `complete` to use a callable other than LiteLLM. It receives
`model`, `messages`, and `tools` when tools are present.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any, Optional, Protocol

from agentconnect.core.message import Message

from agentconnect.agent.tools import ToolLike, _call_tool, _ensure_tool

logger = logging.getLogger(__name__)

DEFAULT_MAX_ROUNDS = 8


class ToolLoopExhausted(Exception):
    """The model was still calling tools when `max_rounds` was reached.

    Raised by [`run_tool_loop`][agentconnect.prebuilt.loop.run_tool_loop].
    [`AIAgent`][agentconnect.prebuilt.ai_agent.AIAgent] `handle` does not
    catch it, so an in-Team request fails through the handler-failure
    path. `chat` and `complete` let the same exception reach the caller.

    Attributes:
        max_rounds: Turn budget that was exhausted.
    """

    def __init__(self, max_rounds: int) -> None:
        self.max_rounds = max_rounds
        super().__init__(f"tool loop exhausted after {max_rounds} rounds")


class CompletionFn(Protocol):
    """Async callable with the LiteLLM `acompletion` shape.

    The loop passes `model`, `messages`, and when tools exist, `tools`.
    Extra keyword arguments from the caller (`temperature`, `api_key`,
    and others) are forwarded unchanged.
    """

    async def __call__(self, **kwargs: Any) -> object: ...


async def run_tool_loop(
    *,
    complete: CompletionFn,
    model: str,
    messages: Sequence[Mapping[str, object]],
    tools: Sequence[ToolLike] | None = None,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    **complete_kwargs: object,
) -> str:
    """Call `complete` until the model returns text or raise on exhaustion.

    `messages` is an OpenAI-style chat history. The loop mutates a local copy
    only. Tool results stay in that copy; they are not written to a Thread.
    A tool exception becomes one error JSON payload and the loop continues.
    Hitting `max_rounds` while tool calls remain raises `ToolLoopExhausted`.

    Raises:
        ValueError: `max_rounds` is below 1.
        ToolLoopExhausted: The model was still calling tools after
            `max_rounds`.
    """
    if max_rounds < 1:
        raise ValueError("max_rounds must be at least 1")
    history: list[dict[str, object]] = [dict(item) for item in messages]
    resolved = [_ensure_tool(item) for item in tools or ()]
    by_name = {tool.name: tool for tool in resolved}
    schemas = [tool.openai_schema() for tool in by_name.values()]
    for round_index in range(max_rounds):
        kwargs: dict[str, object] = {
            "model": model,
            "messages": history,
            **complete_kwargs,
        }
        if schemas:
            kwargs["tools"] = schemas
        response = await complete(**kwargs)
        message = _choice_message(response)
        text = _content_text(message)
        calls = _tool_calls(message)
        if not calls:
            return text
        history.append(_assistant_with_calls(text, calls))
        for call in calls:
            call_id, name, arguments = _unpack_call(call)
            tool = by_name.get(name)
            if tool is None:
                payload = json.dumps({"error": f"unknown tool {name!r}"})
            else:
                try:
                    payload = await _call_tool(tool, arguments)
                except Exception as exc:
                    logger.warning(
                        "tool %s failed round=%s: %s", name, round_index, exc
                    )
                    payload = json.dumps({"error": str(exc)})
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": payload,
                }
            )
    logger.warning("tool loop hit max_rounds=%s model=%s", max_rounds, model)
    raise ToolLoopExhausted(max_rounds)


def messages_from_thread(
    history: Sequence[Message | Mapping[str, object]],
    current: Message | Mapping[str, object] | str,
    *,
    self_address: Optional[str] = None,
    instructions: Optional[str] = None,
) -> list[dict[str, object]]:
    """Build a chat history from Runtime Messages (`ctx.history` plus this turn).

    Args:
        history: Earlier Thread Messages or chat dicts.
        current: This turn as a Message, chat dict, or string.
        self_address: Address treated as this Agent (`assistant` role).
        instructions: Optional system prompt prepended to the history.

    Returns:
        OpenAI-style chat messages.

    Examples:
        ```python
        messages = messages_from_thread(
            ctx.history, msg, self_address=agent.address
        )
        ```
    """
    out: list[dict[str, object]] = []
    if instructions:
        out.append({"role": "system", "content": instructions})
    for item in history:
        out.append(_history_item(item, self_address=self_address))
    if isinstance(current, str):
        out.append({"role": "user", "content": current})
    elif isinstance(current, Mapping) and "role" in current:
        out.append(dict(current))
    else:
        out.append(_history_item(current, self_address=self_address, as_user=True))
    return out


def _history_item(
    item: object,
    *,
    self_address: Optional[str],
    as_user: bool = False,
) -> dict[str, object]:
    if isinstance(item, Mapping) and "role" in item and "content" in item:
        if "sender" not in item:
            return {"role": str(item["role"]), "content": _content_text(item)}
    sender = str(getattr(item, "sender", None) or "")
    if not sender and isinstance(item, Mapping):
        sender = str(item.get("sender") or "")
    role = "user"
    if not as_user and self_address and sender == self_address:
        role = "assistant"
    return {"role": role, "content": _content_text(item)}


def _choice_message(response: object) -> object:
    if isinstance(response, Mapping):
        choices = response.get("choices") or []
        if not choices:
            return {}
        first = choices[0]
        if isinstance(first, Mapping):
            return first.get("message") or {}
        return getattr(first, "message", None) or {}
    choices = getattr(response, "choices", None) or []
    if not choices:
        return {}
    return getattr(choices[0], "message", None) or {}


def _content_text(message: object) -> str:
    if message is None:
        return ""
    if isinstance(message, str):
        return message
    if isinstance(message, Mapping):
        if "content" in message:
            return _stringify_content(message.get("content"))
        return _stringify_content(message)
    return _stringify_content(getattr(message, "content", None))


def _stringify_content(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, Sequence) and not isinstance(content, (str, bytes)):
        parts: list[str] = []
        for block in content:
            if isinstance(block, Mapping):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
            else:
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    if isinstance(content, (dict, list)):
        return json.dumps(content, default=str)
    return str(content)


def _tool_calls(message: object) -> list[object]:
    if isinstance(message, Mapping):
        calls = message.get("tool_calls") or []
    else:
        calls = getattr(message, "tool_calls", None) or []
    return list(calls)


def _unpack_call(call: object) -> tuple[str, str, str]:
    if isinstance(call, Mapping):
        call_id = str(call.get("id") or "")
        function = call.get("function") or {}
        if isinstance(function, Mapping):
            name = str(function.get("name") or "")
            arguments = function.get("arguments") or "{}"
        else:
            name = str(getattr(function, "name", "") or "")
            arguments = getattr(function, "arguments", None) or "{}"
        return (
            call_id,
            name,
            arguments if isinstance(arguments, str) else json.dumps(arguments),
        )
    function = getattr(call, "function", None)
    call_id = str(getattr(call, "id", "") or "")
    name = str(getattr(function, "name", "") or "")
    arguments = getattr(function, "arguments", None) or "{}"
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments)
    return call_id, name, arguments


def _assistant_with_calls(text: str, calls: Sequence[object]) -> dict[str, object]:
    serialized: list[dict[str, object]] = []
    for call in calls:
        call_id, name, arguments = _unpack_call(call)
        serialized.append(
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        )
    payload: dict[str, object] = {
        "role": "assistant",
        "content": text or None,
        "tool_calls": serialized,
    }
    return payload
