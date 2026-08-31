"""Golden tests for the LiteLLM tool loop with a recorded model."""

from __future__ import annotations

import pytest

from agentconnect.prebuilt.loop import run_tool_loop
from agentconnect.prebuilt.tools import Tool


def scripted(*turns):
    queue = list(turns)

    async def complete(**kwargs):
        assert queue, "model was called more times than recorded"
        return queue.pop(0)

    return complete


def text_turn(content: str) -> dict:
    return {"choices": [{"message": {"content": content, "tool_calls": []}}]}


def tool_turn(name: str, arguments: str, call_id: str = "c1") -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": None,
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


async def ping() -> str:
    return "pong"


PING = Tool(
    name="ping",
    description="Return pong.",
    parameters={"type": "object", "properties": {}},
    handler=ping,
)


@pytest.mark.asyncio
async def test_loop_returns_text_when_model_stops():
    reply = await run_tool_loop(
        complete=scripted(text_turn("hello")),
        model="recorded",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert reply == "hello"


@pytest.mark.asyncio
async def test_loop_runs_one_tool_then_returns_text():
    reply = await run_tool_loop(
        complete=scripted(tool_turn("ping", "{}"), text_turn("pong from model")),
        model="recorded",
        messages=[{"role": "user", "content": "ping the tool"}],
        tools=[PING],
    )
    assert reply == "pong from model"


@pytest.mark.asyncio
async def test_loop_unknown_tool_still_finishes():
    reply = await run_tool_loop(
        complete=scripted(tool_turn("missing", "{}"), text_turn("gave up")),
        model="recorded",
        messages=[{"role": "user", "content": "call missing"}],
        tools=[PING],
    )
    assert reply == "gave up"


@pytest.mark.asyncio
async def test_loop_stops_at_max_rounds():
    reply = await run_tool_loop(
        complete=scripted(tool_turn("ping", "{}"), tool_turn("ping", "{}", "c2")),
        model="recorded",
        messages=[{"role": "user", "content": "loop"}],
        tools=[PING],
        max_rounds=2,
    )
    assert "Stopped after 2 tool rounds" in reply
