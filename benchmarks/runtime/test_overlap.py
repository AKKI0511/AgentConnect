"""Send, renew, and expiry overlapping a hashed Team.find."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from tests.support.budgets import (
    SEND_DURING_FIND_MEMBERS,
    SEND_DURING_FIND_P95_S,
    SEND_DURING_FIND_SAMPLES,
    extra_lag,
    loop_lag_budget_s,
    percentile,
)
from tests.support.runtime import join_roster, probe_during, start_team
from tests.support.stores import open_store
from tests.team.conftest import deadline, join_member, make_did

from agentconnect.team.directory.embedder import HashedEmbedder
from benchmarks.runtime.helpers import sample_seconds

QUERY = "similar paperwork"
MEMBERS = SEND_DURING_FIND_MEMBERS


def _start(async_bridge, store_kind: str):
    store = async_bridge.run(open_store(store_kind))
    team = async_bridge.run(
        start_team(store, embeddings=HashedEmbedder(), lease_ttl_seconds=8)
    )
    writer = async_bridge.run(join_member(team, "writer", max_in_flight=8))
    async_bridge.run(join_roster(team, MEMBERS))
    caller = async_bridge.run(
        join_member(team, "researcher", agent_did=make_did("researcher"))
    )
    token = caller["session_token"]
    async_bridge.run(team.find(token, QUERY))
    return store, team, writer, token


def _stop(async_bridge, team, store) -> None:
    async_bridge.run(team.stop())
    async_bridge.run(store.clear())
    async_bridge.run(store.close())


@pytest.mark.perf
@pytest.mark.parametrize("store_kind", ["memory", "redis"])
def test_send_during_hashed_find(benchmark, async_bridge, store_kind: str) -> None:
    store, team, writer, token = _start(async_bridge, store_kind)
    held: dict[str, asyncio.Task] = {}
    try:

        def setup():
            async def body():
                held["search"] = asyncio.create_task(team.find(token, QUERY))
                await asyncio.sleep(0)

            async_bridge.run(body())
            return (), {}

        def send_once():
            return async_bridge.run(
                team.send(
                    token,
                    {
                        "id": str(uuid.uuid4()),
                        "recipient": "writer",
                        "kind": "event",
                        "content": "notes",
                    },
                )
            )

        def teardown():
            found = async_bridge.run(held["search"])
            assert found["matches"]

        result = benchmark.pedantic(
            send_once,
            setup=setup,
            teardown=teardown,
            rounds=SEND_DURING_FIND_SAMPLES,
            warmup_rounds=1,
            iterations=1,
        )
        assert result["message"]["recipient"] == "writer@content-squad"
        p95 = percentile(sample_seconds(benchmark), 95)
        assert p95 < SEND_DURING_FIND_P95_S, (
            f"send during find p95 {p95 * 1000:.1f}ms exceeds "
            f"{SEND_DURING_FIND_P95_S * 1000:.0f}ms"
        )
        benchmark.extra_info.update(
            {
                "store": store_kind,
                "members": MEMBERS,
                "send_p95_s": p95,
                "budget_send_p95_s": SEND_DURING_FIND_P95_S,
            }
        )
    finally:
        _stop(async_bridge, team, store)


@pytest.mark.perf
@pytest.mark.parametrize("store_kind", ["memory", "redis"])
def test_renew_during_hashed_find(benchmark, async_bridge, store_kind: str) -> None:
    store, team, writer, token = _start(async_bridge, store_kind)
    held: dict[str, asyncio.Task] = {}
    try:
        async_bridge.run(
            team.send(
                token,
                {
                    "id": str(uuid.uuid4()),
                    "recipient": "writer",
                    "kind": "request",
                    "content": "hold",
                    "collect": "ticket",
                    "deadline": deadline(60),
                },
            )
        )
        delivery = async_bridge.run(team.lease(writer["session_token"]))["deliveries"][
            0
        ]

        def setup():
            async def body():
                held["search"] = asyncio.create_task(team.find(token, QUERY))
                await asyncio.sleep(0)

            async_bridge.run(body())
            return (), {}

        def renew_once():
            return async_bridge.run(
                team.renew(writer["session_token"], delivery["lease_id"])
            )

        def teardown():
            found = async_bridge.run(held["search"])
            assert found["matches"]

        renewed = benchmark.pedantic(
            renew_once,
            setup=setup,
            teardown=teardown,
            rounds=SEND_DURING_FIND_SAMPLES,
            warmup_rounds=1,
            iterations=1,
        )
        assert renewed["lease_expires_at"]
        p95 = percentile(sample_seconds(benchmark), 95)
        assert p95 < SEND_DURING_FIND_P95_S, (
            f"renew during find p95 {p95 * 1000:.1f}ms exceeds "
            f"{SEND_DURING_FIND_P95_S * 1000:.0f}ms"
        )
        async_bridge.run(
            team.reply(
                writer["session_token"],
                {
                    "id": str(uuid.uuid4()),
                    "lease_id": delivery["lease_id"],
                    "outcome": "completed",
                    "content": "done",
                },
            )
        )
        benchmark.extra_info.update(
            {
                "store": store_kind,
                "members": MEMBERS,
                "renew_p95_s": p95,
                "budget_renew_p95_s": SEND_DURING_FIND_P95_S,
            }
        )
    finally:
        _stop(async_bridge, team, store)


@pytest.mark.perf
@pytest.mark.parametrize("store_kind", ["memory", "redis"])
def test_expiry_during_hashed_find(benchmark, async_bridge, store_kind: str) -> None:
    store, team, writer, token = _start(async_bridge, store_kind)
    try:
        expiring = async_bridge.run(
            team.send(
                token,
                {
                    "id": str(uuid.uuid4()),
                    "recipient": "writer",
                    "kind": "request",
                    "content": "expire",
                    "collect": "ticket",
                    "deadline": deadline(0.2),
                },
            )
        )

        async def find_until_expired():
            async with asyncio.timeout(5):
                while True:
                    found = await team.find(token, QUERY)
                    assert found["matches"]
                    ticket = await team.get_result(token, expiring["message"]["id"])
                    if ticket["state"] == "expired":
                        return found
                    await asyncio.sleep(0.01)

        captured: dict[str, list[float]] = {}

        def timed():
            async def wrapped():
                result, intervals = await probe_during(
                    find_until_expired(), members=MEMBERS, enforce=False
                )
                captured["intervals"] = intervals
                return result

            return async_bridge.run(wrapped())

        found = benchmark.pedantic(timed, rounds=1, warmup_rounds=0, iterations=1)
        assert found["matches"]
        extras = extra_lag(captured["intervals"])
        lag = max(extras)
        budget = loop_lag_budget_s(MEMBERS)
        assert lag < budget, (
            f"expiry-during-find extra lag {lag * 1000:.1f}ms exceeds "
            f"{budget * 1000:.0f}ms"
        )
        benchmark.extra_info.update(
            {
                "store": store_kind,
                "members": MEMBERS,
                "extra_lag_max_s": lag,
                "lag_budget_s": budget,
                "expiry_state": "expired",
            }
        )
    finally:
        _stop(async_bridge, team, store)
