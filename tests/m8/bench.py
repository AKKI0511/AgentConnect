"""Runtime discovery benchmark.

Measures public ``Team.find`` on memory and Redis, embedded and HTTP,
hashed and real FastEmbed. Isolated Directory searches are not the
release evidence.

    uv run --extra serve --extra embeddings --extra redis python tests/m8/bench.py
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import importlib.metadata
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from tests.m8.budgets import (
    CONCURRENT_FINDERS,
    HASHED_SUPPORTED_MEMBERS,
    LOOP_LAG_S_REBUILD,
    NEURAL_MEASURED_MEMBERS,
    NEURAL_SUPPORTED_MEMBERS,
    SEND_DURING_FIND_MEMBERS,
    SEND_DURING_FIND_P95_S,
    SEND_DURING_FIND_SAMPLES,
    STRESS_MEMBERS,
    WARM_SAMPLES,
    extra_lag,
    find_p95_budget_s,
    loop_lag_budget_s,
    percentile,
)
from tests.m8.stores import CountingStore, connect_redis
from tests.m8.support import (
    LONG_PROFILE_MEMBERS,
    FailingEmbedder,
    heavy_profile,
    join_roster,
    platform_report,
    probe_during,
    short_profile,
    specialist_profile,
    start_team,
)
from tests.team.conftest import deadline, join_member, make_did

from agentconnect.team.directory.embedder import (
    DEFAULT_FASTEMBED_MODEL,
    HASHED_DIM,
    FastEmbedEmbedder,
    HashedEmbedder,
)
from agentconnect.team.http import HTTP_PREFIX
from agentconnect.team.retention import RETAINED_BYTES_KEY
from agentconnect.team.store.memory import MemoryStore

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = Path(__file__).resolve().parent / "results" / "latest.json"
HTTP_WARMUPS = 3


def _quiet_http_logs() -> None:
    for name in ("httpx", "httpcore", "httpcore.http11", "uvicorn", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _git_revision() -> str:
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            text=True,
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=str(ROOT),
            text=True,
        ).strip()
        return f"{head}-dirty" if dirty else head
    except Exception:
        return "unknown"


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _provenance() -> dict[str, Any]:
    neural_packages = {
        "fastembed": _package_version("fastembed"),
        "onnxruntime": _package_version("onnxruntime"),
        "numpy": _package_version("numpy"),
    }
    return {
        "hashed": {"name": HashedEmbedder.name, "dim": HASHED_DIM},
        "neural": {
            "backend": f"fastembed:{DEFAULT_FASTEMBED_MODEL}",
            "model": DEFAULT_FASTEMBED_MODEL,
            "packages": neural_packages,
        },
        "runtime_packages": {
            "redis": _package_version("redis"),
            "httpx": _package_version("httpx"),
            "pydantic": _package_version("pydantic"),
        },
    }


def _rss_bytes() -> int | None:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class _Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = _Counters()
        counters.cb = ctypes.sizeof(_Counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_Counters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        ok = psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(),
            ctypes.byref(counters),
            counters.cb,
        )
        if ok:
            return int(counters.WorkingSetSize)
        return None
    import resource

    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(usage)
    return int(usage) * 1024


def _summarize(times: list[float]) -> dict[str, float]:
    if not times:
        return {}
    elapsed = sum(times)
    return {
        "samples": float(len(times)),
        "p50_s": percentile(times, 50),
        "p95_s": percentile(times, 95),
        "p99_s": percentile(times, 99),
        "max_s": max(times),
        "throughput_qps": (len(times) / elapsed) if elapsed else 0.0,
    }


async def _http_find(
    client: Any, origin: str, token: str, query: str
) -> dict[str, Any]:
    response = await client.post(
        f"{origin}{HTTP_PREFIX}/directory/find",
        json={"query": query},
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    return response.json()


def _queue_stats(team) -> dict[str, int]:
    directory = team._directory
    embedder = getattr(directory, "_active", None)
    cpu = getattr(directory, "_cpu", None)
    work = getattr(embedder, "_work", None)
    return {
        "search_in_flight_peak": int(getattr(directory, "search_in_flight_peak", 0)),
        "dir_cpu_peak_pending": int(getattr(cpu, "peak_pending", 0) or 0),
        "embed_peak_pending": int(getattr(work, "peak_pending", 0) or 0),
        "dir_worker_threads": 1,
        "embed_worker_threads": 1,
    }


async def _open_store(kind: str, counting: bool = True):
    if kind == "memory":
        inner = MemoryStore()
        await inner.open()
        store = CountingStore(inner) if counting else inner
        if counting:
            await store.open()
        return store
    store = await connect_redis()
    if counting:
        wrapped = CountingStore(store)
        wrapped.persistence = "durable"
        return wrapped
    return store


async def _measure_finds(team, token: str, query: str, samples: int) -> list[float]:
    times: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        found = await team.find(token, query)
        times.append(time.perf_counter() - started)
        assert found["matches"]
    return times


def _case_result(
    *,
    name: str,
    status: str,
    budget_p95: float | None,
    times: list[float],
    extras: list[float],
    members: int,
    rebuild: bool = False,
    **fields: Any,
) -> dict[str, Any]:
    summary = _summarize(times)
    lag_budget = loop_lag_budget_s(members, rebuild=rebuild)
    extra_max = max(extras) if extras else None
    p95 = summary.get("p95_s")
    gated = status == "ok" and budget_p95 is not None and p95 is not None
    passed = True
    if gated and p95 >= budget_p95:
        passed = False
        status = "failed"
    if extra_max is not None and extra_max >= lag_budget and status == "ok":
        passed = False
        status = "failed"
    return {
        "name": name,
        "status": status,
        "passed": passed and status == "ok",
        "members": members,
        "budget_p95_s": budget_p95,
        "lag_budget_s": lag_budget,
        "latency": summary,
        "latency_samples_s": times,
        "extra_lag_max_s": extra_max,
        **fields,
    }


async def _run_warm_case(
    *,
    store_kind: str,
    backend: str,
    members: int,
    transport: str,
    query: str = "similar paperwork",
) -> dict[str, Any]:
    embeddings = HashedEmbedder() if backend == "hashed" else FastEmbedEmbedder()
    store = await _open_store("memory" if store_kind == "memory" else "redis")
    team = await start_team(store, embeddings=embeddings, lease_ttl_seconds=8)
    name = f"{backend}-{store_kind}-{transport}-{members}"
    try:
        await join_roster(team, members, specialist=True)
        caller = await join_member(team, "researcher", agent_did=make_did("researcher"))
        token = caller["session_token"]
        await team.find(token, query)
        async with AsyncExitStack() as stack:
            if transport == "http":
                import httpx

                origin = await team.serve()
                client = await stack.enter_async_context(
                    httpx.AsyncClient(timeout=60.0, trust_env=False)
                )

                async def find():
                    return await _http_find(client, origin, token, query)

                for _ in range(HTTP_WARMUPS):
                    found = await find()
                    assert found["matches"]
            else:

                async def find():
                    return await team.find(token, query)

            times = []
            for _ in range(WARM_SAMPLES):
                started = time.perf_counter()
                found = await find()
                times.append(time.perf_counter() - started)
                assert found["matches"]
            found, intervals = await probe_during(
                find(), members=members, enforce=False
            )
            assert found["matches"]
            burst_started = time.perf_counter()
            burst = await asyncio.gather(*[find() for _ in range(CONCURRENT_FINDERS)])
            burst_s = time.perf_counter() - burst_started
            assert all(item["matches"] for item in burst)
        directory = team._directory
        if directory.using_fallback or directory.backend_name != embeddings.name:
            raise RuntimeError(
                f"requested {backend} backend {embeddings.name}, "
                f"but measured {directory.backend_name}"
            )
        retained = await store.get(RETAINED_BYTES_KEY)
        calls = getattr(store, "calls", {})
        write_bytes = getattr(store, "write_bytes", 0)
        budget = find_p95_budget_s(members) if backend == "hashed" else None
        status = "ok"
        if backend == "neural" and members not in NEURAL_SUPPORTED_MEMBERS:
            status = "measured"
        return _case_result(
            name=name,
            status=status,
            budget_p95=budget,
            times=times,
            extras=extra_lag(intervals),
            members=members,
            store=store_kind,
            backend=backend,
            transport=transport,
            corpus="short-near-duplicate",
            concurrent_burst_s=burst_s,
            concurrent_finders=CONCURRENT_FINDERS,
            queue=_queue_stats(team),
            store_calls=calls,
            write_bytes=write_bytes,
            retained_bytes=0 if retained is None else int(retained),
            rss_bytes=_rss_bytes(),
            cpu_process_s=time.process_time(),
            backend_name=team._directory.backend_name if team._directory else backend,
        )
    except Exception as exc:
        return {
            "name": name,
            "status": "failed",
            "passed": False,
            "members": members,
            "error": f"{type(exc).__name__}: {exc}",
            "store": store_kind,
            "backend": backend,
            "transport": transport,
        }
    finally:
        await team.stop()
        await store.clear()
        await store.close()


async def _run_overlap(store_kind: str) -> dict[str, Any]:
    store = await _open_store("memory" if store_kind == "memory" else "redis")
    team = await start_team(store, embeddings=HashedEmbedder(), lease_ttl_seconds=8)
    members = SEND_DURING_FIND_MEMBERS
    try:
        writer = await join_member(team, "writer", max_in_flight=8)
        await join_roster(team, members)
        caller = await join_member(team, "researcher", agent_did=make_did("researcher"))
        token = caller["session_token"]
        await team.find(token, "similar paperwork")
        held = await team.send(
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
        delivery = (await team.lease(writer["session_token"]))["deliveries"][0]
        send_times: list[float] = []
        renew_times: list[float] = []
        for _ in range(SEND_DURING_FIND_SAMPLES):
            search = asyncio.create_task(team.find(token, "similar paperwork"))
            await asyncio.sleep(0)
            started = time.perf_counter()
            await team.send(
                token,
                {
                    "id": str(uuid.uuid4()),
                    "recipient": "writer",
                    "kind": "event",
                    "content": "notes",
                },
            )
            send_times.append(time.perf_counter() - started)
            started = time.perf_counter()
            await team.renew(writer["session_token"], delivery["lease_id"])
            renew_times.append(time.perf_counter() - started)
            found = await search
            assert found["matches"]
        expiring = await team.send(
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

        async def find_until_expired():
            async with asyncio.timeout(5):
                while True:
                    found = await team.find(token, "similar paperwork")
                    assert found["matches"]
                    ticket = await team.get_result(token, expiring["message"]["id"])
                    if ticket["state"] == "expired":
                        return found
                    await asyncio.sleep(0.01)

        found, intervals = await probe_during(
            find_until_expired(),
            members=members,
            enforce=False,
        )
        await team.reply(
            writer["session_token"],
            {
                "id": str(uuid.uuid4()),
                "lease_id": delivery["lease_id"],
                "outcome": "completed",
                "content": "done",
            },
        )
        send_p95 = percentile(send_times, 95)
        renew_p95 = percentile(renew_times, 95)
        lag = max(extra_lag(intervals))
        passed = (
            send_p95 < SEND_DURING_FIND_P95_S
            and renew_p95 < SEND_DURING_FIND_P95_S
            and lag < loop_lag_budget_s(members)
        )
        status = "ok" if passed else "failed"
        return {
            "name": f"overlap-hashed-{store_kind}-{members}",
            "status": status,
            "passed": status == "ok",
            "members": members,
            "store": store_kind,
            "backend": "hashed",
            "transport": "embedded",
            "send_p95_s": send_p95,
            "renew_p95_s": renew_p95,
            "budget_renew_p95_s": SEND_DURING_FIND_P95_S,
            "budget_send_p95_s": SEND_DURING_FIND_P95_S,
            "extra_lag_max_s": lag,
            "lag_budget_s": loop_lag_budget_s(members),
            "expiry_state": "expired",
            "held_ticket": held["message"]["id"],
            "queue": _queue_stats(team),
        }
    except Exception as exc:
        return {
            "name": f"overlap-hashed-{store_kind}-{members}",
            "status": "failed",
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        await team.stop()
        await store.clear()
        await store.close()


async def _run_long_profile_phases(store_kind: str) -> list[dict[str, Any]]:
    """Cold index, warm ranking, and one Profile update on public Team.find."""
    store = await _open_store("memory" if store_kind == "memory" else "redis")
    team = await start_team(store, embeddings=HashedEmbedder())
    members = LONG_PROFILE_MEMBERS
    writer_did = make_did("writer")
    held: dict[str, str] = {}
    out: list[dict[str, Any]] = []

    async def _cold_index():
        await join_member(
            team,
            "writer",
            agent_did=writer_did,
            profile=short_profile(0),
        )
        for index in range(members - 1):
            name = f"agent{index:02d}"
            await join_member(
                team,
                name,
                agent_did=make_did(name),
                profile=heavy_profile(f"task{index:02d}"),
            )
        caller = await join_member(team, "researcher")
        held["token"] = caller["session_token"]
        return await team.find(held["token"], "clause review notes")

    try:
        started = time.perf_counter()
        found, intervals = await probe_during(
            _cold_index(), members=members, enforce=False
        )
        elapsed = time.perf_counter() - started
        assert found["matches"]
        out.append(
            _case_result(
                name=f"hashed-{store_kind}-embedded-{members}-long-cold",
                status="ok",
                budget_p95=None,
                times=[elapsed],
                extras=extra_lag(intervals),
                members=members,
                store=store_kind,
                backend="hashed",
                transport="embedded",
                corpus="valid-long-multi-skill",
                phase="cold-index",
                matches=len(found["matches"]),
                queue=_queue_stats(team),
            )
        )
        times = await _measure_finds(team, held["token"], "clause review notes", 10)
        found, intervals = await probe_during(
            team.find(held["token"], "clause review notes"),
            members=members,
            enforce=False,
        )
        out.append(
            _case_result(
                name=f"hashed-{store_kind}-embedded-{members}-long-warm",
                status="ok",
                budget_p95=None,
                times=times,
                extras=extra_lag(intervals),
                members=members,
                store=store_kind,
                backend="hashed",
                transport="embedded",
                corpus="valid-long-multi-skill",
                phase="warm-rank",
                top=found["matches"][0]["address"],
            )
        )
        await join_member(
            team,
            "writer",
            agent_did=writer_did,
            profile=specialist_profile(),
        )
        started = time.perf_counter()
        found, intervals = await probe_during(
            team.find(held["token"], "missing terms and contract risk"),
            members=members,
            enforce=False,
        )
        elapsed = time.perf_counter() - started
        top = found["matches"][0]["address"]
        status = "ok" if top.startswith("writer@") else "failed"
        case = _case_result(
            name=f"hashed-{store_kind}-embedded-{members}-profile-update",
            status=status,
            budget_p95=None,
            times=[elapsed],
            extras=extra_lag(intervals),
            members=members,
            store=store_kind,
            backend="hashed",
            transport="embedded",
            corpus="valid-long-multi-skill",
            phase="profile-update",
            top=top,
        )
        if status == "failed":
            case["error"] = f"expected writer@ after Profile update, ranked {top}"
            case["passed"] = False
        out.append(case)
        return out
    except Exception as exc:
        out.append(
            {
                "name": f"hashed-{store_kind}-embedded-{members}-long-phase",
                "status": "failed",
                "passed": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        return out
    finally:
        await team.stop()
        await store.clear()
        await store.close()


async def _run_fallback_rebuild(store_kind: str) -> dict[str, Any]:
    """Fail the configured backend on the first find and rebuild hashed space."""
    members = LONG_PROFILE_MEMBERS
    embedder = FailingEmbedder(succeed_calls=members + 2)
    store = await _open_store("memory" if store_kind == "memory" else "redis")
    team = await start_team(store, embeddings=embedder)
    name = f"fallback-rebuild-{store_kind}-embedded-{members}"
    try:
        for index in range(members):
            agent = f"agent{index:02d}"
            await join_member(
                team,
                agent,
                agent_did=make_did(agent),
                profile=heavy_profile(f"task{index:02d}"),
            )
        caller = await join_member(team, "researcher")
        started = time.perf_counter()
        found, intervals = await probe_during(
            team.find(caller["session_token"], "clause review notes"),
            members=members,
            rebuild=True,
            enforce=False,
        )
        elapsed = time.perf_counter() - started
        directory = team._directory
        if not directory.using_fallback or directory.backend_name != "hashed":
            raise RuntimeError(
                f"expected hashed fallback, measured {directory.backend_name}"
            )
        assert found["matches"]
        return _case_result(
            name=name,
            status="ok",
            budget_p95=None,
            times=[elapsed],
            extras=extra_lag(intervals),
            members=members,
            rebuild=True,
            store=store_kind,
            backend="hashed-fallback",
            transport="embedded",
            corpus="valid-long-multi-skill",
            phase="fallback-rebuild",
            matches=len(found["matches"]),
            embed_calls=embedder.calls,
            using_fallback=True,
            queue=_queue_stats(team),
        )
    except Exception as exc:
        return {
            "name": name,
            "status": "failed",
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        await team.stop()
        await store.clear()
        await store.close()


async def _run_stress() -> dict[str, Any]:
    store = MemoryStore()
    team = await start_team(store, embeddings=HashedEmbedder())
    try:
        await join_roster(team, STRESS_MEMBERS)
        caller = await join_member(team, "researcher")
        found, intervals = await probe_during(
            team.find(caller["session_token"], "similar paperwork", limit=20),
            members=STRESS_MEMBERS,
            enforce=False,
        )
        extras = extra_lag(intervals)
        budget = loop_lag_budget_s(STRESS_MEMBERS)
        status = "ok" if extras and max(extras) < budget else "failed"
        return {
            "name": f"hashed-memory-embedded-{STRESS_MEMBERS}-stress",
            "status": status,
            "passed": status == "ok",
            "members": STRESS_MEMBERS,
            "extra_lag_max_s": max(extras) if extras else None,
            "lag_budget_s": budget,
            "matches": len(found["matches"]),
        }
    finally:
        await team.stop()
        await store.close()


def _neural_available(required: bool) -> bool:
    try:
        import fastembed  # noqa: F401
    except ImportError as exc:
        if required:
            raise SystemExit(
                "neural coverage is required; install agentconnect[embeddings]"
            ) from exc
        return False
    return True


def _phase_cases_in_child() -> list[dict[str, Any]]:
    """Run cold/update/rebuild in a new process so 1,000-member finds stay isolated."""
    handle = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    out = Path(handle.name)
    handle.close()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--internal-phases",
                "--out",
                str(out),
            ],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        if out.is_file():
            payload = json.loads(out.read_text(encoding="utf-8"))
            loaded = list(payload.get("cases") or [])
            if loaded:
                return loaded
        detail = (completed.stderr or completed.stdout or "").strip()[-2000:]
        return [
            {
                "name": "phase-worker",
                "status": "failed",
                "passed": False,
                "error": detail or f"exit {completed.returncode}",
            }
        ]
    finally:
        out.unlink(missing_ok=True)


async def run_benchmark(
    *,
    quick: bool = False,
    stress: bool = False,
    require_neural: bool = False,
    internal_phases: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    _quiet_http_logs()
    cases: list[dict[str, Any]] = []
    if internal_phases:
        for store_kind in ("memory", "redis"):
            cases.extend(await _run_long_profile_phases(store_kind))
            cases.append(await _run_fallback_rebuild(store_kind))
        return _finish_report(started, cases)

    neural = _neural_available(require_neural)
    hashed_sizes = (10,) if quick else HASHED_SUPPORTED_MEMBERS
    stores = ("memory",) if quick else ("memory", "redis")
    transports = ("embedded",) if quick else ("embedded", "http")
    if not quick:
        cases.extend(_phase_cases_in_child())
        gc.collect()
    for size in hashed_sizes:
        for store_kind in stores:
            for transport in transports:
                cases.append(
                    await _run_warm_case(
                        store_kind=store_kind,
                        backend="hashed",
                        members=size,
                        transport=transport,
                    )
                )
                gc.collect()
    if not quick:
        cases.append(await _run_overlap("memory"))
        gc.collect()
        cases.append(await _run_overlap("redis"))
        gc.collect()
    if neural:
        neural_sizes = (10,) if quick else NEURAL_MEASURED_MEMBERS
        for size in neural_sizes:
            store_kinds = ("memory",) if size == 1000 or quick else ("memory", "redis")
            transport_kinds = ("embedded",) if size == 1000 or quick else transports
            for store_kind in store_kinds:
                for transport in transport_kinds:
                    cases.append(
                        await _run_warm_case(
                            store_kind=store_kind,
                            backend="neural",
                            members=size,
                            transport=transport,
                        )
                    )
                    gc.collect()
    elif require_neural:
        raise SystemExit("neural coverage is required")
    else:
        cases.append(
            {
                "name": "neural",
                "status": "skipped",
                "passed": False,
                "reason": "fastembed is not installed",
            }
        )
    if stress:
        cases.append(await _run_stress())
    return _finish_report(started, cases)


def _finish_report(started: float, cases: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [case for case in cases if case.get("status") == "failed"]
    measured = [case for case in cases if case.get("status") == "measured"]
    return {
        "revision": _git_revision(),
        "environment": {
            **platform_report(),
            "rss_bytes": _rss_bytes(),
            "cpu_process_s": time.process_time(),
        },
        "provenance": _provenance(),
        "budgets": {
            "hashed_p95_s": {
                str(size): find_p95_budget_s(size) for size in (10, 100, 400, 1000)
            },
            "send_during_find_p95_s": SEND_DURING_FIND_P95_S,
            "rebuild_lag_s": LOOP_LAG_S_REBUILD,
            "warm_samples": WARM_SAMPLES,
        },
        "elapsed_s": time.perf_counter() - started,
        "cases": cases,
        "failed_names": [case["name"] for case in failed],
        "measured_unsupported_names": [case["name"] for case in measured],
    }


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AgentConnect Runtime discovery benchmark"
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--stress", action="store_true")
    parser.add_argument(
        "--internal-phases", action="store_true", help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--require-neural",
        action="store_true",
        default=os.environ.get("AGENTCONNECT_REQUIRE_NEURAL", "").strip()
        in {"1", "true", "yes"},
    )
    args = parser.parse_args(argv)
    report = asyncio.run(
        run_benchmark(
            quick=args.quick,
            stress=args.stress,
            require_neural=args.require_neural,
            internal_phases=args.internal_phases,
        )
    )
    write_report(report, args.out)
    print(
        json.dumps({"out": str(args.out), "failed": report["failed_names"]}, indent=2)
    )
    return 1 if report["failed_names"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
