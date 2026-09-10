"""Session renewal, deferred in-flight caps, and handler causality."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from agentconnect.agent import BaseAgent
from agentconnect.agent.errors import SessionError
from agentconnect.agent.session import Session, _TrackedLease
from agentconnect.team import Team
from agentconnect.transport.runtime import TransportError
from tests.agent.conftest import DeferredAgent, EchoAgent


@pytest.mark.asyncio
async def test_handler_longer_than_lease_finishes_once():
    runtime = await Team(
        "content-squad",
        lease_ttl_seconds=0.25,
        sweep_interval_seconds=0.05,
        session_ttl_seconds=30,
    ).start()

    class Slow(EchoAgent):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.calls = 0

        async def handle(self, message, ctx):
            self.calls += 1
            await asyncio.sleep(0.9)
            return {"slow": message.content}

    writer = Slow(name="writer")
    researcher = EchoAgent(name="researcher")
    await writer.join(runtime)
    await researcher.join(runtime)
    try:
        ticket = await researcher.ask("writer", "long", deadline_seconds=8)
        assert ticket.state == "completed"
        assert ticket.content == {"slow": "long"}
        assert writer.calls == 1
    finally:
        await writer.leave()
        await researcher.leave()
        await runtime.stop()


@pytest.mark.asyncio
async def test_deferred_reply_counts_against_max_in_flight():
    runtime = await Team(
        "content-squad",
        lease_ttl_seconds=8,
        sweep_interval_seconds=0.05,
        session_ttl_seconds=30,
    ).start()
    writer = DeferredAgent(name="writer", max_in_flight=1)
    researcher = EchoAgent(name="researcher")
    await writer.join(runtime)
    await researcher.join(runtime)
    try:
        first = await researcher.ask(
            "writer", "one", deadline_seconds=8, collect="ticket"
        )
        second = await researcher.ask(
            "writer", "two", deadline_seconds=8, collect="ticket"
        )
        for _ in range(40):
            if writer.ticket_handle is not None:
                break
            await asyncio.sleep(0.05)
        assert writer.ticket_handle is not None
        await asyncio.sleep(0.2)
        assert writer.seen is not None
        assert writer.seen.content == "one"
        assert first.state == "open"
        assert second.state == "open"
        await writer.ticket_handle.reply("first-done")
        for _ in range(40):
            if writer.seen is not None and writer.seen.content == "two":
                break
            await asyncio.sleep(0.05)
        assert writer.seen.content == "two"
        assert writer.ticket_handle is not None
        await writer.ticket_handle.reply("second-done")
        done = await researcher.get_result(second.id)
        while done.state == "open":
            await asyncio.sleep(0.05)
            done = await researcher.get_result(second.id)
        assert done.content == "second-done"
    finally:
        await writer.leave()
        await researcher.leave()
        await runtime.stop()


@pytest.mark.asyncio
async def test_ctx_ask_inherits_parent_thread_and_deadline():
    runtime = await Team("content-squad", session_ttl_seconds=30).start()
    seen: dict[str, object] = {}

    class Editor(EchoAgent):
        async def handle(self, message, ctx):
            seen["editor_parent"] = message.parent_id
            seen["editor_trace"] = message.trace_id
            seen["editor_thread"] = message.thread_id
            seen["editor_deadline"] = message.deadline
            seen["editor_history"] = list(ctx.history)
            return {"edit": message.content}

    class Writer(EchoAgent):
        async def handle(self, message, ctx):
            seen["writer_id"] = message.id
            seen["writer_trace"] = message.trace_id
            seen["writer_thread"] = message.thread_id
            inner = await ctx.ask("editor", "tighten", collect="wait")
            if inner.state != "completed":
                ctx.defer()
                return None
            return inner.content

    writer = Writer(name="writer")
    editor = Editor(name="editor")
    researcher = EchoAgent(name="researcher")
    await writer.join(runtime)
    await editor.join(runtime)
    await researcher.join(runtime)
    try:
        ticket = await researcher.ask(
            "writer",
            "draft",
            deadline_seconds=8,
            collect="wait",
        )
        assert ticket.state == "completed"
        assert ticket.content == {"edit": "tighten"}
        assert seen["editor_parent"] == seen["writer_id"]
        assert seen["editor_trace"] == seen["writer_trace"]
        assert seen["editor_thread"] != seen["writer_thread"]
        assert seen["editor_history"] == []
        assert seen["editor_deadline"] == ticket.deadline
    finally:
        await writer.leave()
        await editor.leave()
        await researcher.leave()
        await runtime.stop()


@pytest.mark.asyncio
async def test_explicit_child_deadline_after_parent_is_rejected():
    runtime = await Team("content-squad", session_ttl_seconds=30).start()
    seen: dict[str, object] = {}

    class Editor(EchoAgent):
        async def handle(self, message, ctx):
            return {"edit": message.content}

    class Writer(EchoAgent):
        async def handle(self, message, ctx):
            with pytest.raises(SessionError) as exc:
                await ctx.ask("editor", "tighten", deadline_seconds=120)
            seen["code"] = exc.value.code
            return "ok"

    writer = Writer(name="writer")
    editor = Editor(name="editor")
    researcher = EchoAgent(name="researcher")
    await writer.join(runtime)
    await editor.join(runtime)
    await researcher.join(runtime)
    try:
        ticket = await researcher.ask("writer", "draft", deadline_seconds=8)
        assert ticket.state == "completed"
        assert seen["code"] == "invalid_request"
    finally:
        await writer.leave()
        await editor.leave()
        await researcher.leave()
        await runtime.stop()


@pytest.mark.asyncio
async def test_ctx_ask_same_peer_continues_thread():
    runtime = await Team("content-squad", session_ttl_seconds=30).start()
    threads: list[str | None] = []

    class Writer(EchoAgent):
        async def handle(self, message, ctx):
            threads.append(message.thread_id)
            if message.content == "follow":
                return {"ack": True}
            inner = await ctx.ask("researcher", "follow", deadline_seconds=5)
            return inner.content

    class Researcher(BaseAgent):
        async def handle(self, message, ctx):
            threads.append(message.thread_id)
            return {"pong": True}

    writer = Writer(name="writer")
    researcher = Researcher(name="researcher")
    await writer.join(runtime)
    await researcher.join(runtime)
    thread_id = str(uuid.uuid4())
    try:
        ticket = await researcher.ask(
            "writer", "start", deadline_seconds=8, thread_id=thread_id
        )
        assert ticket.state == "completed"
        assert ticket.content == {"pong": True}
        assert len(threads) >= 2
        assert threads[0] == threads[1]
    finally:
        await writer.leave()
        await researcher.leave()
        await runtime.stop()


@pytest.mark.asyncio
async def test_cycle_at_concurrency_one_expires_by_deadline():
    runtime = await Team(
        "content-squad",
        wait_hold_seconds=3,
        sweep_interval_seconds=0.05,
        session_ttl_seconds=30,
        lease_ttl_seconds=8,
    ).start()

    class Cycle(BaseAgent):
        def __init__(self, peer: str, **kwargs):
            super().__init__(**kwargs)
            self.peer = peer
            self.handled = 0

        async def handle(self, message, ctx):
            self.handled += 1
            nested = await ctx.ask(self.peer, "pong", collect="wait")
            if nested.state == "completed":
                return nested.content
            ctx.defer()
            return None

    agent_a = Cycle("agent-b", name="agent-a")
    agent_b = Cycle("agent-a", name="agent-b")
    researcher = EchoAgent(name="researcher")
    await agent_a.join(runtime)
    await agent_b.join(runtime)
    await researcher.join(runtime)
    try:
        ticket = await researcher.ask(
            "agent-a",
            "start",
            deadline_seconds=1.5,
            collect="wait",
        )
        assert ticket.state == "expired"
        assert agent_a.handled == 1
        assert agent_b.handled == 1
    finally:
        await agent_a.leave()
        await agent_b.leave()
        await researcher.leave()
        await runtime.stop()


@pytest.mark.asyncio
async def test_team_tools_ask_from_handler_inherits_parent():
    runtime = await Team("content-squad", session_ttl_seconds=30).start()
    seen: dict[str, object] = {}

    class Editor(EchoAgent):
        async def handle(self, message, ctx):
            seen["parent_id"] = message.parent_id
            seen["trace_id"] = message.trace_id
            seen["thread_id"] = message.thread_id
            return {"edit": message.content}

    class Writer(EchoAgent):
        def __init__(self, name: str):
            super().__init__(name=name)
            self.tools = self.team_tools()

        async def handle(self, message, ctx):
            seen["writer_id"] = message.id
            seen["writer_trace"] = message.trace_id
            seen["writer_thread"] = message.thread_id
            ticket = await self.tools.ask(
                recipient="editor",
                content="tighten",
            )
            if ticket["state"] == "completed":
                return ticket["response"]["content"]
            return ticket

    writer = Writer(name="writer")
    editor = Editor(name="editor")
    researcher = EchoAgent(name="researcher")
    await writer.join(runtime)
    await editor.join(runtime)
    await researcher.join(runtime)
    try:
        ticket = await researcher.ask("writer", "draft", deadline_seconds=8)
        assert ticket.state == "completed"
        assert ticket.content == {"edit": "tighten"}
        assert seen["parent_id"] == seen["writer_id"]
        assert seen["trace_id"] == seen["writer_trace"]
        assert seen["thread_id"] != seen["writer_thread"]
    finally:
        await writer.leave()
        await editor.leave()
        await researcher.leave()
        await runtime.stop()


async def _until_terminal(agent, ticket_id, *, timeout=8.0):
    loop = asyncio.get_running_loop()
    limit = loop.time() + timeout
    ticket = await agent.get_result(ticket_id)
    while ticket.state == "open" and loop.time() < limit:
        await asyncio.sleep(0.05)
        ticket = await agent.get_result(ticket_id)
    return ticket


@pytest.mark.asyncio
async def test_saved_context_ask_keeps_delivery_parent():
    runtime = await Team("content-squad", session_ttl_seconds=30).start()
    seen: dict[str, object] = {}

    class Editor(EchoAgent):
        async def handle(self, message, ctx):
            seen["parent_id"] = message.parent_id
            return {"edit": message.content}

    class Writer(EchoAgent):
        async def handle(self, message, ctx):
            seen["writer_id"] = message.id
            handle = ctx.defer()
            asyncio.create_task(self._later(ctx, handle))
            return None

        async def _later(self, ctx, handle):
            inner = await ctx.ask("editor", "tighten", collect="wait")
            if inner.state == "completed":
                await handle.reply(inner.content)

    writer = Writer(name="writer")
    editor = Editor(name="editor")
    researcher = EchoAgent(name="researcher")
    await writer.join(runtime)
    await editor.join(runtime)
    await researcher.join(runtime)
    try:
        pending = await researcher.ask(
            "writer", "draft", deadline_seconds=8, collect="ticket"
        )
        ticket = await _until_terminal(researcher, pending.id)
        assert ticket.state == "completed"
        assert ticket.content == {"edit": "tighten"}
        assert seen["parent_id"] == seen["writer_id"]
    finally:
        await writer.leave()
        await editor.leave()
        await researcher.leave()
        await runtime.stop()


@pytest.mark.asyncio
async def test_cancelled_handler_stops_renewal_and_occupancy():
    runtime = await Team(
        "content-squad",
        lease_ttl_seconds=1.0,
        session_ttl_seconds=30,
        sweep_interval_seconds=0.05,
    ).start()

    class Slow(BaseAgent):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.started = asyncio.Event()
            self.cancelled = asyncio.Event()
            self.seen: list[object] = []

        async def handle(self, message, ctx):
            self.seen.append(message.content)
            if message.content == "first":
                self.started.set()
                try:
                    await asyncio.sleep(30)
                except asyncio.CancelledError:
                    self.cancelled.set()
                    raise
            return {"echo": message.content}

    writer = Slow(name="writer", max_in_flight=1)
    researcher = EchoAgent(name="researcher")
    await writer.join(runtime)
    await researcher.join(runtime)
    try:
        first = await researcher.ask(
            "writer", "first", deadline_seconds=8, collect="ticket"
        )
        await asyncio.wait_for(writer.started.wait(), timeout=5)
        session = writer._session
        assert session is not None
        second_task = asyncio.create_task(
            researcher.ask("writer", "second", deadline_seconds=8)
        )
        await asyncio.sleep(0.1)
        tasks = list(session._inflight)
        assert tasks
        tasks[0].cancel()
        await asyncio.wait_for(writer.cancelled.wait(), timeout=5)
        for _ in range(50):
            if session._occupied() == 0:
                break
            await asyncio.sleep(0.01)
        assert session._occupied() == 0
        second = await asyncio.wait_for(second_task, timeout=8)
        assert second.state == "completed"
        assert second.content == {"echo": "second"}
        first = await researcher.get_result(first.id)
        assert first.state == "open"
        assert "second" in writer.seen
    finally:
        await writer.leave()
        await researcher.leave()
        await runtime.stop()


@pytest.mark.asyncio
async def test_expiry_cancels_handler_and_frees_occupancy():
    runtime = await Team(
        "content-squad",
        lease_ttl_seconds=0.2,
        sweep_interval_seconds=0.05,
        session_ttl_seconds=30,
    ).start()

    class Slow(BaseAgent):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.calls = 0
            self.cancelled = 0

        async def handle(self, message, ctx):
            self.calls += 1
            if message.content == "next":
                return {"echo": message.content}
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                self.cancelled += 1
                raise
            return {"late": message.content}

    writer = Slow(name="writer", max_in_flight=1)
    researcher = EchoAgent(name="researcher")
    await writer.join(runtime)
    await researcher.join(runtime)
    try:
        pending = await researcher.ask(
            "writer", "hold", deadline_seconds=0.4, collect="ticket"
        )
        first = await _until_terminal(researcher, pending.id, timeout=5)
        assert first.state == "expired"
        second = await researcher.ask("writer", "next", deadline_seconds=5)
        assert second.state == "completed"
        assert second.content == {"echo": "next"}
        assert writer.cancelled >= 1
    finally:
        await writer.leave()
        await researcher.leave()
        await runtime.stop()


@pytest.mark.asyncio
async def test_deferred_expiry_stops_renewal_and_frees_occupancy():
    runtime = await Team(
        "content-squad",
        lease_ttl_seconds=0.2,
        sweep_interval_seconds=0.05,
        session_ttl_seconds=30,
    ).start()
    writer = DeferredAgent(name="writer", max_in_flight=1)
    researcher = EchoAgent(name="researcher")
    await writer.join(runtime)
    await researcher.join(runtime)
    try:
        pending = await researcher.ask(
            "writer", "hold", deadline_seconds=0.4, collect="ticket"
        )
        for _ in range(40):
            if writer.ticket_handle is not None:
                break
            await asyncio.sleep(0.05)
        assert writer.ticket_handle is not None
        first = await _until_terminal(researcher, pending.id, timeout=5)
        assert first.state == "expired"
        second = await researcher.ask(
            "writer", "next", deadline_seconds=5, collect="ticket"
        )
        for _ in range(40):
            if writer.seen is not None and writer.seen.content == "next":
                break
            await asyncio.sleep(0.05)
        assert writer.ticket_handle is not None
        await writer.ticket_handle.reply("second-done")
        done = await _until_terminal(researcher, second.id, timeout=5)
        assert done.state == "completed"
        assert done.content == "second-done"
    finally:
        await writer.leave()
        await researcher.leave()
        await runtime.stop()


@pytest.mark.asyncio
async def test_long_running_wait_returns_open_then_completes():
    runtime = await Team(
        "content-squad",
        wait_hold_seconds=0.1,
        lease_ttl_seconds=0.2,
        sweep_interval_seconds=0.05,
        session_ttl_seconds=30,
    ).start()

    class AgentC(EchoAgent):
        async def handle(self, message, ctx):
            await asyncio.sleep(0.9)
            return {"from": "c"}

    class AgentB(BaseAgent):
        async def handle(self, message, ctx):
            handle = ctx.defer()
            inner = await ctx.ask("agent-c", "go", collect="wait")
            while inner.state == "open":
                await asyncio.sleep(0.05)
                inner = await self.get_result(inner.id)
            if inner.state == "completed":
                await handle.reply(inner.content)
            return None

    agent_c = AgentC(name="agent-c")
    agent_b = AgentB(name="agent-b")
    researcher = EchoAgent(name="researcher")
    await agent_c.join(runtime)
    await agent_b.join(runtime)
    await researcher.join(runtime)
    try:
        pending = await researcher.ask(
            "agent-b", "start", deadline_seconds=8, collect="wait"
        )
        assert pending.state == "open"
        ticket = await _until_terminal(researcher, pending.id, timeout=8)
        assert ticket.state == "completed"
        assert ticket.content == {"from": "c"}
        assert ticket.id == pending.id
    finally:
        await researcher.leave()
        await agent_b.leave()
        await agent_c.leave()
        await runtime.stop()


@pytest.mark.asyncio
async def test_hard_expiry_cancels_long_handler():
    runtime = await Team(
        "content-squad",
        wait_hold_seconds=0.1,
        lease_ttl_seconds=0.2,
        sweep_interval_seconds=0.05,
        session_ttl_seconds=30,
    ).start()

    class Slow(BaseAgent):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.cancelled = 0

        async def handle(self, message, ctx):
            try:
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                self.cancelled += 1
                raise
            return {"late": True}

    writer = Slow(name="writer")
    researcher = EchoAgent(name="researcher")
    await writer.join(runtime)
    await researcher.join(runtime)
    try:
        pending = await researcher.ask(
            "writer", "hold", deadline_seconds=0.4, collect="wait"
        )
        assert pending.state in {"open", "expired"}
        ticket = await _until_terminal(researcher, pending.id, timeout=5)
        assert ticket.state == "expired"
        assert ticket.id == pending.id
        await asyncio.sleep(0.2)
        assert writer.cancelled >= 1
    finally:
        await writer.leave()
        await researcher.leave()
        await runtime.stop()


@pytest.mark.asyncio
async def test_occupied_counts_deferred_and_unwinding_once_each():
    session = Session.__new__(Session)
    session.max_in_flight = 2
    session._active = {}
    session._inflight = set()
    session._active["deferred"] = _TrackedLease(None, "2026-01-01T00:00:00Z", task=None)
    assert session._occupied() == 1
    assert session._room() == 1

    async def _hold():
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await asyncio.sleep(0)
            raise

    unwinding = asyncio.create_task(_hold())
    session._inflight.add(unwinding)
    try:
        assert session._occupied() == 2
        assert session._room() == 0
        session._active["running"] = _TrackedLease(
            None, "2026-01-01T00:00:00Z", task=unwinding
        )
        assert session._occupied() == 2
        del session._active["running"]
        assert session._occupied() == 2
        assert session._room() == 0
    finally:
        unwinding.cancel()
        await asyncio.gather(unwinding, return_exceptions=True)


@pytest.mark.asyncio
async def test_third_delivery_waits_for_deferred_and_unwinding_slots():
    runtime = await Team(
        "content-squad",
        lease_ttl_seconds=0.2,
        sweep_interval_seconds=0.05,
        session_ttl_seconds=30,
    ).start()

    class Mixed(BaseAgent):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.deferred = None
            self.slow_started = asyncio.Event()
            self.in_cleanup = asyncio.Event()
            self.cleanup_gate = asyncio.Event()
            self.third_started = asyncio.Event()
            self.seen: list[object] = []

        async def handle(self, message, ctx):
            self.seen.append(message.content)
            if message.content == "defer":
                self.deferred = ctx.defer()
                return None
            if message.content == "slow":
                self.slow_started.set()
                try:
                    await asyncio.sleep(30)
                except asyncio.CancelledError:
                    self.in_cleanup.set()
                    await self.cleanup_gate.wait()
                    raise
            if message.content == "third":
                self.third_started.set()
                return {"echo": "third"}
            return {"echo": message.content}

    writer = Mixed(name="writer", max_in_flight=2)
    researcher = EchoAgent(name="researcher")
    await writer.join(runtime)
    await researcher.join(runtime)
    try:
        await researcher.ask("writer", "defer", deadline_seconds=8, collect="ticket")
        for _ in range(40):
            if writer.deferred is not None:
                break
            await asyncio.sleep(0.05)
        assert writer.deferred is not None
        await researcher.ask("writer", "slow", deadline_seconds=0.4, collect="ticket")
        await asyncio.wait_for(writer.slow_started.wait(), timeout=5)
        session = writer._session
        assert session is not None
        assert session._occupied() == 2
        await researcher.ask("writer", "third", deadline_seconds=8, collect="ticket")
        await asyncio.wait_for(writer.in_cleanup.wait(), timeout=5)
        assert session._occupied() == 2
        await asyncio.sleep(0.3)
        assert not writer.third_started.is_set()
        assert "third" not in writer.seen
        writer.cleanup_gate.set()
        await asyncio.wait_for(writer.third_started.wait(), timeout=5)
        assert "third" in writer.seen
    finally:
        writer.cleanup_gate.set()
        await writer.leave()
        await researcher.leave()
        await runtime.stop()


class _RecoveringTransport:
    """Fail send/heartbeat until join succeeds, or hang join."""

    def __init__(self, inner, *, hang_join: bool = False, timeout: float = 5.0):
        self._inner = inner
        self.fail = False
        self.hang_join = hang_join
        self.join_calls = 0
        self.join_started = asyncio.Event()
        self._timeout = timeout

    def __getattr__(self, name):
        return getattr(self._inner, name)

    async def send(self, *args, **kwargs):
        if self.fail:
            raise TransportError("unavailable", "down", retryable=True)
        return await self._inner.send(*args, **kwargs)

    async def heartbeat(self, *args, **kwargs):
        if self.fail:
            raise TransportError("unavailable", "down", retryable=True)
        return await self._inner.heartbeat(*args, **kwargs)

    async def join(self, request):
        self.join_calls += 1
        self.join_started.set()
        if self.hang_join:
            await asyncio.Event().wait()
        result = await self._inner.join(request)
        self.fail = False
        return result


@pytest.mark.asyncio
async def test_handler_reconnect_does_not_await_itself():
    runtime = await Team("content-squad", session_ttl_seconds=30).start()

    class Writer(BaseAgent):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.recovered = asyncio.Event()
            self.asked = False

        async def handle(self, message, ctx):
            if message.content != "go":
                return {"echo": message.content}
            if self.asked:
                ctx.defer()
                return None
            self.asked = True
            inner = await ctx.ask("echo", "ping", collect="wait")
            self.recovered.set()
            if inner.state == "completed":
                return inner.content
            return {"state": inner.state}

    writer = Writer(name="writer")
    echo = EchoAgent(name="echo")
    researcher = EchoAgent(name="researcher")
    await writer.join(runtime)
    await echo.join(runtime)
    await researcher.join(runtime)
    session = writer._session
    assert session is not None
    wrapper = _RecoveringTransport(session._transport)
    session._transport = wrapper
    wrapper.fail = True
    try:
        await researcher.ask("writer", "go", deadline_seconds=8, collect="ticket")
        await asyncio.wait_for(writer.recovered.wait(), timeout=5)
        assert wrapper.join_calls >= 1
    finally:
        await writer.leave()
        await echo.leave()
        await researcher.leave()
        await runtime.stop()


@pytest.mark.asyncio
async def test_handler_reconnect_foreground_timeout_is_bounded():
    runtime = await Team("content-squad", session_ttl_seconds=30).start()

    class Writer(BaseAgent):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.error: SessionError | None = None

        async def handle(self, message, ctx):
            try:
                await ctx.ask("echo", "ping", collect="ticket")
            except SessionError as exc:
                self.error = exc
                return {"code": exc.code}
            return {"ok": True}

    writer = Writer(name="writer")
    echo = EchoAgent(name="echo")
    researcher = EchoAgent(name="researcher")
    await writer.join(runtime)
    await echo.join(runtime)
    await researcher.join(runtime)
    session = writer._session
    assert session is not None
    wrapper = _RecoveringTransport(session._transport, hang_join=True, timeout=0.05)
    session._transport = wrapper
    wrapper.fail = True
    try:
        ticket = await researcher.ask(
            "writer", "go", deadline_seconds=8, collect="wait"
        )
        assert writer.error is not None
        assert writer.error.code == "unavailable"
        assert writer.error.retryable is True
        assert ticket.state == "completed"
        assert ticket.content == {"code": "unavailable"}
    finally:
        await writer.leave()
        await echo.leave()
        await researcher.leave()
        await runtime.stop()


@pytest.mark.asyncio
async def test_shutdown_during_handler_reconnect_does_not_stick():
    runtime = await Team("content-squad", session_ttl_seconds=30).start()

    class Writer(BaseAgent):
        async def handle(self, message, ctx):
            await ctx.ask("echo", "ping", collect="ticket")
            return {"ok": True}

    writer = Writer(name="writer")
    echo = EchoAgent(name="echo")
    researcher = EchoAgent(name="researcher")
    await writer.join(runtime)
    await echo.join(runtime)
    await researcher.join(runtime)
    session = writer._session
    assert session is not None
    wrapper = _RecoveringTransport(session._transport, hang_join=True, timeout=30.0)
    session._transport = wrapper
    wrapper.fail = True
    try:
        await researcher.ask("writer", "go", deadline_seconds=8, collect="ticket")
        await asyncio.wait_for(wrapper.join_started.wait(), timeout=5)
        await asyncio.wait_for(writer.leave(), timeout=2)
        writer._session = None
        await echo.leave()
        await researcher.leave()
    finally:
        await runtime.stop()
