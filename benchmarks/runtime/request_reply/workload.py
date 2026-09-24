"""N-pair send -> lease -> reply -> get_result with no model work.

Uses the shared Runtime test helpers and the public Session transports.
One pair is one caller Session and one worker Session. Pairs run at the
same time; each pair keeps one request in flight.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from tests.support.budgets import (
    EXCHANGE_LEASE_RETRIES,
    EXCHANGE_TRIP_TIMEOUT_S,
    EXCHANGE_WARMUP_TRIPS,
    percentile,
)
from tests.support.runtime import message_id, platform_report, start_team
from tests.support.stores import open_store
from tests.team.conftest import deadline, join_member

from agentconnect.team import Team
from agentconnect.team.store.base import Store
from agentconnect.team.store.redis import RedisStore
from agentconnect.transport.agent_http import HttpRuntimeTransport
from agentconnect.transport.inprocess import InProcessTransport
from agentconnect.transport.runtime import RuntimeTransport, TransportError

ROOT = Path(__file__).resolve().parents[3]
PAYLOAD = "ping"
REPLY = "pong"

_TEAM_KW: dict[str, Any] = {
    "embeddings": "none",
    "lease_ttl_seconds": 30,
    "session_ttl_seconds": 300,
    "sweep_interval_seconds": 1.0,
    "replay_horizon_seconds": 30,
    "wait_hold_seconds": 25.0,
    "work_lifetime_seconds": 120,
}


@dataclass
class ExchangeBench:
    """Started Team, transports, and N caller/worker pairs."""

    store: Store
    team: Team
    replica: subprocess.Popen[bytes] | None
    caller_ops: RuntimeTransport
    worker_ops: RuntimeTransport
    pairs: list[tuple[str, str, str]]
    store_kind: str
    transport: str
    replicas: int


def summarize(
    outcomes: list[tuple[str, float, str]],
    *,
    wall_s: float,
    store_kind: str,
    transport: str,
    concurrency: int,
    replicas: int,
    trips_per_pair: int,
) -> dict[str, Any]:
    """Percentiles on completed trips; rates over every attempted trip."""
    completed = [latency for status, latency, _detail in outcomes if status == "ok"]
    errors = sum(1 for status, _latency, _detail in outcomes if status == "error")
    timeouts = sum(1 for status, _latency, _detail in outcomes if status == "timeout")
    attempted = len(outcomes)
    ok = len(completed)
    samples: list[str] = []
    for status, _latency, detail in outcomes:
        if status == "ok" or not detail or detail in samples:
            continue
        samples.append(detail)
        if len(samples) >= 8:
            break
    row: dict[str, Any] = {
        "store": store_kind,
        "transport": transport,
        "concurrency": concurrency,
        "replicas": replicas,
        "trips_per_pair": trips_per_pair,
        "attempted": attempted,
        "completed": ok,
        "errors": errors,
        "timeouts": timeouts,
        "error_rate": (errors / attempted) if attempted else 1.0,
        "timeout_rate": (timeouts / attempted) if attempted else 1.0,
        "error_samples": samples,
        "wall_s": wall_s,
        "rps": (ok / wall_s) if wall_s > 0 else 0.0,
        "p50_s": percentile(completed, 50) if completed else None,
        "p95_s": percentile(completed, 95) if completed else None,
        "p99_s": percentile(completed, 99) if completed else None,
        "min_s": min(completed) if completed else None,
        "max_s": max(completed) if completed else None,
        "workload": (
            f"{concurrency} independent caller/worker pairs, "
            f"{trips_per_pair} serial collect=ticket round-trips per pair, "
            f"fixed JSON {PAYLOAD!r}/{REPLY!r}, no model, no Directory find"
        ),
        **platform_report(),
    }
    return row


async def _http_transport(origin: str) -> HttpRuntimeTransport:
    transport = HttpRuntimeTransport(origin, timeout=30.0)
    await transport._client.aclose()
    transport._client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=5.0),
        limits=httpx.Limits(max_connections=256, max_keepalive_connections=128),
        trust_env=False,
    )
    return transport


def _message_id_of(delivery: Any) -> str | None:
    message = delivery.get("message") if hasattr(delivery, "get") else None
    if message is None:
        return None
    if isinstance(message, dict):
        raw = message.get("id")
        return str(raw) if raw else None
    raw = getattr(message, "id", None)
    return str(raw) if raw else None


async def _reply_completed(
    worker_ops: RuntimeTransport, worker_token: str, lease_id: str
) -> None:
    await worker_ops.reply(
        worker_token,
        {
            "id": message_id(),
            "lease_id": lease_id,
            "outcome": "completed",
            "content": REPLY,
        },
    )


async def _drain(worker_ops: RuntimeTransport, worker_token: str) -> None:
    """Finish leftover leased work so the next send is not paired wrongly."""
    for _ in range(8):
        try:
            leased = await worker_ops.lease(worker_token, 1)
        except Exception:
            return
        items = leased.get("deliveries") or []
        if not items:
            return
        try:
            await _reply_completed(worker_ops, worker_token, items[0]["lease_id"])
        except Exception:
            return


async def _round_trip(
    caller_ops: RuntimeTransport,
    worker_ops: RuntimeTransport,
    caller_token: str,
    worker_token: str,
    worker_name: str,
) -> None:
    sent = await caller_ops.send(
        caller_token,
        {
            "id": message_id(),
            "recipient": worker_name,
            "kind": "request",
            "content": PAYLOAD,
            "collect": "ticket",
            "deadline": deadline(60),
        },
    )
    ticket_id = sent["message"]["id"]
    delivery = None
    for _ in range(EXCHANGE_LEASE_RETRIES):
        leased = await worker_ops.lease(worker_token, 1)
        items = leased.get("deliveries") or []
        if not items:
            await asyncio.sleep(0.002)
            continue
        item = items[0]
        if _message_id_of(item) not in {None, ticket_id}:
            await _reply_completed(worker_ops, worker_token, item["lease_id"])
            continue
        delivery = item
        break
    if delivery is None:
        raise TimeoutError("lease returned no work")
    await _reply_completed(worker_ops, worker_token, delivery["lease_id"])
    ticket = await caller_ops.get_result(caller_token, ticket_id)
    if ticket.get("state") != "completed":
        raise RuntimeError(f"ticket state {ticket.get('state')!r}")
    if ticket.get("response", {}).get("content") != REPLY:
        raise RuntimeError("reply content mismatch")


async def _timed_trip(
    caller_ops: RuntimeTransport,
    worker_ops: RuntimeTransport,
    caller_token: str,
    worker_token: str,
    worker_name: str,
) -> tuple[str, float, str]:
    started = time.perf_counter()
    try:
        async with asyncio.timeout(EXCHANGE_TRIP_TIMEOUT_S):
            await _round_trip(
                caller_ops, worker_ops, caller_token, worker_token, worker_name
            )
    except TimeoutError as exc:
        return "timeout", time.perf_counter() - started, str(exc) or "timeout"
    except TransportError as exc:
        return "error", time.perf_counter() - started, f"{exc.code}: {exc.message}"
    except Exception as exc:
        return "error", time.perf_counter() - started, f"{type(exc).__name__}: {exc}"
    return "ok", time.perf_counter() - started, ""


async def _pair_loop(
    bench: ExchangeBench,
    pair: tuple[str, str, str],
    trips: int,
) -> list[tuple[str, float, str]]:
    caller_token, worker_token, worker_name = pair
    out: list[tuple[str, float, str]] = []
    for _ in range(trips):
        out.append(
            await _timed_trip(
                bench.caller_ops,
                bench.worker_ops,
                caller_token,
                worker_token,
                worker_name,
            )
        )
        if out[-1][0] != "ok":
            await _drain(bench.worker_ops, worker_token)
    return out


async def run_trips(bench: ExchangeBench, trips: int) -> list[tuple[str, float, str]]:
    """Run ``trips`` round-trips on every pair concurrently."""
    groups = await asyncio.gather(
        *[_pair_loop(bench, pair, trips) for pair in bench.pairs]
    )
    outcomes: list[tuple[str, float, str]] = []
    for group in groups:
        outcomes.extend(group)
    return outcomes


async def measure(bench: ExchangeBench, trips_per_pair: int) -> dict[str, Any]:
    started = time.perf_counter()
    outcomes = await run_trips(bench, trips_per_pair)
    wall_s = time.perf_counter() - started
    return summarize(
        outcomes,
        wall_s=wall_s,
        store_kind=bench.store_kind,
        transport=bench.transport,
        concurrency=len(bench.pairs),
        replicas=bench.replicas,
        trips_per_pair=trips_per_pair,
    )


def spawn_replica(url: str, prefix: str) -> tuple[subprocess.Popen[bytes], str]:
    """Start a second Runtime process on the same Redis prefix."""
    ready = Path(tempfile.mkdtemp(prefix="ac-exchange-")) / "origin.txt"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "benchmarks.runtime.request_reply",
            "--redis-url",
            url,
            "--prefix",
            prefix,
            "--ready-file",
            str(ready),
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    deadline_at = time.time() + 20.0
    while time.time() < deadline_at:
        if proc.poll() is not None:
            err = (proc.stderr.read() if proc.stderr else b"").decode(
                "utf-8", errors="replace"
            )
            raise RuntimeError(f"replica process exited: {err.strip()}")
        if ready.exists():
            origin = ready.read_text(encoding="utf-8").strip()
            if origin.startswith("http://"):
                return proc, origin
        time.sleep(0.05)
    proc.terminate()
    raise RuntimeError("replica process did not become ready")


def stop_replica(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None:
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


async def open_exchange(
    store_kind: str,
    transport: str,
    concurrency: int,
    *,
    replicas: int = 1,
) -> ExchangeBench:
    """Start a Team, join N pairs, and optionally a second Redis HTTP replica."""
    if replicas not in (1, 2):
        raise ValueError("replicas must be 1 or 2")
    if replicas == 2 and (store_kind != "redis" or transport != "http"):
        raise ValueError("two replicas need Redis and HTTP")
    store = await open_store(store_kind)
    team = await start_team(store, **_TEAM_KW)
    replica: subprocess.Popen[bytes] | None = None
    caller_ops: RuntimeTransport
    worker_ops: RuntimeTransport
    try:
        origin_a: str | None = None
        if transport == "http":
            origin_a = await team.serve()
        if replicas == 2:
            if not isinstance(store, RedisStore):
                raise RuntimeError("two replicas require RedisStore")
            replica, origin_b = spawn_replica(store._url, store._prefix)
        else:
            origin_b = origin_a
        pairs: list[tuple[str, str, str]] = []
        for index in range(concurrency):
            caller_name = f"caller{index:04d}"
            worker_name = f"worker{index:04d}"
            caller = await join_member(team, caller_name)
            worker = await join_member(team, worker_name, max_in_flight=1)
            pairs.append(
                (caller["session_token"], worker["session_token"], worker_name)
            )
        if transport == "http":
            assert origin_a is not None and origin_b is not None
            caller_ops = await _http_transport(origin_a)
            worker_ops = (
                caller_ops if origin_b == origin_a else await _http_transport(origin_b)
            )
        else:
            caller_ops = InProcessTransport(team)
            worker_ops = caller_ops
        bench = ExchangeBench(
            store=store,
            team=team,
            replica=replica,
            caller_ops=caller_ops,
            worker_ops=worker_ops,
            pairs=pairs,
            store_kind=store_kind,
            transport=transport,
            replicas=replicas,
        )
        await run_trips(bench, EXCHANGE_WARMUP_TRIPS)
        return bench
    except Exception:
        stop_replica(replica)
        try:
            await store.clear()
        except Exception:
            pass
        await team.stop()
        try:
            await store.close()
        except Exception:
            pass
        raise


async def close_exchange(bench: ExchangeBench) -> None:
    stop_replica(bench.replica)
    if bench.worker_ops is not bench.caller_ops:
        await bench.worker_ops.close()
    await bench.caller_ops.close()
    try:
        await bench.store.clear()
    except Exception:
        pass
    await bench.team.stop()
    try:
        await bench.store.close()
    except Exception:
        pass


async def serve_replica(url: str, prefix: str, ready_file: str) -> None:
    """HTTP Runtime sharing ``url``/``prefix``. Writes the origin, then waits."""
    store = RedisStore(url, prefix=prefix)
    await store.open()
    team = await start_team(store, **_TEAM_KW)
    origin = await team.serve()
    Path(ready_file).write_text(origin, encoding="utf-8")
    try:
        await asyncio.Event().wait()
    finally:
        await team.stop_serving()
