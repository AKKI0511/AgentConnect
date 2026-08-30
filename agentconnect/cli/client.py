"""HTTP client for CLI commands talking to a running Team.

Loopback Runtime HTTP with no Authorization header runs as ``operator``.
The CLI relies on that, so a person has the same verbs as an Agent.

    from agentconnect.cli.client import RuntimeClient

    client = RuntimeClient("http://127.0.0.1:9000")
    snapshot = client.status()
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator, Optional
from uuid import uuid4

import httpx

from agentconnect.team.errors import TeamError

HTTP_PREFIX = "/agentconnect/v1"


class RuntimeClient:
    """Synchronous HTTP Client for operator CLI commands."""

    def __init__(self, origin: str, *, timeout: float = 35.0) -> None:
        """Talk to the Runtime at ``origin``, for example ``http://127.0.0.1:9000``."""
        self.origin = origin.rstrip("/")
        self._client = httpx.Client(
            base_url=self.origin,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "RuntimeClient":
        """Return this client for use as a context manager."""
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Close on context exit."""
        self.close()

    def status(self) -> dict[str, Any]:
        """GET /status as the loopback operator."""
        return self._get("/status")

    def find(
        self,
        query: str,
        *,
        limit: Optional[int] = None,
        detail: str = "summary",
    ) -> dict[str, Any]:
        """POST /directory/find."""
        body: dict[str, Any] = {"query": query, "detail": detail}
        if limit is not None:
            body["limit"] = limit
        return self._post("/directory/find", body)

    def ask(
        self,
        recipient: str,
        content: Any,
        *,
        deadline_seconds: float = 30.0,
        collect: str = "wait",
    ) -> dict[str, Any]:
        """POST /messages as a reply-expected request."""
        deadline = datetime.now(timezone.utc) + timedelta(seconds=deadline_seconds)
        body = {
            "id": str(uuid4()),
            "recipient": recipient,
            "kind": "request",
            "content": content,
            "collect": collect,
            "deadline": deadline.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }
        timeout = max(self._client.timeout.read or 35.0, deadline_seconds + 10.0)
        return self._post("/messages", body, timeout=timeout)

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        """GET /traces/{trace_id}."""
        return self._get(f"/traces/{trace_id}")

    def issue_token(
        self,
        *,
        name: Optional[str] = None,
        agent_did: Optional[str] = None,
        ttl_seconds: Optional[float] = None,
        single_use: bool = False,
    ) -> dict[str, Any]:
        """POST /tokens."""
        body: dict[str, Any] = {"single_use": single_use}
        if name is not None:
            body["name"] = name
        if agent_did is not None:
            body["agent_did"] = agent_did
        if ttl_seconds is not None:
            body["ttl_seconds"] = ttl_seconds
        return self._post("/tokens", body)

    def revoke_token(self, token: str) -> None:
        """POST /tokens/revoke."""
        response = self._request("POST", "/tokens/revoke", json={"token": token})
        if response.status_code == 204:
            return
        self._raise(response)

    def watch(self) -> Iterator[dict[str, Any]]:
        """Yield Trace events from GET /traces/events."""
        try:
            stream = self._client.stream(
                "GET",
                HTTP_PREFIX + "/traces/events",
                headers={"Accept": "text/event-stream"},
                timeout=None,
            )
        except httpx.HTTPError as exc:
            raise TeamError(
                "unavailable", f"Runtime is unreachable at {self.origin}"
            ) from exc
        try:
            with stream as response:
                if response.status_code != 200:
                    response.read()
                    self._raise(response)
                current_event = "message"
                data_lines: list[str] = []
                for line in response.iter_lines():
                    if line is None:
                        continue
                    if line.startswith(":"):
                        continue
                    if line.startswith("event:"):
                        current_event = line[6:].strip() or "message"
                        continue
                    if line.startswith("data:"):
                        data_lines.append(line[5:].lstrip())
                        continue
                    if line == "":
                        if data_lines:
                            payload = "\n".join(data_lines)
                            try:
                                parsed = json.loads(payload)
                            except json.JSONDecodeError:
                                parsed = {"raw": payload}
                            yield {"type": current_event, "data": parsed}
                        current_event = "message"
                        data_lines = []
        except httpx.HTTPError as exc:
            raise TeamError(
                "unavailable", f"Runtime is unreachable at {self.origin}"
            ) from exc

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return self._client.request(method, HTTP_PREFIX + path, **kwargs)
        except httpx.HTTPError as exc:
            raise TeamError(
                "unavailable", f"Runtime is unreachable at {self.origin}"
            ) from exc

    def _get(self, path: str) -> dict[str, Any]:
        return self._result(self._request("GET", path))

    def _post(
        self, path: str, body: dict[str, Any], *, timeout: Optional[float] = None
    ) -> dict[str, Any]:
        return self._result(self._request("POST", path, json=body, timeout=timeout))

    def _result(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code in {200, 204}:
            if response.status_code == 204 or not response.content:
                return {}
            data = response.json()
            if isinstance(data, dict):
                return data
            raise TeamError("internal", "Runtime returned a non-object body")
        self._raise(response)
        raise AssertionError("unreachable")

    def _raise(self, response: httpx.Response) -> None:
        try:
            payload = response.json()
        except Exception:
            payload = {}
        if isinstance(payload, dict) and isinstance(payload.get("code"), str):
            raise TeamError(
                payload["code"],
                str(payload.get("message") or response.reason_phrase),
                details=(
                    payload.get("details")
                    if isinstance(payload.get("details"), dict)
                    else None
                ),
                retryable=(
                    payload.get("retryable")
                    if isinstance(payload.get("retryable"), bool)
                    else None
                ),
            )
        raise TeamError(
            "unavailable",
            f"Runtime HTTP {response.status_code} from {self.origin}",
        )
