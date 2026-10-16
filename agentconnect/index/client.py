"""HTTP client for one Index process.

[`IndexClient`][agentconnect.index.client.IndexClient] stores and searches
records on a running Index. Same-Team discovery is
[`BaseAgent.find`][agentconnect.agent.base.BaseAgent.find].

`close` closes this HTTP connection and leaves Index records in place.
Reads may retry a dropped connection or HTTP 502, 503, or 504. Writes
are not retried. `get_registration` returns None when the id is absent.
Any other missing route or a body that is not the expected record raises.
"""

from __future__ import annotations

import asyncio
from types import TracebackType

import httpx
from pydantic import TypeAdapter

from agentconnect.index.models import (
    AgentRegistration,
    IndexQuery,
    IndexSearchHit,
    RegistrationUpdate,
    _canonical_agent_id,
)

_REGISTRATIONS = TypeAdapter(list[AgentRegistration])
_SEARCH_HITS = TypeAdapter(list[IndexSearchHit])
_RETRY_STATUS = frozenset({502, 503, 504})


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

    async def register(self, registration: AgentRegistration) -> AgentRegistration:
        """Store `registration` and return the stored copy.

        A repeated id is HTTP 409. An id that cannot go in a URL path,
        or a DID that does not match its public key, is rejected before
        a record is stored.
        """
        response = await self._request(
            "POST",
            "agents/register",
            json_body=registration.model_dump(mode="json"),
            ok=201,
        )
        return AgentRegistration.model_validate(response.json())

    async def get_registration(self, agent_id: str) -> AgentRegistration | None:
        """Return the stored record, or None when that id is absent."""
        try:
            response = await self._request(
                "GET",
                f"agents/{_canonical_agent_id(agent_id)}",
                ok=200,
                retry=True,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                try:
                    if exc.response.json() == {"detail": "registration not found"}:
                        return None
                except ValueError:
                    pass
            raise
        return AgentRegistration.model_validate(response.json())

    async def list_registrations(self) -> list[AgentRegistration]:
        """Return every record the process is holding."""
        response = await self._request("GET", "agents", ok=200, retry=True)
        return _REGISTRATIONS.validate_python(response.json())

    async def update_registration(
        self, agent_id: str, updates: RegistrationUpdate
    ) -> AgentRegistration:
        """Replace the fields set on `updates`. An unknown id is HTTP 404."""
        response = await self._request(
            "PUT",
            f"agents/{_canonical_agent_id(agent_id)}",
            json_body=updates.model_dump(mode="json", exclude_unset=True),
            ok=200,
        )
        return AgentRegistration.model_validate(response.json())

    async def unregister(self, agent_id: str) -> None:
        """Remove `agent_id`. An unknown id is HTTP 404."""
        await self._request("DELETE", f"agents/{_canonical_agent_id(agent_id)}", ok=200)

    async def search(self, query: IndexQuery) -> list[IndexSearchHit]:
        """Return ranked hits. Each hit has the record and its score."""
        response = await self._request(
            "POST",
            "agents/search",
            json_body=query.model_dump(mode="json"),
            ok=200,
            retry=True,
        )
        return _SEARCH_HITS.validate_python(response.json())

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
