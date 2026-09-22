"""Registration and execution regressions for plain callable tools."""

from __future__ import annotations

from typing import Annotated, Any, Optional

import pytest
from pydantic import BaseModel, Field, ValidationError

from agentconnect.agent.tools import Tool, _call_tool
from agentconnect.core.base import public_json_schema
from agentconnect.core.directory import FindRequest, GetProfileRequest
from agentconnect.core.operations import (
    AskToolRequest,
    GetHistoryRequest,
    GetResultRequest,
    TellToolRequest,
)
from agentconnect.agent import BaseAgent


def test_annotated_constraints_stay_on_the_advertised_argument():
    def bounded(n: Annotated[int, Field(ge=1, le=10)]) -> str:
        """Count items.

        Args:
            n: How many.
        """
        return str(n)

    prop = Tool.from_callable(bounded).parameters["properties"]["n"]
    assert prop["type"] == "integer"
    assert prop["minimum"] == 1
    assert prop["maximum"] == 10
    assert prop["description"] == "How many."


class Node(BaseModel):
    name: str = Field(min_length=1)
    child: Optional["Node"] = None


def test_schema_references_are_kept():
    def walk(node: Node) -> str:
        return node.name

    schema = Tool.from_callable(walk).parameters
    assert "$defs" in schema
    dumped = str(schema)
    assert "#/$defs/" in dumped
    assert schema["properties"]["node"]["$ref"].startswith("#/$defs/")
    assert schema["$defs"]
    child = next(iter(schema["$defs"].values()))
    assert child["properties"]["name"]["minLength"] == 1


def test_unannotated_varargs_and_any_fail_at_registration():
    def bare(x) -> str:
        return str(x)

    def star(*args: str) -> str:
        return ""

    def keywords(query: str, **extra: str) -> str:
        return query + "".join(extra)

    def untyped_any(value: Any) -> str:
        return str(value)

    def positional_only(query: str, /) -> str:
        return query

    for fn in (bare, star, keywords, untyped_any, positional_only):
        with pytest.raises(ValueError, match=fn.__name__):
            Tool.from_callable(fn)


class Payload(BaseModel):
    name: str
    count: int


@pytest.mark.asyncio
async def test_pydantic_argument_is_passed_as_the_model_instance():
    seen: list[Payload] = []

    def take(payload: Payload) -> str:
        seen.append(payload)
        return f"{payload.name}:{payload.count}"

    tool = Tool.from_callable(take)
    assert await _call_tool(tool, {"payload": {"name": "refund", "count": 2}}) == (
        "refund:2"
    )
    assert len(seen) == 1
    assert isinstance(seen[0], Payload)
    assert seen[0].name == "refund"
    assert seen[0].count == 2


@pytest.mark.asyncio
async def test_invalid_pydantic_argument_does_not_call_the_handler():
    calls: list[Payload] = []

    def take(payload: Payload) -> str:
        calls.append(payload)
        return payload.name

    tool = Tool.from_callable(take)
    with pytest.raises(ValidationError):
        await _call_tool(tool, {"payload": {"name": "refund"}})
    assert calls == []


def test_team_tool_parameters_match_mcp_request_schemas():
    class Holder(BaseAgent):
        async def handle(self, message, ctx) -> Any:
            return None

    tools = {item.name: item.parameters for item in Holder(name="holder").team_tools()}
    assert tools["find"] == public_json_schema(FindRequest)
    assert tools["ask"] == public_json_schema(AskToolRequest)
    assert tools["tell"] == public_json_schema(TellToolRequest)
    assert tools["get_result"] == public_json_schema(GetResultRequest)
    assert tools["get_history"] == public_json_schema(GetHistoryRequest)
    assert tools["get_profile"] == public_json_schema(GetProfileRequest)
