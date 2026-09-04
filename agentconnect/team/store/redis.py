"""Redis Store. Memberships, mailboxes, Messages, Tickets, and Threads survive restart."""

from __future__ import annotations

import json
from typing import Any, Optional

from agentconnect.team.store.base import Store, StoreRecord

_CAS_LUA = """
local cur = redis.call('GET', KEYS[1])
if not cur then return 0 end
local doc = cjson.decode(cur)
if tonumber(doc.v) ~= tonumber(ARGV[1]) then return 0 end
redis.call('SET', KEYS[1], ARGV[2])
return 1
"""

_INDEX_ADD_IF_BELOW_LUA = """
local member = ARGV[3]
local existing = redis.call('ZSCORE', KEYS[1], member)
if existing then
  redis.call('ZADD', KEYS[1], ARGV[2], member)
  return 1
end
local n = redis.call('ZCARD', KEYS[1])
if n >= tonumber(ARGV[1]) then return 0 end
redis.call('ZADD', KEYS[1], ARGV[2], member)
return 1
"""

_INCR_IF_BELOW_LUA = """
local raw = redis.call('GET', KEYS[1])
local n = 0
local v = 0
if raw then
  local doc = cjson.decode(raw)
  n = tonumber(doc.d) or 0
  v = tonumber(doc.v) or 0
end
if n >= tonumber(ARGV[1]) then return 0 end
local wrapped = cjson.encode({v = v + 1, d = n + 1})
redis.call('SET', KEYS[1], wrapped)
local ttl = tonumber(ARGV[2])
if ttl and ttl > 0 then
  redis.call('EXPIRE', KEYS[1], ttl)
end
return 1
"""

_DECR_FLOOR_LUA = """
local raw = redis.call('GET', KEYS[1])
local n = 0
local v = 0
if raw then
  local doc = cjson.decode(raw)
  n = tonumber(doc.d) or 0
  v = tonumber(doc.v) or 0
end
if n <= 0 then
  return 0
end
local nxt = n - 1
local wrapped = cjson.encode({v = v + 1, d = nxt})
redis.call('SET', KEYS[1], wrapped)
local ttl = tonumber(ARGV[1])
if ttl and ttl > 0 then
  redis.call('EXPIRE', KEYS[1], ttl)
end
return nxt
"""


class RedisStore(Store):
    """Durable document store keyed under a per-Team prefix.

    Pass the same ``url`` and ``prefix`` to a new Runtime after a restart to
    recover open Tickets and queued Mailbox work. ``insert`` uses ``SET NX``.
    ``compare_and_set`` and Mailbox depth checks use small Lua scripts.
    """

    persistence = "durable"

    def __init__(self, url: str, *, prefix: str = "ac") -> None:
        """Connect later via ``open``. Keys are stored under ``prefix``."""
        if not url:
            raise ValueError("Redis store requires a URL")
        self._url = url
        self._prefix = prefix.rstrip(":")
        self._redis: Any = None
        self._cas = None
        self._index_add_if_below = None
        self._incr_if_below = None
        self._decr_floor = None

    def _key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    def _index_key(self, key: str) -> str:
        return f"{self._key(key)}#z"

    def _set_key(self, key: str) -> str:
        return f"{self._key(key)}#set"

    async def open(self) -> None:
        """Open the Redis client connection."""
        await self._client()

    async def _client(self):
        if self._redis is not None:
            return self._redis
        from redis.asyncio import Redis

        self._redis = Redis.from_url(self._url, decode_responses=True)
        self._cas = self._redis.register_script(_CAS_LUA)
        self._index_add_if_below = self._redis.register_script(_INDEX_ADD_IF_BELOW_LUA)
        self._incr_if_below = self._redis.register_script(_INCR_IF_BELOW_LUA)
        self._decr_floor = self._redis.register_script(_DECR_FLOOR_LUA)
        return self._redis

    async def close(self) -> None:
        """Close the Redis client. The next ``open`` reconnects."""
        if self._redis is None:
            return
        try:
            await self._redis.aclose()
        finally:
            self._redis = None
            self._cas = None
            self._index_add_if_below = None
            self._incr_if_below = None
            self._decr_floor = None

    async def ping(self) -> None:
        """Confirm Redis is reachable."""
        client = await self._client()
        await client.ping()

    async def get(self, key: str) -> Any | None:
        """Return the JSON value at ``key``, or None."""
        record = await self.get_record(key)
        if record is None:
            return None
        return record.value

    async def get_record(self, key: str) -> StoreRecord | None:
        """Return value and version at ``key``, or None."""
        client = await self._client()
        raw = await client.get(self._key(key))
        if raw is None:
            return None
        return _unwrap(raw)

    async def put(self, key: str, value: Any) -> None:
        """Write a JSON value at ``key``, bumping the version."""
        record = await self.get_record(key)
        version = 1 if record is None else record.version + 1
        client = await self._client()
        await client.set(self._key(key), _wrap(value, version))

    async def insert(self, key: str, value: Any) -> bool:
        """Write ``value`` only if ``key`` is absent (``SET NX``)."""
        client = await self._client()
        result = await client.set(self._key(key), _wrap(value, 1), nx=True)
        return bool(result)

    async def compare_and_set(self, key: str, version: int, value: Any) -> bool:
        """Replace ``key`` when the stored version matches, via Lua."""
        client = await self._client()
        script = self._cas
        if script is None:
            await self._client()
            script = self._cas
        result = await script(
            keys=[self._key(key)],
            args=[str(version), _wrap(value, version + 1)],
            client=client,
        )
        return int(result or 0) == 1

    async def delete(self, key: str) -> None:
        """Remove the document, set, and index at ``key``."""
        client = await self._client()
        namespaced = self._key(key)
        await client.delete(namespaced, self._set_key(key), self._index_key(key))

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

    async def index_add(self, key: str, score: float, member: str) -> None:
        """Add or update ``member`` in the Redis sorted set at ``key``."""
        client = await self._client()
        await client.zadd(self._index_key(key), {member: float(score)})

    async def index_remove(self, key: str, member: str) -> None:
        """Remove ``member`` from the Redis sorted set at ``key``."""
        client = await self._client()
        await client.zrem(self._index_key(key), member)

    async def index_range(
        self,
        key: str,
        *,
        max_score: float,
        min_score: float = float("-inf"),
        limit: Optional[int] = None,
    ) -> list[str]:
        """Return members with scores in ``[min_score, max_score]``, lowest first."""
        client = await self._client()
        kwargs: dict[str, Any] = {}
        if limit is not None:
            kwargs["start"] = 0
            kwargs["num"] = max(0, int(limit))
        members = await client.zrangebyscore(
            self._index_key(key),
            min_score,
            max_score,
            **kwargs,
        )
        return [str(item) for item in members]

    async def index_card(self, key: str) -> int:
        """Return the number of members in the Redis sorted set at ``key``."""
        client = await self._client()
        return int(await client.zcard(self._index_key(key)))

    async def index_add_if_card_below(
        self, key: str, score: float, member: str, max_card: int
    ) -> bool:
        """Add ``member`` when the sorted set has fewer than ``max_card`` members."""
        client = await self._client()
        script = self._index_add_if_below
        if script is None:
            await self._client()
            script = self._index_add_if_below
        result = await script(
            keys=[self._index_key(key)],
            args=[str(max_card), str(float(score)), member],
            client=client,
        )
        return int(result or 0) == 1

    async def increment_if_below(
        self,
        key: str,
        limit: int,
        *,
        ttl_seconds: Optional[float] = None,
    ) -> bool:
        """Increment an integer document when it is below ``limit``."""
        client = await self._client()
        script = self._incr_if_below
        if script is None:
            await self._client()
            script = self._incr_if_below
        ttl = 0 if ttl_seconds is None else max(1, int(ttl_seconds))
        result = await script(
            keys=[self._key(key)],
            args=[str(limit), str(ttl)],
            client=client,
        )
        return int(result or 0) == 1

    async def decrement_floor(
        self,
        key: str,
        *,
        ttl_seconds: Optional[float] = None,
    ) -> int:
        """Decrement an integer document, not below ``0``."""
        client = await self._client()
        script = self._decr_floor
        if script is None:
            await self._client()
            script = self._decr_floor
        ttl = 0 if ttl_seconds is None else max(1, int(ttl_seconds))
        result = await script(
            keys=[self._key(key)],
            args=[str(ttl)],
            client=client,
        )
        return int(result or 0)

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


def _wrap(value: Any, version: int) -> str:
    return json.dumps(
        {"v": int(version), "d": value},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _unwrap(raw: str) -> StoreRecord:
    payload = json.loads(raw)
    if isinstance(payload, dict) and "v" in payload and "d" in payload:
        return StoreRecord(value=payload["d"], version=int(payload["v"]))
    return StoreRecord(value=payload, version=1)
