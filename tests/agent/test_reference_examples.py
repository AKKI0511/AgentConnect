"""Published reference snippets. Setup lives here, not in every docstring."""

from __future__ import annotations

import inspect
import re
import textwrap

import pytest
from tests.agent.conftest import DeferredAgent, EchoAgent

import agentconnect
import agentconnect.agent as agent_api
import agentconnect.agent.base as agent_base
import agentconnect.agent.context as agent_context
from agentconnect.agent.base import BaseAgent
from agentconnect.agent.context import Context
from agentconnect.core.base import parse_schema
from agentconnect.core.operations import LeaseRequest
from agentconnect.team import Team

_FENCE = re.compile(r"```python\n(.*?)```", re.DOTALL)


def _python_examples(obj: object) -> list[str]:
    doc = inspect.getdoc(obj)
    assert doc, f"missing docstring on {obj}"
    blocks = [textwrap.dedent(block.lstrip("\n")) for block in _FENCE.findall(doc)]
    assert blocks, f"no python example on {obj}"
    return blocks


def _documented_objects():
    modules = (agentconnect, agent_api, agent_base, agent_context)
    seen: set[int] = set()
    for module in modules:
        candidates = [module]
        for value in vars(module).values():
            if inspect.isclass(value) and value.__module__ == module.__name__:
                candidates.append(value)
                candidates.extend(
                    member
                    for name, member in vars(value).items()
                    if not name.startswith("_") or name == "__init__"
                )
        for obj in candidates:
            target = obj.fget if isinstance(obj, property) else obj
            key = id(target)
            if key in seen:
                continue
            seen.add(key)
            doc = inspect.getdoc(target)
            if doc and _FENCE.search(doc):
                yield target


def _compile_fragment(src: str, label: str) -> None:
    wrapped = "async def _example():\n" + textwrap.indent(src, "    ")
    compile(wrapped, label, "exec")


@pytest.mark.asyncio
async def test_package_orientation_fragments(team: Team, monkeypatch) -> None:
    import contextlib
    import io
    import sys
    from types import SimpleNamespace

    calls = []
    configured_writer = object()

    class RunnerDouble:
        @staticmethod
        async def run(agent, *, input):
            assert agent is configured_writer
            calls.append(input)
            return SimpleNamespace(final_output="Release note draft.")

    monkeypatch.setitem(sys.modules, "agents", SimpleNamespace(Runner=RunnerDouble))
    namespace = {"writer_agent": configured_writer}
    adapter_src, request_src = _python_examples(agentconnect)
    exec(compile(adapter_src, "<agentconnect adapter>", "exec"), namespace)
    researcher = EchoAgent(name="researcher")
    reviewer = EchoAgent(name="reviewer")
    namespace.update(team=team, researcher=researcher, reviewer=reviewer)
    wrapped = "async def _example():\n" + textwrap.indent(
        request_src + "\nreturn writer, ticket\n", "    "
    )
    exec(compile(wrapped, "<agentconnect request>", "exec"), namespace)
    stdout = io.StringIO()
    writer = None
    try:
        with contextlib.redirect_stdout(stdout):
            writer, ticket = await namespace["_example"]()
        assert ticket.state == "completed"
        assert stdout.getvalue().strip() == "Release note draft."
        assert calls == [
            "Draft a release note from these findings: search is faster, "
            "and request deadlines now appear in the activity log."
        ]
        assert writer.address == "writer@content-squad"
        assert researcher.address == "researcher@content-squad"
        assert reviewer.address == "reviewer@content-squad"
        assert await writer.handle(SimpleNamespace(kind="event"), None) is None
        assert len(calls) == 1
    finally:
        if writer is not None:
            await writer.leave()
        await researcher.leave()
        await reviewer.leave()


def test_agent_workflow_examples_compile() -> None:
    for obj in _documented_objects():
        for index, src in enumerate(_python_examples(obj)):
            _compile_fragment(src, f"<{getattr(obj, '__qualname__', obj)}:{index}>")


def test_parse_schema_example() -> None:
    src = _python_examples(parse_schema)[0]
    namespace: dict[str, object] = {}
    exec(compile(src, "<parse_schema.__doc__>", "exec"), namespace)
    lease = namespace["lease"]
    assert isinstance(lease, LeaseRequest)
    assert lease.max_items == 2


@pytest.mark.asyncio
async def test_open_ticket_has_no_content(team: Team) -> None:
    writer = DeferredAgent(name="writer")
    caller = EchoAgent(name="caller")
    await writer.join(team)
    await caller.join(team)
    try:
        pending = await caller.ask("writer", "later", collect="ticket")
        assert pending.state == "open"
        with pytest.raises(AttributeError):
            pending.content
        ticket = await caller.get_result(pending.id)
        assert ticket.state == "open"
        with pytest.raises(AttributeError):
            ticket.content
    finally:
        await writer.leave()
        await caller.leave()


@pytest.mark.asyncio
async def test_ask_and_get_result_fragments_collect_same_work(team: Team) -> None:
    import asyncio
    import contextlib
    import io

    writer = DeferredAgent(name="writer")
    agent = EchoAgent(name="caller")
    await writer.join(team)
    await agent.join(team)
    namespace = {"agent": agent, "release_findings": "Search is faster."}
    ask_src = _python_examples(BaseAgent.ask)[0]
    wrapped = "async def _ask_example():\n" + textwrap.indent(
        ask_src + "\nreturn ticket\n", "    "
    )
    exec(compile(wrapped, "<BaseAgent.ask>", "exec"), namespace)
    result_src = _python_examples(BaseAgent.get_result)[0]
    wrapped = "async def _result_example():\n" + textwrap.indent(
        result_src + "\nreturn ticket\n", "    "
    )
    exec(compile(wrapped, "<BaseAgent.get_result>", "exec"), namespace)
    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            pending = await namespace["_ask_example"]()
            assert pending.state == "open"
            namespace["pending"] = pending
            assert (await namespace["_result_example"]()).state == "open"
            while writer.ticket_handle is None:
                await asyncio.sleep(0.01)
            await writer.ticket_handle.reply("Release note draft.")
            ticket = await namespace["_result_example"]()
        assert ticket.state == "completed"
        assert ticket.id == pending.id
        assert stdout.getvalue().strip() == "Release note draft."
        assert writer.seen.content == {
            "task": "Draft a release note.",
            "findings": "Search is faster.",
        }
    finally:
        await agent.leave()
        await writer.leave()


@pytest.mark.asyncio
async def test_find_snippet_asks_the_match(team: Team) -> None:
    import contextlib
    import io

    class NotesWriter(BaseAgent):
        profile = {
            "summary": "Turns notes into a short draft.",
            "skills": [
                {
                    "name": "drafting",
                    "description": "Draft from notes.",
                }
            ],
        }

        async def handle(self, message, ctx):
            if message.kind != "request":
                return None
            return f"Draft from notes: {message.content}"

    src = _python_examples(BaseAgent.find)[0]
    writer = NotesWriter(name="writer")
    agent = EchoAgent(name="caller")
    await writer.join(team)
    await agent.join(team)
    try:
        namespace = {"agent": agent, "release_findings": "Search is faster."}
        wrapped = "async def _example():\n" + textwrap.indent(src, "    ")
        exec(compile(wrapped, "<BaseAgent.find>", "exec"), namespace)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            await namespace["_example"]()
        assert "Search is faster." in stdout.getvalue()
        assert "Draft a release note." in stdout.getvalue()
    finally:
        await agent.leave()
        await writer.leave()


@pytest.mark.asyncio
async def test_context_fragments_keep_parent_open_until_callback(team: Team) -> None:
    import asyncio

    ask_src = _python_examples(Context.ask)[0]
    defer_src, reply_src = _python_examples(Context.defer)
    namespace = {}
    wrapped = "async def inspect_child(ctx, draft):\n" + textwrap.indent(
        ask_src + "\nreturn ticket\n", "    "
    )
    exec(compile(wrapped, "<Context.ask>", "exec"), namespace)
    wrapped = "async def defer_example(ctx):\n" + textwrap.indent(
        defer_src + "\nreturn pending\n", "    "
    )
    exec(compile(wrapped, "<Context.defer handler>", "exec"), namespace)
    wrapped = "async def completion_callback(pending, draft):\n" + textwrap.indent(
        reply_src, "    "
    )
    exec(compile(wrapped, "<Context.defer>", "exec"), namespace)

    class Relay(BaseAgent):
        child = None
        pending = None

        async def handle(self, message, ctx):
            self.child = await namespace["inspect_child"](ctx, "Draft to check.")
            self.pending = await namespace["defer_example"](ctx)

    editor = DeferredAgent(name="editor")
    relay = Relay(name="relay")
    caller = EchoAgent(name="caller")
    await editor.join(team)
    await relay.join(team)
    await caller.join(team)
    try:
        parent = await caller.ask("relay", "quarterly notes", collect="ticket")
        while relay.pending is None or editor.ticket_handle is None:
            await asyncio.sleep(0.01)
        assert relay.child.state == "open"
        assert (await caller.get_result(parent.id)).state == "open"
        await editor.ticket_handle.reply("Checked draft.")
        child = await relay.get_result(relay.child.id)
        assert child.state == "completed"
        await namespace["completion_callback"](relay.pending, child.content)
        result = await caller.get_result(parent.id)
        assert result.state == "completed"
        assert result.content == "Checked draft."
        assert editor.seen.parent_id == parent.id
    finally:
        await caller.leave()
        await relay.leave()
        await editor.leave()
