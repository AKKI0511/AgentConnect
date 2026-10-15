from __future__ import annotations

from collections.abc import Mapping

import logging
from typing import Literal, Optional, Tuple, Dict

import httpx
import time
import asyncio
import random

from agentconnect.transport.base import OutboundTransport, RouteContext
from agentconnect.transport.schemas import TransportTarget, InboxResponse
from agentconnect.transport.envelope import CollaborationMessage as Message

logger = logging.getLogger(__name__)


class HTTPOutboundTransport(OutboundTransport):
    """Default AgentConnect HTTP v1 transport over HTTP.

    Endpoints (server responsibilities):
    - POST `{target.url}{target.inbox_path}` -> JSON `{status, request_id?, response?}`
      - HTTP 200: completed synchronously; may include `response`
      - HTTP 201/202: accepted/pending; should include `request_id`
    - GET  `{target.url}{target.inbox_path}/{request_id}` -> JSON `{status, response?}`
      - HTTP 200: `status` in {completed, pending}
      - HTTP 404/410: not found

    Contract (see `OutboundTransport`):
    - send(...) -> (ok, immediate_response?, request_id?)
    - check(...) -> (status: 'completed'|'pending'|'not_found', response?)
    """

    def __init__(
        self,
        verify_ssl: Optional[bool] = None,
        timeout: Optional[float] = None,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
        retries: Optional[int] = None,
        backoff_factor: Optional[float] = None,
        jitter_seconds: Optional[float] = None,
        idempotency_header: Optional[str] = None,
    ) -> None:
        """Initialize HTTP transport with retry defaults."""
        timeout_v = timeout if timeout is not None else 30.0
        connect_timeout_v = connect_timeout if connect_timeout is not None else 10.0
        read_timeout_v = read_timeout if read_timeout is not None else 20.0
        self._timeout = httpx.Timeout(
            timeout=timeout_v, connect=connect_timeout_v, read=read_timeout_v
        )

        self._verify_ssl = verify_ssl if verify_ssl is not None else True
        self._retries = retries if retries is not None else 3
        self._backoff_factor = backoff_factor if backoff_factor is not None else 0.5
        self._jitter = jitter_seconds if jitter_seconds is not None else 0.2
        self._idempotency_header = (
            idempotency_header
            if idempotency_header is not None
            else "X-Idempotency-Key"
        )
        # Simple per-target circuit breaker and health cache (keyed by base_url+inbox_path)
        self._cb_state: dict[
            str, tuple[int, float]
        ] = {}  # key -> (fail_count, open_until_ts)
        self._down_cache: dict[str, float] = {}  # key -> down_until_ts
        # Persistent clients keyed by base URL for reuse
        self._clients: Dict[str, httpx.AsyncClient] = {}

    async def send(
        self, message: Message, target: TransportTarget, ctx: RouteContext
    ) -> Tuple[bool, Optional[Message], Optional[str]]:
        """Send a collaboration request to a remote inbox.

        Returns:
            (ok, immediate_response, request_id)

        Behavior:
        - POST 200 with `status='completed'` and a `response` → returns the response immediately.
        - POST 201/202 (or 200 with `accepted|pending` body/missing body) → returns ok=True and any `request_id`.
        - POST 5xx/408/425/429 → returns ok=False and trips short circuit breaker/mark-down.
        - POST non-retryable 4xx → returns ok=False without tripping the circuit breaker.
        """
        base_url = (target.url or "").rstrip("/")
        path = target.inbox_path
        url = f"{base_url}{path}"
        cb_key = url

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "envelope": message.to_wire_dict(),
        }

        # Idempotency key header: prefer request_id; fallback to response_to for responses
        if message.metadata:
            req_id = message.metadata.get("request_id") or message.metadata.get(
                "response_to"
            )
            if isinstance(req_id, str) and req_id:
                headers[self._idempotency_header] = req_id

        if not self._verify_ssl:
            logger.warning("verify_ssl disabled for HTTPOutboundTransport")
        client = await self._get_client(base_url)
        # Circuit breaker check (shared key with GET/poll)
        if self._is_cb_open(cb_key) or self._is_marked_down(cb_key):
            return False, None, None
        try:
            resp = await self._request_with_retries(
                client=client, method="POST", url=url, headers=headers, json=payload
            )
        except httpx.RequestError:
            # Network-level exhaustion: treat like transient/server failure
            self._record_cb_failure(cb_key)
            self._mark_down(cb_key)
            return False, None, None

        code = resp.status_code
        # Parse body if JSON and expected
        parsed: Optional[InboxResponse] = None
        if code in (200, 201, 202):
            try:
                parsed = InboxResponse.model_validate(resp.json())
            except Exception:
                try:
                    body_preview = resp.text
                except Exception:
                    body_preview = "<unavailable>"
                logger.error("Error parsing response url=%s body=%s", url, body_preview)
                parsed = None

        # Success paths
        if code in (200, 201, 202):
            self._record_cb_success(cb_key)
            self._mark_up(cb_key)
            if (
                code == 200
                and parsed
                and parsed.status == "completed"
                and parsed.response
            ):
                response_msg = Message.from_wire_dict(parsed.response)
                return True, response_msg, parsed.request_id
            # Accepted/pending or created: return request id if present
            request_id = parsed.request_id if parsed else None
            return True, None, request_id

        # Non-success paths
        if self._should_trip_cb(code):
            self._record_cb_failure(cb_key)
            self._mark_down(cb_key)
        return False, None, None

    async def check(
        self, request_id: str, target: TransportTarget, ctx: RouteContext
    ) -> Tuple[str, Optional[Message]]:
        """Poll the remote inbox for the status of a previous request.

        Returns:
            (status, response)

        Status values: 'completed', 'pending', 'not_found'.
        """
        base_url = (target.url or "").rstrip("/")
        path = target.inbox_path
        url = f"{base_url}{path}/{request_id}"
        cb_key = f"{base_url}{path}"

        headers = {
            "Accept": "application/json",
        }

        # Use a conservative timeout for rehydration checks to avoid blocking
        # the hub control flow. This reuses the configured read timeout but caps
        # the overall check to a small window.
        client = await self._get_client(base_url)
        # Skip promptly if the same target is marked down/open circuit
        if self._is_cb_open(cb_key) or self._is_marked_down(cb_key):
            return "pending", None
        try:
            # Choose a short conservative timeout for rehydration checks.
            # We reuse read_timeout but cap to 2 seconds to avoid long blocking.
            short_timeout = min(float(self._timeout.read or 2.0), 2.0)
            resp = await self._request_with_retries(
                client,
                method="GET",
                url=url,
                headers=headers,
                timeout_override=short_timeout,
            )
        except Exception:
            # Network error: treat as pending to avoid false negatives
            return "pending", None

        code = resp.status_code
        if code in (404, 410):
            return "not_found", None
        if code in (200,):
            try:
                data = InboxResponse.model_validate(resp.json())
            except Exception:
                # If we cannot parse, treat 200 without body as pending
                self._record_cb_success(cb_key)
                self._mark_up(cb_key)
                return "pending", None
            if data.status == "completed" and data.response:
                self._record_cb_success(cb_key)
                self._mark_up(cb_key)
                return "completed", Message.from_wire_dict(data.response)
            # accepted/pending/not_found from body
            if data.status == "not_found":
                return "not_found", None
            self._record_cb_success(cb_key)
            self._mark_up(cb_key)
            return "pending", None
        # Other 4xx: do not trip CB, remain pending
        if 400 <= code < 500:
            return "pending", None
        # 5xx or unexpected: trip CB briefly and return pending
        self._record_cb_failure(cb_key)
        self._mark_down(cb_key)
        return "pending", None

    async def _request_with_retries(
        self,
        client: httpx.AsyncClient,
        method: Literal["GET", "POST"],
        url: str,
        headers: dict[str, str],
        json: Mapping[str, object] | None = None,
        timeout_override: Optional[float] = None,
    ) -> httpx.Response:
        """Unified retry logic for HTTP requests with exponential backoff and jitter.

        Retries on transient/network errors and retryable status codes:
        {408, 425, 429, 500, 502, 503, 504}. Respects `Retry-After` when present.
        Returns the final response if retries are exhausted due to HTTP status.
        Raises the last exception for network-level failures with no response.
        """
        attempt = 0
        last_exc = None

        while attempt <= self._retries:
            try:
                # Per-request timeout override keeps rehydration checks conservative
                if method.upper() == "GET":
                    # Do not send any json/body on GET
                    if timeout_override is not None:
                        resp = await client.get(
                            url, headers=headers, timeout=timeout_override
                        )
                    else:
                        resp = await client.get(url, headers=headers)
                else:
                    if timeout_override is not None:
                        resp = await client.post(
                            url, headers=headers, json=json, timeout=timeout_override
                        )
                    else:
                        resp = await client.post(url, headers=headers, json=json)
                if resp.status_code in (408, 425, 429, 500, 502, 503, 504):
                    ra = resp.headers.get("Retry-After")
                    if ra:
                        try:
                            await asyncio.sleep(float(ra))
                        except Exception:
                            pass
                    raise httpx.HTTPStatusError(
                        "Transient", request=resp.request, response=resp
                    )
                return resp
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_exc = e
                if attempt == self._retries:
                    break
                backoff = self._backoff_factor * (2**attempt) + random.uniform(
                    0, self._jitter
                )
                await asyncio.sleep(backoff)
                attempt += 1
        if isinstance(last_exc, httpx.HTTPStatusError):
            return last_exc.response
        assert last_exc is not None
        raise last_exc

    def _is_cb_open(self, key: str) -> bool:
        state = self._cb_state.get(key)
        if not state:
            return False
        fail_count, open_until = state
        if open_until and time.time() < open_until:
            return True
        return False

    def _record_cb_failure(self, key: str) -> None:
        previous = self._cb_state.get(key, (0, 0))
        fail_count, open_until = previous
        fail_count += 1
        # Open circuit after 3 consecutive failures for 10s
        if fail_count >= 3 and not (open_until and time.time() < open_until):
            open_until = time.time() + 10
            logger.debug(
                "CB opened url=%s fail_count=%d open_for_s=%d",
                key,
                fail_count,
                10,
            )
        self._cb_state[key] = (fail_count, open_until)

    def _record_cb_success(self, key: str) -> None:
        if key in self._cb_state:
            prev_fail_count, prev_open_until = self._cb_state[key]
            if prev_fail_count or prev_open_until:
                logger.debug(
                    "CB closed url=%s prev_fail_count=%d", key, prev_fail_count
                )
            self._cb_state[key] = (0, 0)

    def _mark_down(self, key: str) -> None:
        # Mark as down for a short window to avoid repeated attempts
        until = time.time() + 5
        self._down_cache[key] = until
        logger.debug("Marked down url=%s until_ts=%d", key, int(until))

    def _mark_up(self, key: str) -> None:
        if key in self._down_cache:
            self._down_cache.pop(key, None)
            logger.debug("Marked up url=%s", key)

    def _is_marked_down(self, key: str) -> bool:
        until = self._down_cache.get(key)
        if not until:
            return False
        if time.time() < until:
            return True
        self._down_cache.pop(key, None)
        return False

    def _should_trip_cb(self, status_code: int) -> bool:
        """Return True if a status code should contribute to opening the circuit.

        Trip for server/unavailable conditions and timeouts; do not trip for ordinary 4xx.
        """
        if status_code in (408, 425, 429):
            return True
        if 500 <= status_code <= 599:
            return True
        return False

    async def _get_client(self, base_url: str) -> httpx.AsyncClient:
        key = base_url or "default"
        client = self._clients.get(key)
        if client is None:
            client = httpx.AsyncClient(verify=self._verify_ssl, timeout=self._timeout)
            self._clients[key] = client
        return client

    async def close(self) -> None:
        """Close and clear all pooled HTTP clients."""
        for key, client in list(self._clients.items()):
            try:
                await client.aclose()
            except Exception:
                pass
            self._clients.pop(key, None)
