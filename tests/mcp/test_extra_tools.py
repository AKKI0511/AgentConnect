"""Extra Team MCP tools use the public SDK callable implementation."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import threading
from typing import Annotated, Any, Literal

import pytest
from mcp.server.mcpserver.context import Context as SdkContext
from mcp.server.mcpserver.exceptions import ToolError as SdkToolError
from mcp.server.mcpserver.tools.base import Tool as SdkTool
from mcp.shared.exceptions import MCPError
from mcp_types import INVALID_PARAMS, CallToolResult, TextContent
from pydantic import BaseModel, Field

from agentconnect.mcp.server import create_team_mcp
from agentconnect.team import Team
from mcp import Client

_ran: list[str] = []


async def ping() -> dict[str, str]:
    """Return a heartbeat."""
    return {"status": "ok"}


def tally(count: int) -> dict[str, int]:
    """Postponed integer annotation."""
    _ran.append(f"tally:{count}")
    return {"count": count}


def counted(
    count: Annotated[int, Field(ge=1, description="how many")],
    mode: Literal["fast", "slow"] = "fast",
) -> dict[str, str]:
    """Count items in a named mode."""
    _ran.append(f"{mode}:{count}")
    return {"mode": mode, "count": str(count)}


class Item(BaseModel):
    sku: str
    qty: Annotated[int, Field(ge=1)]


def pack(item: Item) -> dict[str, Any]:
    """Pack one nested item."""
    _ran.append(f"{item.sku}:{item.qty}")
    return {"sku": item.sku, "qty": item.qty}


class Score(BaseModel):
    value: int
    label: str


def score(n: int) -> Score:
    """Return a typed score."""
    return Score(value=n, label="ok")


async def echo_request(ctx: SdkContext) -> dict[str, str]:
    """Echo the injected request id."""
    return {"request_id": str(ctx.request_id)}


async def echo_label(ctx: str) -> dict[str, str]:
    """Treat ctx as an ordinary string argument."""
    _ran.append(ctx)
    return {"ctx": ctx}


def boxed() -> CallToolResult:
    """Return an explicit MCP result."""
    return CallToolResult(content=[TextContent(type="text", text="hello")])


def fail_doc() -> str:
    """Raise a recoverable extra-tool failure."""
    raise SdkToolError("Please choose a different document")


def boom() -> str:
    """Crash with internals that must stay off the wire."""
    raise RuntimeError("secret internals")


def protocol() -> str:
    """Raise a protocol error."""
    raise MCPError(INVALID_PARAMS, "not ready")


def type_boom() -> str:
    """Raise TypeError during execution, not during binding."""
    raise TypeError("internal type confusion")


def first(a: str) -> str:
    """First duplicate-name extra."""
    return a


def second(b: int) -> int:
    """Second extra renamed to collide."""
    return b


def _body(result: Any) -> dict[str, Any]:
    if result.structured_content:
        return dict(result.structured_content)
    if result.content:
        text = result.content[0].text
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}
        if isinstance(parsed, dict):
            return parsed
        return {"value": parsed}
    raise AssertionError("empty tool result")


def _error_text(result: Any) -> str:
    assert result.is_error
    return " ".join(getattr(item, "text", "") or "" for item in result.content or [])


def _listed_schema(tool: Any) -> dict[str, Any]:
    schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None)
    if hasattr(schema, "model_dump"):
        schema = schema.model_dump()
    assert isinstance(schema, dict)
    return schema


def _listed_output(tool: Any) -> dict[str, Any]:
    schema = getattr(tool, "outputSchema", None) or getattr(tool, "output_schema", None)
    if hasattr(schema, "model_dump"):
        schema = schema.model_dump(by_alias=True)
    assert isinstance(schema, dict)
    return schema


@pytest.fixture(autouse=True)
def _clear_ran() -> None:
    _ran.clear()


@pytest.mark.asyncio
async def test_extra_tools_validate_annotations_and_nested_inputs():
    team = await Team("content-squad", tools=[counted, pack, tally]).start()
    mcp = create_team_mcp(team)
    try:
        async with Client(mcp) as client:
            tools = {item.name: item for item in (await client.list_tools()).tools}
            tally_schema = _listed_schema(tools["tally"])
            tally_count = (tally_schema.get("properties") or {}).get("count") or {}
            assert tally_count.get("type") == "integer"
            counted_schema = _listed_schema(tools["counted"])
            count_field = (counted_schema.get("properties") or {}).get("count") or {}
            mode_field = (counted_schema.get("properties") or {}).get("mode") or {}
            assert (
                count_field.get("minimum") == 1
                or count_field.get("exclusiveMinimum") == 0
            )
            assert "how many" in (count_field.get("description") or "")
            assert set(mode_field.get("enum") or ()) == {"fast", "slow"}

            ok = _body(await client.call_tool("counted", {"count": 2}))
            assert ok["mode"] == "fast"
            assert _ran == ["fast:2"]

            tallied = _body(await client.call_tool("tally", {"count": 4}))
            assert tallied == {"count": 4}
            assert _ran == ["fast:2", "tally:4"]

            bad_count = await client.call_tool("counted", {"count": "oops"})
            assert bad_count.is_error
            assert _ran == ["fast:2", "tally:4"]

            bad_mode = await client.call_tool("counted", {"count": 2, "mode": "nope"})
            assert bad_mode.is_error
            assert _ran == ["fast:2", "tally:4"]

            packed = _body(
                await client.call_tool("pack", {"item": {"sku": "a", "qty": 3}})
            )
            assert packed == {"sku": "a", "qty": 3}
            nested = await client.call_tool("pack", {"item": {"sku": "a", "qty": 0}})
            assert nested.is_error
            assert _ran == ["fast:2", "tally:4", "a:3"]
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_extra_tools_inject_context_by_annotation_not_name():
    team = await Team("content-squad", tools=[echo_request, echo_label]).start()
    mcp = create_team_mcp(team)
    try:
        async with Client(mcp) as client:
            tools = {item.name: item for item in (await client.list_tools()).tools}
            request_schema = _listed_schema(tools["echo_request"])
            label_schema = _listed_schema(tools["echo_label"])
            assert "ctx" not in (request_schema.get("properties") or {})
            assert "ctx" in (label_schema.get("properties") or {})

            injected = _body(await client.call_tool("echo_request", {}))
            assert injected["request_id"]

            missing = await client.call_tool("echo_label", {})
            assert missing.is_error
            assert _ran == []

            labeled = _body(await client.call_tool("echo_label", {"ctx": "hello"}))
            assert labeled["ctx"] == "hello"
            assert _ran == ["hello"]
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_extra_tools_preserve_typed_results_and_error_kinds():
    extras = [score, boxed, fail_doc, boom, protocol, type_boom]
    team = await Team("content-squad", tools=extras).start()
    mcp = create_team_mcp(team)
    try:
        async with Client(mcp) as client:
            tools = {item.name: item for item in (await client.list_tools()).tools}
            score_out = _listed_output(tools["score"])
            assert "value" in (score_out.get("properties") or {})
            assert "label" in (score_out.get("properties") or {})
            scored = _body(await client.call_tool("score", {"n": 7}))
            assert scored == {"value": 7, "label": "ok"}

            boxed_result = await client.call_tool("boxed", {})
            assert not boxed_result.is_error
            assert boxed_result.content[0].text == "hello"

            failed = await client.call_tool("fail_doc", {})
            assert failed.is_error
            text = _error_text(failed)
            assert "Please choose a different document" in text

            crashed = await client.call_tool("boom", {})
            assert crashed.is_error
            crash_text = _error_text(crashed)
            assert "secret internals" not in crash_text
            assert "Error executing tool boom" in crash_text

            type_failed = await client.call_tool("type_boom", {})
            assert type_failed.is_error
            type_text = _error_text(type_failed)
            assert "internal type confusion" not in type_text
            assert "Error executing tool type_boom" in type_text

            failed = False
            try:
                await client.call_tool("protocol", {})
            except* MCPError as group:
                failed = True
                codes = [
                    item.code for item in group.exceptions if isinstance(item, MCPError)
                ]
            assert failed
            assert INVALID_PARAMS in codes
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_sync_extra_tool_lets_other_work_progress(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    loop = asyncio.get_running_loop()

    def hold() -> dict[str, str]:
        """Block until the test releases this extra."""
        started.set()
        if not release.wait(timeout=2.0):
            raise TimeoutError("hold was not released")
        finished.set()
        return {"status": "held"}

    async def _assert_overlap(mcp: Any, *, expect_progress: bool) -> None:
        started.clear()
        release.clear()
        finished.clear()
        ping_future: concurrent.futures.Future[Any] | None = None
        progressed = False

        async with Client(mcp) as holder, Client(mcp) as other:
            held = asyncio.create_task(holder.call_tool("hold", {}))

            def coordinator() -> None:
                nonlocal ping_future, progressed
                try:
                    if not started.wait(timeout=1.0):
                        return
                    ping_future = asyncio.run_coroutine_threadsafe(
                        other.call_tool("ping", {}),
                        loop,
                    )
                    try:
                        ping_future.result(timeout=0.5 if expect_progress else 0.15)
                    except concurrent.futures.TimeoutError:
                        pass
                    progressed = (
                        ping_future.done()
                        and ping_future.exception() is None
                        and not finished.is_set()
                    )
                finally:
                    release.set()

            worker = threading.Thread(target=coordinator, daemon=True)
            worker.start()
            try:
                held_result = await asyncio.wait_for(held, timeout=2.5)
                worker.join(timeout=2.5)
                assert ping_future is not None
                ping_result = await asyncio.wait_for(
                    asyncio.wrap_future(ping_future), timeout=1.0
                )
            finally:
                release.set()
                if not held.done():
                    await asyncio.wait_for(held, timeout=1.0)

        assert not held_result.is_error
        assert _body(held_result).get("status") == "held"
        assert not ping_result.is_error
        assert _body(ping_result).get("status") == "ok"
        assert progressed is expect_progress

    team = await Team("content-squad", tools=[hold, ping]).start()
    mcp = create_team_mcp(team)
    try:
        await _assert_overlap(mcp, expect_progress=True)

        async def run_inline(func: Any, *args: Any, **_kwargs: Any) -> Any:
            return func(*args)

        from mcp.server.mcpserver.utilities import func_metadata as sdk_fn_meta

        monkeypatch.setattr(sdk_fn_meta.anyio.to_thread, "run_sync", run_inline)
        await _assert_overlap(mcp, expect_progress=False)
    finally:
        await team.stop()


@pytest.mark.asyncio
async def test_duplicate_extra_names_are_rejected():
    colliding = second
    colliding.__name__ = "first"
    try:
        with pytest.raises(ValueError, match="already registered"):
            Team("content-squad", tools=[first, colliding])
        team = await Team("content-squad").start()
        try:
            with pytest.raises(ValueError, match="already registered"):
                create_team_mcp(team, extra_tools=[first, colliding])
        finally:
            await team.stop()
    finally:
        colliding.__name__ = "second"


@pytest.mark.asyncio
async def test_listed_extra_names_match_one_implementation():
    team = await Team("content-squad", tools=[ping, counted]).start()
    mcp = create_team_mcp(team)
    try:
        async with Client(mcp) as client:
            names = [item.name for item in (await client.list_tools()).tools]
            extras = [name for name in names if name in {"ping", "counted"}]
            assert extras == ["ping", "counted"]
            assert names.count("ping") == 1
            listed = (await client.list_tools()).tools
            ping_tool = next(item for item in listed if item.name == "ping")
            assert _listed_schema(ping_tool) == SdkTool.from_function(ping).parameters
    finally:
        await team.stop()
