"""Yielding memory store, Redis require-path, and call counters."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import shutil
import subprocess
import time
import uuid
from typing import Any, Optional, Sequence

import pytest

from agentconnect.team.store.base import Store, StoreRecord
from agentconnect.team.store.memory import MemoryStore
from agentconnect.team.store.ops import ApplyResult, StoreOp
from agentconnect.team.store.redis import RedisStore

DEFAULT_REDIS_URL = "redis://127.0.0.1:6380/15"


def redis_url() -> str:
    """Return the Redis URL. Local default is the dedicated 6380 instance."""
    return os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)


def redis_is_required() -> bool:
    """True in CI or when AGENTCONNECT_REQUIRE_REDIS is set."""
    flag = os.environ.get("AGENTCONNECT_REQUIRE_REDIS", "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    return os.environ.get("CI", "").strip().lower() in {"1", "true"}


class YieldingStore(Store):
    """Wrap a Store and yield the event loop around every awaited call.

    MemoryStore otherwise runs whole operations without an await inside the
    lock. Yielding lets concurrent Runtime tasks interleave the way Redis I/O
    does, so races cannot hide behind an in-process critical section.
    """

    def __init__(self, inner: Store | None = None) -> None:
        self._inner = inner or MemoryStore()
        self.persistence = getattr(self._inner, "persistence", "volatile")

    async def _call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        await asyncio.sleep(0)
        result = getattr(self._inner, name)(*args, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        await asyncio.sleep(0)
        return result

    async def open(self) -> None:
        await self._call("open")

    async def close(self) -> None:
        await self._call("close")

    async def get(self, key: str) -> Any | None:
        return await self._call("get", key)

    async def get_many(self, keys: Sequence[str]) -> list[Any | None]:
        return await self._call("get_many", keys)

    async def get_record(self, key: str) -> StoreRecord | None:
        return await self._call("get_record", key)

    async def apply(self, ops: Sequence[StoreOp]) -> ApplyResult:
        return await self._call("apply", ops)

    async def put(self, key: str, value: Any) -> None:
        await self._call("put", key, value)

    async def insert(self, key: str, value: Any) -> bool:
        return await self._call("insert", key, value)

    async def compare_and_set(self, key: str, version: int, value: Any) -> bool:
        return await self._call("compare_and_set", key, version, value)

    async def delete(self, key: str) -> None:
        await self._call("delete", key)

    async def set_add(self, key: str, member: str) -> None:
        await self._call("set_add", key, member)

    async def set_remove(self, key: str, member: str) -> None:
        await self._call("set_remove", key, member)

    async def set_members(self, key: str) -> list[str]:
        return await self._call("set_members", key)

    async def set_is_member(self, key: str, member: str) -> bool:
        return await self._call("set_is_member", key, member)

    async def index_add(self, key: str, score: float, member: str) -> None:
        await self._call("index_add", key, score, member)

    async def index_remove(self, key: str, member: str) -> None:
        await self._call("index_remove", key, member)

    async def index_range(
        self,
        key: str,
        *,
        max_score: float,
        min_score: float = float("-inf"),
        limit: Optional[int] = None,
    ) -> list[str]:
        return await self._call(
            "index_range", key, max_score=max_score, min_score=min_score, limit=limit
        )

    async def index_card(self, key: str) -> int:
        return await self._call("index_card", key)

    async def index_add_if_card_below(
        self, key: str, score: float, member: str, max_card: int
    ) -> bool:
        return await self._call("index_add_if_card_below", key, score, member, max_card)

    async def increment_if_below(
        self,
        key: str,
        limit: int,
        *,
        ttl_seconds: Optional[float] = None,
    ) -> bool:
        return await self._call(
            "increment_if_below", key, limit, ttl_seconds=ttl_seconds
        )

    async def decrement_floor(
        self,
        key: str,
        *,
        ttl_seconds: Optional[float] = None,
    ) -> int:
        return await self._call("decrement_floor", key, ttl_seconds=ttl_seconds)

    async def exists(self, key: str) -> bool:
        return await self._call("exists", key)

    async def ping(self) -> None:
        await self._call("ping")

    async def clear(self) -> None:
        await self._call("clear")


class CountingStore(Store):
    """Count Store calls and approximate write bytes for reports."""

    def __init__(self, inner: Store) -> None:
        self._inner = inner
        self.persistence = getattr(inner, "persistence", "volatile")
        self.calls: dict[str, int] = {}
        self.write_bytes = 0

    def _count(self, name: str) -> None:
        self.calls[name] = self.calls.get(name, 0) + 1

    async def _call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        self._count(name)
        result = getattr(self._inner, name)(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    async def open(self) -> None:
        await self._call("open")

    async def close(self) -> None:
        await self._call("close")

    async def get(self, key: str) -> Any | None:
        return await self._call("get", key)

    async def get_many(self, keys: Sequence[str]) -> list[Any | None]:
        return await self._call("get_many", keys)

    async def get_record(self, key: str) -> StoreRecord | None:
        return await self._call("get_record", key)

    async def apply(self, ops: Sequence[StoreOp]) -> ApplyResult:
        self.write_bytes += sum(len(str(op)) for op in ops)
        return await self._call("apply", ops)

    async def put(self, key: str, value: Any) -> None:
        self.write_bytes += len(str(value))
        await self._call("put", key, value)

    async def insert(self, key: str, value: Any) -> bool:
        self.write_bytes += len(str(value))
        return await self._call("insert", key, value)

    async def compare_and_set(self, key: str, version: int, value: Any) -> bool:
        self.write_bytes += len(str(value))
        return await self._call("compare_and_set", key, version, value)

    async def delete(self, key: str) -> None:
        await self._call("delete", key)

    async def set_add(self, key: str, member: str) -> None:
        await self._call("set_add", key, member)

    async def set_remove(self, key: str, member: str) -> None:
        await self._call("set_remove", key, member)

    async def set_members(self, key: str) -> list[str]:
        return await self._call("set_members", key)

    async def set_is_member(self, key: str, member: str) -> bool:
        return await self._call("set_is_member", key, member)

    async def index_add(self, key: str, score: float, member: str) -> None:
        await self._call("index_add", key, score, member)

    async def index_remove(self, key: str, member: str) -> None:
        await self._call("index_remove", key, member)

    async def index_range(
        self,
        key: str,
        *,
        max_score: float,
        min_score: float = float("-inf"),
        limit: Optional[int] = None,
    ) -> list[str]:
        return await self._call(
            "index_range", key, max_score=max_score, min_score=min_score, limit=limit
        )

    async def index_card(self, key: str) -> int:
        return await self._call("index_card", key)

    async def index_add_if_card_below(
        self, key: str, score: float, member: str, max_card: int
    ) -> bool:
        return await self._call("index_add_if_card_below", key, score, member, max_card)

    async def increment_if_below(
        self,
        key: str,
        limit: int,
        *,
        ttl_seconds: Optional[float] = None,
    ) -> bool:
        return await self._call(
            "increment_if_below", key, limit, ttl_seconds=ttl_seconds
        )

    async def decrement_floor(
        self,
        key: str,
        *,
        ttl_seconds: Optional[float] = None,
    ) -> int:
        return await self._call("decrement_floor", key, ttl_seconds=ttl_seconds)

    async def ping(self) -> None:
        await self._call("ping")

    async def clear(self) -> None:
        await self._call("clear")


async def connect_redis(prefix: str | None = None) -> RedisStore:
    """Open Redis or skip/fail according to the require-path."""
    url = redis_url()
    store = RedisStore(url, prefix=prefix or f"ac:test:{uuid.uuid4()}")
    try:
        await store.open()
        await store.ping()
    except Exception as exc:
        try:
            await store.close()
        except Exception:
            pass
        if redis_is_required():
            pytest.fail(f"Redis is required at {url}: {type(exc).__name__}: {exc}")
        pytest.skip(f"Redis is not reachable at {url}")
    return store


async def restart_redis() -> None:
    """Restart the Redis server used by tests and wait until PING succeeds.

    Uses ``DEBUG RESTART`` (enable it when starting the test server).
    Falls back to restarting a Docker Redis that publishes the URL port,
    including GitHub Actions service containers.
    """
    url = redis_url()
    if await _try_debug_restart(url):
        await _wait_for_redis(url)
        return
    _docker_restart_redis()
    await _wait_for_redis(url)


async def _try_debug_restart(url: str) -> bool:
    from redis.asyncio import Redis
    from redis.exceptions import ConnectionError as RedisConnectionError
    from redis.exceptions import ResponseError
    from redis.exceptions import TimeoutError as RedisTimeoutError

    client = Redis.from_url(url, decode_responses=True)
    try:
        try:
            await client.execute_command("DEBUG", "RESTART")
            return True
        except (
            RedisConnectionError,
            RedisTimeoutError,
            ConnectionError,
            OSError,
            TimeoutError,
        ):
            return True
        except ResponseError:
            return False
    finally:
        try:
            await client.aclose()
        except Exception:
            pass


def _redis_port() -> int:
    from urllib.parse import urlparse

    parsed = urlparse(redis_url())
    return int(parsed.port or 6379)


def _docker_redis_container() -> str | None:
    from urllib.parse import urlparse

    docker = shutil.which("docker")
    if docker is None or urlparse(redis_url()).hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        return None
    args = [docker, "ps", "-a", "--filter", f"publish={_redis_port()}"]
    named = os.environ.get("AGENTCONNECT_REDIS_CONTAINER", "").strip()
    if named:
        args.extend(["--filter", f"name=^/{named}$"])
    listed = subprocess.run(
        [*args, "--format", "{{.ID}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    candidates = listed.stdout.split() if listed.returncode == 0 else []
    # Never choose an unrelated named container or guess between matches.
    return candidates[0] if len(candidates) == 1 else None


def _docker_restart_redis() -> None:
    docker = shutil.which("docker")
    container = _docker_redis_container()
    if docker is None:
        pytest.fail("Redis DEBUG RESTART failed and docker is not available")
    if container is None:
        pytest.fail(
            "Redis DEBUG RESTART failed and no Docker Redis publishes "
            f"port {_redis_port()}"
        )
    completed = subprocess.run(
        [docker, "restart", container],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        pytest.fail(
            "Redis did not restart via DEBUG RESTART or docker: "
            + (completed.stderr or completed.stdout or "unknown error")
        )


async def _redis_accepts_ping(url: str, *, timeout_s: float) -> bool:
    from redis.asyncio import Redis

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        probe = Redis.from_url(url, decode_responses=True)
        try:
            await probe.ping()
            await probe.aclose()
            return True
        except Exception:
            try:
                await probe.aclose()
            except Exception:
                pass
            await asyncio.sleep(0.1)
    return False


async def _wait_for_redis(url: str, *, timeout_s: float = 20.0) -> None:
    if await _redis_accepts_ping(url, timeout_s=timeout_s):
        return
    pytest.fail("Redis did not accept PING after restart")


async def drop_http_send(origin: str, token: str, body: dict[str, Any]) -> None:
    """Write an HTTP send, then close the socket without reading the response."""
    from urllib.parse import urlparse

    parsed = urlparse(origin)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    payload = json.dumps(body).encode("utf-8")
    _reader, writer = await asyncio.open_connection(host, port)
    request = (
        "POST /agentconnect/v1/messages HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Authorization: Bearer {token}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(payload)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii") + payload
    writer.write(request)
    await writer.drain()
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


async def open_store(kind: str) -> Store:
    """Return a yielding memory store, MemoryStore, or required/skippable Redis."""
    if kind == "yielding-memory":
        store = YieldingStore()
        await store.open()
        return store
    if kind == "memory":
        store = MemoryStore()
        await store.open()
        return store
    if kind == "redis":
        return await connect_redis()
    raise ValueError(f"unknown store kind: {kind}")
