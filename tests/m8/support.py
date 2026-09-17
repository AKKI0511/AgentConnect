"""Shared helpers for M8 gate tests."""

from __future__ import annotations

import asyncio
import platform
import sys
import time
import uuid
from typing import Any, Awaitable, Sequence

from tests.m8.budgets import LOOP_PROBE_SLEEP_S, extra_lag, loop_lag_budget_s
from tests.team.conftest import join_member, make_did, profile

from agentconnect.core.base import dump_public
from agentconnect.core.profile import AgentProfile
from agentconnect.team import Team
from agentconnect.team.store.base import Store

STORE_KINDS = ("yielding-memory", "redis")
LONG_PROFILE_MEMBERS = 20


class FailingEmbedder:
    """Test backend that succeeds ``succeed_calls`` times, then raises."""

    name = "openai:fake"
    input_char_limit = None
    max_batch = 8

    def __init__(self, succeed_calls: int) -> None:
        self.succeed_calls = succeed_calls
        self.calls = 0

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        if self.calls > self.succeed_calls:
            raise RuntimeError("api down")
        return [[1.0, 0.0] for _ in texts]


def message_id() -> str:
    return str(uuid.uuid4())


async def start_team(store: Store, **kwargs: Any) -> Team:
    """Start a Team on ``store`` with test-friendly lifetimes."""
    settings: dict[str, Any] = {
        "store": store,
        "embeddings": "none",
        "session_ttl_seconds": 30,
        "lease_ttl_seconds": kwargs.pop("lease_ttl_seconds", 2.0),
        "sweep_interval_seconds": kwargs.pop("sweep_interval_seconds", 0.05),
        "replay_horizon_seconds": kwargs.pop("replay_horizon_seconds", 2.0),
        "wait_hold_seconds": kwargs.pop("wait_hold_seconds", 0.4),
    }
    settings.update(kwargs)
    team = Team("content-squad", **settings)
    await team.start()
    return team


class LoopProbe:
    """10ms event-loop observer armed before work and sampled through the end.

    ``intervals`` are total ``asyncio.sleep`` durations. Extra lag is
    ``interval - sleep_for``. The observer starts before the workload and
    records one tick after it finishes so a stall at startup or shutdown
    is visible.
    """

    def __init__(self, sleep_for: float = LOOP_PROBE_SLEEP_S) -> None:
        self.sleep_for = sleep_for
        self.intervals: list[float] = []
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self.intervals.clear()
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="m8-loop-probe")
        await asyncio.sleep(0)

    async def _run(self) -> None:
        while not self._stop.is_set():
            started = time.perf_counter()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.sleep_for)
            except asyncio.TimeoutError:
                pass
            self.intervals.append(time.perf_counter() - started)

    async def stop(self) -> list[float]:
        await asyncio.sleep(self.sleep_for)
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None
        return list(self.intervals)


async def timer_delays(
    samples: int = 8, sleep_for: float = LOOP_PROBE_SLEEP_S
) -> list[float]:
    """Measure idle event-loop intervals. Prefer :func:`probe_during` under load."""
    delays: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        await asyncio.sleep(sleep_for)
        delays.append(time.perf_counter() - started)
    return delays


def assert_loop_responsive(
    intervals: list[float], *, members: int, rebuild: bool = False
) -> None:
    """Fail when extra lag on the 10ms probe exceeds the predetermined budget."""
    budget = loop_lag_budget_s(members, rebuild=rebuild)
    assert intervals, "loop probe produced no samples"
    extras = extra_lag(intervals)
    assert min(intervals) < 0.04
    worst = max(extras)
    assert worst < budget, (
        f"event-loop extra lag {worst * 1000:.1f}ms "
        f"(interval {max(intervals) * 1000:.1f}ms) exceeds "
        f"{budget * 1000:.0f}ms extra-lag budget at {members} members"
    )


async def probe_during(
    awaitable: Awaitable[Any],
    *,
    members: int,
    rebuild: bool = False,
    enforce: bool = True,
) -> tuple[Any, list[float]]:
    """Arm the lag observer, then run ``awaitable`` through completion."""
    probe = LoopProbe()
    await probe.start()
    try:
        result = await awaitable
    finally:
        intervals = await probe.stop()
    if enforce:
        assert_loop_responsive(intervals, members=members, rebuild=rebuild)
    return result, intervals


def platform_report() -> dict[str, str]:
    """Interpreter and host fields for the M8 performance report."""
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }


def short_profile(index: int) -> dict[str, Any]:
    return dump_public(
        AgentProfile.model_validate(
            profile(summary=f"Handles similar paperwork {index}.")
        )
    )


def specialist_profile() -> dict[str, Any]:
    return dump_public(
        AgentProfile.model_validate(
            profile(
                summary="Reviews contracts for risk and missing terms.",
                skill="contract_review",
                description="Read a contract and list risks and missing clauses.",
                tags=["legal", "contracts"],
            )
        )
    )


def heavy_profile(label: str) -> dict[str, Any]:
    """Long multi-Skill Profile that stays inside public field limits."""
    slug = "".join(ch if ch.isalnum() else "-" for ch in label.lower()).strip("-")
    slug = (slug or "item")[:24]
    skill_desc = (
        f"Long-form administration for {label}: read incoming packets, "
        f"extract clause families, and file the distinguishing notes. "
    ) * 6
    skill_desc = skill_desc[:1000].rstrip()
    description = (
        f"Handles {label} across multi-skill office workflows. "
        f"Includes a late-binding specialty named {label}. "
    ) * 12
    description = description[:2000].rstrip()
    summary = f"Long-form administrator for {label}."[:200]
    return dump_public(
        AgentProfile.model_validate(
            {
                "summary": summary,
                "description": description,
                "skills": [
                    {"name": f"{slug}-one", "description": skill_desc},
                    {"name": f"{slug}-two", "description": skill_desc},
                    {
                        "name": f"late-{slug}"[:63].rstrip("-"),
                        "description": f"Distinguishing skill for {label}.",
                    },
                ],
            }
        )
    )


async def join_roster(team: Team, count: int, *, specialist: bool = False) -> None:
    """Join ``count`` near-duplicate members, optionally one legal specialist."""
    if specialist:
        await join_member(
            team,
            "reviewer",
            agent_did=make_did("reviewer"),
            profile=specialist_profile(),
        )
        count -= 1
    for index in range(max(0, count)):
        name = f"agent{index:04d}"
        await join_member(
            team, name, agent_did=make_did(name), profile=short_profile(index)
        )
