"""Public SDK collaboration: find, fanout, thread history, and reconnect.

Handlers return fixed JSON. There is no model, keyword parser, or agent
framework. Timings include joins, work, history/collection, and leaves. The
adjusted journey mean subtracts configured critical-path handler sleeps;
it is not an isolated Runtime overhead measurement.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from tests.support.budgets import (
    COLLAB_HANDLER_DELAY_S,
    COLLAB_P99_MIN_SAMPLES,
    COLLAB_PAYLOAD_BYTES,
    COLLAB_SPECIALISTS,
    COLLAB_TIMEOUT_S,
    percentile,
)
from tests.support.runtime import platform_report, start_team
from tests.support.stores import open_store

from agentconnect import AgentProfile, BaseAgent, Skill
from agentconnect.core.identity import AgentIdentity
from agentconnect.team import Team
from agentconnect.team.store.base import Store

PAYLOAD = {"task": "draft", "notes": "n" * COLLAB_PAYLOAD_BYTES}
QUERY = "someone who can verify a contract"
CAPACITY_OBSERVATION_S = 0.05
HANDLER_SLEEP_COUNTS = {
    "discover_profile_ask": 1,
    "specialist_fanout": 1,  # Three handler sleeps overlap.
    "thread_follow_up": 2,
    "reconnect_open_ticket": 0,  # SlowWorker uses a barrier, no sleep.
}


class Reviewer(BaseAgent):
    profile = AgentProfile(
        summary="Reviews contracts for risk and missing terms.",
        skills=[
            Skill(
                name="contract_review",
                description="Read a contract and list risks and missing clauses.",
            )
        ],
    )

    async def handle(self, message, ctx):
        if message.kind != "request":
            return None
        if COLLAB_HANDLER_DELAY_S:
            await asyncio.sleep(COLLAB_HANDLER_DELAY_S)
        return {"agent": self.name, "echo": message.content}


class Writer(BaseAgent):
    profile = AgentProfile(
        summary="Turns notes into a short draft.",
        skills=[Skill(name="drafting", description="Draft from notes.")],
    )

    async def handle(self, message, ctx):
        if message.kind != "request":
            return None
        if COLLAB_HANDLER_DELAY_S:
            await asyncio.sleep(COLLAB_HANDLER_DELAY_S)
        return {"agent": self.name, "echo": message.content}


class Metrics(BaseAgent):
    profile = AgentProfile(
        summary="Reports fixed SLO numbers for a named service.",
        skills=[Skill(name="slo", description="Return p99 and error rate.")],
    )

    async def handle(self, message, ctx):
        if message.kind != "request":
            return None
        if COLLAB_HANDLER_DELAY_S:
            await asyncio.sleep(COLLAB_HANDLER_DELAY_S)
        return {"agent": self.name, "echo": message.content}


class SlowWorker(BaseAgent):
    """One in-flight Delivery. Tests wait on ``release`` after they reconnect."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("max_in_flight", 1)
        super().__init__(*args, **kwargs)
        self.release = asyncio.Event()
        self.started = asyncio.Event()
        self.another_started = asyncio.Event()
        self.seen: list[str] = []
        self.active = 0
        self.max_active = 0

    async def handle(self, message, ctx):
        if message.kind != "request":
            return None
        self.seen.append(message.id)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        if len(self.seen) > 1:
            self.another_started.set()
        self.started.set()
        try:
            await self.release.wait()
            return {"agent": self.name, "echo": message.content}
        finally:
            self.active -= 1


@dataclass
class CollabBench:
    store: Store
    team: Team
    origin: str | None
    store_kind: str
    transport: str
    identities: dict[str, AgentIdentity] = field(default_factory=dict)


def _identity(bench: CollabBench, name: str) -> AgentIdentity:
    existing = bench.identities.get(name)
    if existing is None:
        existing = AgentIdentity.create_key_based()
        bench.identities[name] = existing
    return existing


def _target(bench: CollabBench) -> Team | str:
    if bench.transport == "http":
        assert bench.origin is not None
        return bench.origin
    return bench.team


def summarize(
    outcomes: list[tuple[str, float, str]],
    *,
    wall_s: float,
    store_kind: str,
    transport: str,
    workload: str,
    repetitions: int,
    warmup: int,
) -> dict[str, Any]:
    completed = [latency for status, latency, _detail in outcomes if status == "ok"]
    errors = sum(1 for status, _latency, _detail in outcomes if status == "error")
    timeouts = sum(1 for status, _latency, _detail in outcomes if status == "timeout")
    attempted = len(outcomes)
    ok = len(completed)
    mean_s = (sum(completed) / ok) if ok else None
    handler_sleep_s = HANDLER_SLEEP_COUNTS[workload] * COLLAB_HANDLER_DELAY_S
    adjusted_journey_s = (
        max(0.0, mean_s - handler_sleep_s) if mean_s is not None else None
    )
    samples: list[str] = []
    for status, _latency, detail in outcomes:
        if status == "ok" or not detail or detail in samples:
            continue
        samples.append(detail)
        if len(samples) >= 8:
            break
    return {
        "store": store_kind,
        "transport": transport,
        "workload": workload,
        "repetitions": repetitions,
        "warmup": warmup,
        "timing_boundary": "joins_journey_leaves_excluding_warmup",
        "payload_notes_bytes": COLLAB_PAYLOAD_BYTES,
        "handler_delay_s": COLLAB_HANDLER_DELAY_S,
        "attempted": attempted,
        "completed": ok,
        "errors": errors,
        "timeouts": timeouts,
        "error_rate": (errors / attempted) if attempted else 1.0,
        "timeout_rate": (timeouts / attempted) if attempted else 1.0,
        "error_samples": samples,
        "percentiles_on": "completed_only",
        "offered_denominator": "attempted",
        "p99_supported": ok >= COLLAB_P99_MIN_SAMPLES,
        "wall_s": wall_s,
        "rps": (ok / wall_s) if wall_s > 0 else 0.0,
        "p50_s": percentile(completed, 50) if completed else None,
        "p95_s": percentile(completed, 95) if completed else None,
        "p99_s": percentile(completed, 99) if ok >= COLLAB_P99_MIN_SAMPLES else None,
        "mean_s": mean_s,
        "configured_critical_path_handler_sleep_s": handler_sleep_s,
        "journey_mean_minus_configured_handler_sleep_s": adjusted_journey_s,
        "capacity_observation_s": (
            CAPACITY_OBSERVATION_S if workload == "reconnect_open_ticket" else 0.0
        ),
        **platform_report(),
    }


async def _timed(
    awaitable, timeout: float = COLLAB_TIMEOUT_S
) -> tuple[str, float, str]:
    started = time.perf_counter()
    try:
        async with asyncio.timeout(timeout):
            await awaitable
    except TimeoutError as exc:
        return "timeout", time.perf_counter() - started, str(exc) or "timeout"
    except Exception as exc:
        return "error", time.perf_counter() - started, f"{type(exc).__name__}: {exc}"
    return "ok", time.perf_counter() - started, ""


async def open_collab(store_kind: str, transport: str) -> CollabBench:
    store = await open_store(store_kind)
    team = await start_team(
        store,
        embeddings="hashed",
        lease_ttl_seconds=30,
        session_ttl_seconds=300,
        wait_hold_seconds=8.0,
        work_lifetime_seconds=120,
    )
    origin = None
    try:
        if transport == "http":
            origin = await team.serve()
        return CollabBench(
            store=store,
            team=team,
            origin=origin,
            store_kind=store_kind,
            transport=transport,
        )
    except Exception:
        await team.stop()
        await store.close()
        raise


async def close_collab(bench: CollabBench) -> None:
    try:
        await bench.store.clear()
    except Exception:
        pass
    await bench.team.stop()
    try:
        await bench.store.close()
    except Exception:
        pass


async def discover_and_ask(bench: CollabBench) -> None:
    target = _target(bench)
    reviewer = Reviewer(name="reviewer", identity=_identity(bench, "reviewer"))
    writer = Writer(name="writer", identity=_identity(bench, "writer"))
    caller = BaseAgent(name="caller", identity=_identity(bench, "caller"))
    await reviewer.join(target)
    await writer.join(target)
    await caller.join(target)
    try:
        found = await caller.find(QUERY)
        assert found.matches
        assert found.matches[0].address.startswith("reviewer@")
        entry = await caller.get_entry(found.matches[0].address)
        assert entry.address.startswith("reviewer@")
        ticket = await caller.ask(
            found.matches[0].address, PAYLOAD, collect="wait", deadline_seconds=20
        )
        if ticket.state == "open":
            ticket = await caller.get_result(ticket.id)
        assert ticket.state == "completed"
        assert ticket.content["agent"] == "reviewer"
    finally:
        await caller.leave()
        await writer.leave()
        await reviewer.leave()


async def fanout_and_aggregate(bench: CollabBench) -> None:
    target = _target(bench)
    specialists = [
        Reviewer(name="reviewer", identity=_identity(bench, "reviewer")),
        Writer(name="writer", identity=_identity(bench, "writer")),
        Metrics(name="metrics", identity=_identity(bench, "metrics")),
    ]
    caller = BaseAgent(name="caller", identity=_identity(bench, "caller"))
    assert len(specialists) == COLLAB_SPECIALISTS
    for agent in specialists:
        await agent.join(target)
    await caller.join(target)
    try:

        async def ask_one(name: str):
            ticket = await caller.ask(
                name, PAYLOAD, collect="wait", deadline_seconds=20
            )
            if ticket.state == "open":
                ticket = await caller.get_result(ticket.id)
            return ticket

        tickets = await asyncio.gather(
            ask_one("reviewer"), ask_one("writer"), ask_one("metrics")
        )
        assert [item.state for item in tickets] == ["completed"] * COLLAB_SPECIALISTS
        agents = {item.content["agent"] for item in tickets}
        assert agents == {"reviewer", "writer", "metrics"}
    finally:
        await caller.leave()
        for agent in specialists:
            await agent.leave()


async def thread_follow_up(bench: CollabBench) -> None:
    target = _target(bench)
    writer = Writer(name="writer", identity=_identity(bench, "writer"))
    caller = BaseAgent(name="caller", identity=_identity(bench, "caller"))
    await writer.join(target)
    await caller.join(target)
    try:
        thread_id = str(uuid.uuid4())
        first = await caller.ask(
            "writer",
            PAYLOAD,
            collect="wait",
            deadline_seconds=20,
            thread_id=thread_id,
        )
        if first.state == "open":
            first = await caller.get_result(first.id)
        assert first.state == "completed"
        assert first.thread_id == thread_id
        assert first.response is not None
        second = await caller.ask(
            "writer",
            {"task": "revise", "notes": "n" * COLLAB_PAYLOAD_BYTES},
            collect="wait",
            deadline_seconds=20,
            thread_id=thread_id,
            parent_id=first.response.id,
        )
        if second.state == "open":
            second = await caller.get_result(second.id)
        assert second.state == "completed"
        history = await caller.get_history(thread_id, limit=10)
        ids = {item.id for item in history.messages}
        assert first.id in ids
        assert second.id in ids
        replies = [item for item in history.messages if item.kind == "response"]
        assert second.response is not None
        assert ids == {first.id, first.response.id, second.id, second.response.id}
        assert len(history.messages) == 4
        assert all(item.thread_id == thread_id for item in history.messages)
        assert [item.seq for item in history.messages] == [1, 2, 3, 4]
        requests = {
            item.id: item for item in history.messages if item.kind == "request"
        }
        assert requests[first.id].parent_id is None
        assert requests[second.id].parent_id == first.response.id
        assert len(replies) == 2
        assert {item.parent_id for item in replies} == {first.id, second.id}
        assert {item.id for item in replies} == {first.response.id, second.response.id}
    finally:
        await caller.leave()
        await writer.leave()


async def reconnect_collects_open_work(bench: CollabBench) -> None:
    target = _target(bench)
    identity = _identity(bench, "caller")
    worker = SlowWorker(name="writer", identity=_identity(bench, "writer"))
    caller = BaseAgent(name="caller", identity=identity)
    await worker.join(target)
    await caller.join(target)
    try:
        pending = await caller.ask(
            "writer", PAYLOAD, collect="ticket", deadline_seconds=30
        )
        assert pending.state == "open"
        await asyncio.wait_for(worker.started.wait(), timeout=COLLAB_TIMEOUT_S)
        extra = await caller.ask(
            "writer",
            {"task": "queued", "notes": "n" * COLLAB_PAYLOAD_BYTES},
            collect="ticket",
            deadline_seconds=30,
        )
        assert extra.state == "open"
        await caller.leave()
        caller = BaseAgent(name="caller", identity=identity)
        await caller.join(target)
        still_open = await caller.get_result(pending.id)
        assert still_open.state == "open"
        assert (await caller.get_result(extra.id)).state == "open"
        # This bounded observation window is part of the measured journey.
        try:
            await asyncio.wait_for(
                worker.another_started.wait(), timeout=CAPACITY_OBSERVATION_S
            )
        except TimeoutError:
            pass
        else:
            raise AssertionError("queued work started while the only slot was occupied")
        assert worker.seen == [pending.id]
        assert worker.active == worker.max_active == 1
        worker.release.set()
        first = await _wait_ticket(caller, pending.id)
        second = await _wait_ticket(caller, extra.id)
        assert first.state == "completed"
        assert second.state == "completed"
        assert first.content == {"agent": "writer", "echo": PAYLOAD}
        assert second.content["echo"]["task"] == "queued"
        assert worker.seen == [pending.id, extra.id]
        # Fresh work proves capacity remains usable after retained work drains.
        recovered = await caller.ask("writer", {"task": "after-reconnect"})
        if recovered.state == "open":
            recovered = await _wait_ticket(caller, recovered.id)
        assert recovered.state == "completed"
        assert recovered.content["echo"] == {"task": "after-reconnect"}
        assert worker.seen == [pending.id, extra.id, recovered.id]
        assert worker.max_active == 1
        assert worker.active == 0
    finally:
        worker.release.set()
        try:
            await caller.leave()
        except Exception:
            pass
        await worker.leave()


async def _wait_ticket(agent: BaseAgent, ticket_id: str):
    async def wait():
        while True:
            ticket = await agent.get_result(ticket_id)
            if ticket.state != "open":
                return ticket
            await asyncio.sleep(0.05)

    return await asyncio.wait_for(wait(), timeout=COLLAB_TIMEOUT_S)


async def measure(
    bench: CollabBench,
    work,
    *,
    repetitions: int,
) -> tuple[list[tuple[str, float, str]], float]:
    # Warmup is executed by the caller before pytest-benchmark starts timing.
    outcomes: list[tuple[str, float, str]] = []
    started = time.perf_counter()
    for _ in range(repetitions):
        outcomes.append(await _timed(work(bench)))
    wall_s = time.perf_counter() - started
    return outcomes, wall_s
