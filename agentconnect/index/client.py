"""HTTP client for one Index process.

[`IndexClient`][agentconnect.index.client.IndexClient] stores and searches
[`DirectoryEntry`][agentconnect.core.directory.DirectoryEntry] snapshots on a
running Index. Same-Team discovery is
[`BaseAgent.find`][agentconnect.agent.base.BaseAgent.find].

`close` closes this HTTP connection and leaves Index records in place.
Reads may retry a dropped connection or HTTP 502, 503, or 504. Writes
are not retried. `get` returns None when that Address is absent.
Any other missing route or a body that is not the expected snapshot raises.
"""

from __future__ import annotations

import asyncio
from types import TracebackType
from urllib.parse import quote

import httpx
from pydantic import TypeAdapter

from agentconnect.core.base import dump_public, parse_schema
from agentconnect.core.directory import DirectoryEntry
from agentconnect.index.models import IndexSearchHit

_ENTRIES = TypeAdapter(list[DirectoryEntry])
_SEARCH_HITS = TypeAdapter(list[IndexSearchHit])
_RETRY_STATUS = frozenset({502, 503, 504})
_MISSING_ENTRY = {"detail": "entry not found"}


def _entry_path(address: str) -> str:
    return f"entries/{quote(str(address), safe='')}"


class IndexClient:
    """HTTP client for one running Index."""

    def __init__(
        self, base_url: str = "http://127.0.0.1:8000", *, timeout: float = 30.0
    ) -> None:
        """
        Raises:
            ValueError: `base_url` is empty.
        """
        if not base_url or not str(base_url).strip():
            raise ValueError("base_url is required")
        self.base_url = str(base_url).rstrip("/") + "/"
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def close(self) -> None:
        """Close this HTTP connection. Stored Index records stay."""
        await self._client.aclose()

    async def __aenter__(self) -> IndexClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def put(self, entry: DirectoryEntry) -> DirectoryEntry:
        """Insert or replace `entry` and return the stored copy.

        The snapshot is keyed by its canonical qualified Address. A cancelled
        or interrupted HTTP write may already have committed; call `get` to
        check. Writes are not retried.
        """
        response = await self._request(
            "PUT",
            _entry_path(entry.address),
            json_body=dump_public(entry),
            ok=200,
        )
        return parse_schema(DirectoryEntry, response.json())

    async def get(self, address: str) -> DirectoryEntry | None:
        """Return the stored snapshot, or None when that Address is absent."""
        try:
            response = await self._request(
                "GET",
                _entry_path(address),
                ok=200,
                retry=True,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                try:
                    if exc.response.json() == _MISSING_ENTRY:
                        return None
                except ValueError:
                    pass
            raise
        return parse_schema(DirectoryEntry, response.json())

    async def delete(self, address: str) -> None:
        """Remove the snapshot at `address`. A missing Address is not an error."""
        await self._request("DELETE", _entry_path(address), ok=204)

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        tags: list[str] | None = None,
    ) -> list[IndexSearchHit]:
        """Return ranked hits for `query`.

        Each hit has the snapshot and its score. `limit` is 1 to 50. When
        `tags` is set, every listed tag must be on the Profile.
        """
        body: dict[str, object] = {"query": query, "limit": limit}
        if tags is not None:
            body["tags"] = tags
        response = await self._request(
            "POST",
            "search",
            json_body=body,
            ok=200,
            retry=True,
        )
        return _SEARCH_HITS.validate_python(response.json())

    async def list(self) -> list[DirectoryEntry]:
        """Return every snapshot the process is holding."""
        response = await self._request("GET", "entries", ok=200, retry=True)
        return _ENTRIES.validate_python(response.json())

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: object | None = None,
        ok: int,
        retry: bool = False,
    ) -> httpx.Response:
        attempts = 4 if retry else 1
        for attempt in range(attempts):
            try:
                response = await self._client.request(method, path, json=json_body)
            except httpx.RequestError:
                if not retry or attempt == attempts - 1:
                    raise
                await asyncio.sleep(0.5 * (2**attempt))
                continue
            if (
                response.status_code in _RETRY_STATUS
                and retry
                and attempt < attempts - 1
            ):
                await asyncio.sleep(0.5 * (2**attempt))
                continue
            if response.status_code != ok:
                response.raise_for_status()
                raise httpx.HTTPStatusError(
                    f"unexpected status {response.status_code}",
                    request=response.request,
                    response=response,
                )
            return response
        raise RuntimeError("Index request failed")
