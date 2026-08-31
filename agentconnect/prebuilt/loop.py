"""Model tool loop owned by AgentConnect.

LiteLLM normalizes provider APIs. It does not run tools. This loop does:
call the model, run any tool calls, append results, repeat until the model
stops calling tools or ``max_rounds`` is hit.

    from agentconnect.prebuilt.loop import run_tool_loop
    from agentconnect.prebuilt.tools import Tool

    reply = await run_tool_loop(
        complete=litellm.acompletion,
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "ping the tool"}],
        tools=[Tool(name="ping", description="Return pong.", parameters={...}, handler=ping)],
    )
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any, Optional, Protocol

from agentconnect.prebuilt.tools import Tool, call_tool

logger = logging.getLogger(__name__)

DEFAULT_MAX_ROUNDS = 8


class CompletionFn(Protocol):
    """Async callable with the LiteLLM ``acompletion`` shape.

    The loop passes ``model``, ``messages``, and when tools exist, ``tools``.
    Extra keyword arguments from the caller (temperature, api_key, ...) are
    forwarded unchanged.
    """

    async def __call__(self, **kwargs: Any) -> Any: ...


async def run_tool_loop(
    *,
    complete: CompletionFn,
    model: str,
    messages: Sequence[Mapping[str, Any]],
    tools: Sequence[Tool] | None = None,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    **complete_kwargs: Any,
) -> str:
    """Call ``complete`` until the model returns text or ``max_rounds`` is hit.

    ``messages`` is an OpenAI-style chat history. The loop mutates a local copy
    only. Tool results stay in that copy; they are not written to a Thread.

        reply = await run_tool_loop(
            complete=scripted_complete,
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hello"}],
        )
    """
    if max_rounds < 1:
        raise ValueError("max_rounds must be at least 1")
    history: list[dict[str, Any]] = [dict(item) for item in messages]
    by_name = {tool.name: tool for tool in tools or ()}
    schemas = [tool.openai_schema() for tool in by_name.values()]
    last_text = ""
    for round_index in range(max_rounds):
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": history,
            **complete_kwargs,
        }
        if schemas:
            kwargs["tools"] = schemas
        response = await complete(**kwargs)
        message = _choice_message(response)
        text = _content_text(message)
        if text:
            last_text = text
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
                    payload = await call_tool(tool, arguments)
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
    if last_text:
        return last_text
    return f"Stopped after {max_rounds} tool rounds."


def messages_from_thread(
    history: Sequence[Mapping[str, Any]],
    current: Mapping[str, Any] | str,
    *,
    self_address: Optional[str] = None,
    instructions: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Build a chat history from Runtime Messages (``ctx.history`` plus this turn).

    messages = messages_from_thread(ctx.history, msg, self_address=agent.address)
    """
    out: list[dict[str, Any]] = []
    if instructions:
        out.append({"role": "system", "content": instructions})
    for item in history:
        out.append(_history_item(item, self_address=self_address))
    if isinstance(current, str):
        out.append({"role": "user", "content": current})
    elif "role" in current:
        out.append(dict(current))
    else:
        out.append(_history_item(current, self_address=self_address, as_user=True))
    return out


def _history_item(
    item: Mapping[str, Any],
    *,
    self_address: Optional[str],
    as_user: bool = False,
) -> dict[str, Any]:
    if "role" in item and "content" in item and "sender" not in item:
        return {"role": str(item["role"]), "content": _content_text(item)}
    sender = str(item.get("sender") or "")
    role = "user"
    if not as_user and self_address and sender == self_address:
        role = "assistant"
    return {"role": role, "content": _content_text(item)}


def _choice_message(response: Any) -> Any:
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


def _content_text(message: Any) -> str:
    if message is None:
        return ""
    if isinstance(message, str):
        return message
    if isinstance(message, Mapping):
        if "content" in message:
            return _stringify_content(message.get("content"))
        return _stringify_content(message)
    return _stringify_content(getattr(message, "content", None))


def _stringify_content(content: Any) -> str:
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


def _tool_calls(message: Any) -> list[Any]:
    if isinstance(message, Mapping):
        calls = message.get("tool_calls") or []
    else:
        calls = getattr(message, "tool_calls", None) or []
    return list(calls)


def _unpack_call(call: Any) -> tuple[str, str, str]:
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


def _assistant_with_calls(text: str, calls: Sequence[Any]) -> dict[str, Any]:
    serialized: list[dict[str, Any]] = []
    for call in calls:
        call_id, name, arguments = _unpack_call(call)
        serialized.append(
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        )
    payload: dict[str, Any] = {
        "role": "assistant",
        "content": text or None,
        "tool_calls": serialized,
    }
    return payload
