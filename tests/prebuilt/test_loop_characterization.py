"""Recorded-model characterization of the prebuilt tool loop.

Pins observable ``run_tool_loop`` and ``messages_from_thread`` behavior.
No network and no litellm.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from agentconnect.prebuilt.loop import messages_from_thread, run_tool_loop
from agentconnect.prebuilt.tools import Tool


def scripted(*turns):
    """Return a completion that yields recorded responses in order."""
    queue = list(turns)

    async def complete(**kwargs):
        assert queue, "model was called more times than recorded"
        return queue.pop(0)

    return complete


def recording_scripted(*turns):
    """Like ``scripted``, but also records every complete kwargs dict.

    ``messages`` is snapshotted at call time because the loop passes the
    same mutable list into every round.
    """
    queue = list(turns)
    recorded: list[dict] = []

    async def complete(**kwargs):
        snap = dict(kwargs)
        messages = kwargs.get("messages")
        if isinstance(messages, list):
            snap["messages"] = [dict(item) for item in messages]
        recorded.append(snap)
        assert queue, "model was called more times than recorded"
        return queue.pop(0)

    return complete, recorded


def text_turn(content) -> dict:
    return {"choices": [{"message": {"content": content, "tool_calls": []}}]}


def tool_turn(
    name: str,
    arguments: str,
    call_id: str = "c1",
    *,
    content=None,
) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": content,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": name, "arguments": arguments},
                        }
                    ],
                }
            }
        ]
    }


def multi_tool_turn(*calls: tuple[str, str, str], content=None) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": content,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": name, "arguments": arguments},
                        }
                        for name, arguments, call_id in calls
                    ],
                }
            }
        ]
    }


async def ping() -> str:
    return "pong"


PING = Tool(
    name="ping",
    description="Return pong.",
    parameters={"type": "object", "properties": {}},
    handler=ping,
)


@pytest.mark.asyncio
async def test_complete_receives_exact_kwargs_across_rounds():
    complete, recorded = recording_scripted(
        tool_turn("ping", "{}"),
        text_turn("done"),
    )
    reply = await run_tool_loop(
        complete=complete,
        model="recorded-model",
        messages=[{"role": "user", "content": "ping"}],
        tools=[PING],
        temperature=0.2,
        api_key="test-key",
    )
    assert reply == "done"
    assert len(recorded) == 2

    first = recorded[0]
    assert first["model"] == "recorded-model"
    assert first["temperature"] == 0.2
    assert first["api_key"] == "test-key"
    assert first["messages"] == [{"role": "user", "content": "ping"}]
    assert first["tools"] == [PING.openai_schema()]

    second = recorded[1]
    assert second["model"] == "recorded-model"
    assert second["temperature"] == 0.2
    assert second["api_key"] == "test-key"
    assert second["tools"] == [PING.openai_schema()]
    assert second["messages"][0] == {"role": "user", "content": "ping"}
    assert second["messages"][1] == {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "ping", "arguments": "{}"},
            }
        ],
    }
    assert second["messages"][2] == {
        "role": "tool",
        "tool_call_id": "c1",
        "content": "pong",
    }


@pytest.mark.asyncio
async def test_loop_returns_text_when_model_stops():
    reply = await run_tool_loop(
        complete=scripted(text_turn("hello")),
        model="recorded",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert reply == "hello"


@pytest.mark.asyncio
async def test_one_tool_then_text_includes_assistant_and_tool_messages():
    complete, recorded = recording_scripted(
        tool_turn("ping", "{}"),
        text_turn("pong from model"),
    )
    reply = await run_tool_loop(
        complete=complete,
        model="recorded",
        messages=[{"role": "user", "content": "ping the tool"}],
        tools=[PING],
    )
    assert reply == "pong from model"
    follow_up = recorded[1]["messages"]
    assert follow_up[1]["role"] == "assistant"
    assert follow_up[1]["tool_calls"][0]["function"]["name"] == "ping"
    assert follow_up[2] == {
        "role": "tool",
        "tool_call_id": "c1",
        "content": "pong",
    }


@pytest.mark.asyncio
async def test_unknown_tool_message_is_json_error_and_loop_finishes():
    complete, recorded = recording_scripted(
        tool_turn("missing", "{}"),
        text_turn("gave up"),
    )
    reply = await run_tool_loop(
        complete=complete,
        model="recorded",
        messages=[{"role": "user", "content": "call missing"}],
        tools=[PING],
    )
    assert reply == "gave up"
    tool_msg = recorded[1]["messages"][2]
    assert tool_msg["role"] == "tool"
    assert json.loads(tool_msg["content"]) == {"error": "unknown tool 'missing'"}


@pytest.mark.asyncio
async def test_handler_exception_becomes_error_json_and_loop_continues():
    async def boom() -> str:
        raise RuntimeError("handler broke")

    failing = Tool(
        name="boom",
        description="Raises.",
        parameters={"type": "object", "properties": {}},
        handler=boom,
    )
    complete, recorded = recording_scripted(
        tool_turn("boom", "{}"),
        text_turn("recovered"),
    )
    reply = await run_tool_loop(
        complete=complete,
        model="recorded",
        messages=[{"role": "user", "content": "call boom"}],
        tools=[failing],
    )
    assert reply == "recovered"
    tool_msg = recorded[1]["messages"][2]
    assert json.loads(tool_msg["content"]) == {"error": "handler broke"}


@pytest.mark.asyncio
async def test_several_tool_calls_in_one_message_run_in_order():
    order: list[str] = []

    async def first() -> str:
        order.append("first")
        return "one"

    async def second() -> str:
        order.append("second")
        return "two"

    tools = [
        Tool(
            name="first",
            description="First.",
            parameters={"type": "object", "properties": {}},
            handler=first,
        ),
        Tool(
            name="second",
            description="Second.",
            parameters={"type": "object", "properties": {}},
            handler=second,
        ),
    ]
    complete, recorded = recording_scripted(
        multi_tool_turn(("first", "{}", "a"), ("second", "{}", "b")),
        text_turn("both done"),
    )
    reply = await run_tool_loop(
        complete=complete,
        model="recorded",
        messages=[{"role": "user", "content": "call both"}],
        tools=tools,
    )
    assert reply == "both done"
    assert order == ["first", "second"]
    follow_up = recorded[1]["messages"]
    assert follow_up[2] == {
        "role": "tool",
        "tool_call_id": "a",
        "content": "one",
    }
    assert follow_up[3] == {
        "role": "tool",
        "tool_call_id": "b",
        "content": "two",
    }


@pytest.mark.asyncio
async def test_max_rounds_exhausted_raises_tool_loop_exhausted():
    from agentconnect.prebuilt.loop import ToolLoopExhausted

    with pytest.raises(ToolLoopExhausted) as exc:
        await run_tool_loop(
            complete=scripted(
                tool_turn("ping", "{}", content="keep going"),
                tool_turn("ping", "{}", "c2", content="still going"),
            ),
            model="recorded",
            messages=[{"role": "user", "content": "loop"}],
            tools=[PING],
            max_rounds=2,
        )
    assert exc.value.max_rounds == 2
    assert "exhausted" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_max_rounds_exhausted_without_text_still_raises():
    from agentconnect.prebuilt.loop import ToolLoopExhausted

    with pytest.raises(ToolLoopExhausted) as exc:
        await run_tool_loop(
            complete=scripted(
                tool_turn("ping", "{}"),
                tool_turn("ping", "{}", "c2"),
            ),
            model="recorded",
            messages=[{"role": "user", "content": "loop"}],
            tools=[PING],
            max_rounds=2,
        )
    assert exc.value.max_rounds == 2
    assert "Stopped after" not in str(exc.value)


@pytest.mark.asyncio
async def test_max_rounds_less_than_one_raises():
    with pytest.raises(ValueError, match="max_rounds must be at least 1"):
        await run_tool_loop(
            complete=scripted(text_turn("nope")),
            model="recorded",
            messages=[{"role": "user", "content": "hi"}],
            max_rounds=0,
        )


@pytest.mark.asyncio
async def test_accepts_attribute_style_litellm_stand_in():
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="from attrs", tool_calls=None)
            )
        ]
    )

    async def complete(**kwargs):
        return response

    reply = await run_tool_loop(
        complete=complete,
        model="recorded",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert reply == "from attrs"


@pytest.mark.asyncio
async def test_list_of_text_blocks_is_concatenated():
    reply = await run_tool_loop(
        complete=scripted(
            text_turn([{"text": "hello"}, {"text": " "}, {"text": "world"}])
        ),
        model="recorded",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert reply == "hello world"


def test_messages_from_thread_optional_system_instructions():
    messages = messages_from_thread(
        [],
        "hi",
        instructions="Be brief.",
    )
    assert messages[0] == {"role": "system", "content": "Be brief."}
    assert messages[1] == {"role": "user", "content": "hi"}


def test_messages_from_thread_self_is_assistant_peer_is_user():
    # Current must be a Mapping: ``"role" in current`` is used at the
    # boundary. Attribute-only stand-ins raise TypeError today.
    prior = [
        SimpleNamespace(sender="agent@team", content="I said this"),
        SimpleNamespace(sender="peer@team", content="peer said this"),
    ]
    messages = messages_from_thread(
        prior,
        {"sender": "peer@team", "content": "now"},
        self_address="agent@team",
    )
    assert messages[0] == {"role": "assistant", "content": "I said this"}
    assert messages[1] == {"role": "user", "content": "peer said this"}
    assert messages[2] == {"role": "user", "content": "now"}


def test_messages_from_thread_current_is_user_even_when_sender_is_self():
    messages = messages_from_thread(
        [],
        {"sender": "agent@team", "content": "talking to myself"},
        self_address="agent@team",
    )
    assert messages == [{"role": "user", "content": "talking to myself"}]


def test_messages_from_thread_chat_shaped_history_passes_through():
    history = [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "two"},
    ]
    messages = messages_from_thread(
        history,
        {"role": "user", "content": "three"},
    )
    assert messages == [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "two"},
        {"role": "user", "content": "three"},
    ]
