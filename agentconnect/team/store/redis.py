"""Redis Store. Memberships, mailboxes, Messages, Tickets, and Threads survive restart."""

from __future__ import annotations

import json
from typing import Any

from agentconnect.team.store.base import Store


class RedisStore(Store):
    """Durable document store keyed under a per-Team prefix.

    Pass the same ``url`` and ``prefix`` to a new Runtime after a restart to
    recover open Tickets and queued Mailbox work.
    """

    persistence = "durable"

    def __init__(self, url: str, *, prefix: str = "ac") -> None:
        """Connect later via ``open``. Keys are stored under ``prefix``."""
        if not url:
            raise ValueError("Redis store requires a URL")
        self._url = url
        self._prefix = prefix.rstrip(":")
        self._redis: Any = None

    def _key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    async def open(self) -> None:
        """Open the Redis client connection."""
        await self._client()

    async def _client(self):
        if self._redis is not None:
            return self._redis
        from redis.asyncio import Redis

        self._redis = Redis.from_url(self._url, decode_responses=True)
        return self._redis

    async def close(self) -> None:
        """Close the Redis client. The next ``open`` reconnects."""
        if self._redis is None:
            return
        try:
            await self._redis.aclose()
        finally:
            self._redis = None

    async def ping(self) -> None:
        """Confirm Redis is reachable."""
        client = await self._client()
        await client.ping()

    async def get(self, key: str) -> Any | None:
        """Return the JSON value at ``key``, or None."""
        client = await self._client()
        raw = await client.get(self._key(key))
        if raw is None:
            return None
        return json.loads(raw)

    async def put(self, key: str, value: Any) -> None:
        """Write a JSON value at ``key``."""
        client = await self._client()
        await client.set(
            self._key(key), json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        )

    async def delete(self, key: str) -> None:
        """Remove the document and set at ``key``."""
        client = await self._client()
        namespaced = self._key(key)
        await client.delete(namespaced)
        await client.delete(self._set_key(key))

    def _set_key(self, key: str) -> str:
        return f"{self._key(key)}#set"

    async def set_add(self, key: str, member: str) -> None:
        """Add ``member`` to the Redis set at ``key``."""
        client = await self._client()
        await client.sadd(self._set_key(key), member)

    async def set_remove(self, key: str, member: str) -> None:
        """Remove ``member`` from the Redis set at ``key``."""
        client = await self._client()
        await client.srem(self._set_key(key), member)

    async def set_members(self, key: str) -> list[str]:
        """Return the sorted members of the Redis set at ``key``."""
        client = await self._client()
        members = await client.smembers(self._set_key(key))
        return sorted(str(item) for item in members)

    async def clear(self) -> None:
        """Delete every key under this store's prefix."""
        client = await self._client()
        pattern = f"{self._prefix}:*"
        batch: list[str] = []
        async for redis_key in client.scan_iter(match=pattern, count=200):
            batch.append(redis_key)
            if len(batch) >= 200:
                await client.delete(*batch)
                batch.clear()
        if batch:
            await client.delete(*batch)
