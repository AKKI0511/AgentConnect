from __future__ import annotations

import logging
import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, TYPE_CHECKING, Optional, Protocol, Tuple
from collections.abc import AsyncIterator
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

if TYPE_CHECKING:
    from agentconnect.index.registry.registration import AgentRegistration

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from agentconnect.config.servers import InboxServerSettings
from agentconnect.transport.schemas import InboxResponse
from agentconnect.transport.envelope import CollaborationMessage as Message


class _RegistrationLookup(Protocol):
    async def get_registration(self, agent_id: str) -> AgentRegistration | None: ...


class _ResponseTracker(Protocol):
    async def check(self, request_id: str) -> tuple[str, Message | None]: ...


class _InboxHub(Protocol):
    @property
    def registry(self) -> _RegistrationLookup: ...

    @property
    def response_tracker(self) -> _ResponseTracker: ...

    async def ingest_remote_message(self, message: Message) -> object: ...


logger = logging.getLogger("uvicorn.error.agentconnect.inbox")


class _BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        """Reject request bodies larger than ``max_body_bytes``."""
        super().__init__(app)
        self._max = max_body_bytes

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Rely on content-length header when present; otherwise stream and reject if exceeded
        try:
            cl = request.headers.get("content-length")
            if cl is not None and int(cl) > self._max:
                return JSONResponse(
                    {"detail": "Request body too large"}, status_code=413
                )
        except Exception:
            pass
        # For safety, read the body here with limit and then replace scope body for downstream
        body = await request.body()
        if len(body) > self._max:
            return JSONResponse({"detail": "Request body too large"}, status_code=413)
        # Recreate request with the already-read body available to downstream
        request._body = body  # FastAPI caches .body()
        return await call_next(request)


class _TokenBucket:
    def __init__(self, rate_per_sec: float, burst: int) -> None:
        """Create a token-bucket limiter with the given rate and burst."""
        self._rate = float(rate_per_sec)
        self._burst = int(max(1, burst))
        self._tokens = float(self._burst)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def allow(self) -> Tuple[bool, float]:
        async with self._lock:
            now = time.monotonic()
            elapsed = max(0.0, now - self._last)
            self._last = now
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True, 0.0
            # Compute wait time until next token
            deficit = 1.0 - self._tokens
            wait_s = deficit / self._rate if self._rate > 0 else 1.0
            return False, max(0.0, wait_s)


def create_agent_inbox_app(
    hub: _InboxHub, settings: Optional[InboxServerSettings] = None
) -> FastAPI:
    """Create a FastAPI inbox app for receiving collaboration requests.

    Endpoints:
      - POST `/agentconnect/collaboration`
      - GET  `/agentconnect/collaboration/{request_id}`
    """
    cfg = settings or InboxServerSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Initialize shared state
        app.state.settings = cfg
        app.state.global_bucket = _TokenBucket(
            cfg.global_rate_per_sec, cfg.global_burst
        )
        app.state.sender_buckets = {}
        app.state.seen_ids = {}
        app.state.idem_cache = {}
        app.state.cache_lock = asyncio.Lock()

        async def _cleanup_loop() -> None:
            try:
                interval = max(1.0, float(cfg.replay_ttl_seconds) / 3.0)
                while True:
                    await asyncio.sleep(interval)
                    now = time.time()
                    # Cleanup replay cache and idempotency cache
                    async with app.state.cache_lock:
                        for mid, exp in list(app.state.seen_ids.items()):
                            if now >= exp:
                                app.state.seen_ids.pop(mid, None)
                        for key, (_, exp) in list(app.state.idem_cache.items()):
                            if now >= exp:
                                app.state.idem_cache.pop(key, None)
            except asyncio.CancelledError:
                return

        app.state._cleanup_task = asyncio.create_task(_cleanup_loop())
        try:
            yield
        finally:
            try:
                app.state._cleanup_task.cancel()
                await app.state._cleanup_task
            except Exception:
                pass

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(_BodySizeLimitMiddleware, max_body_bytes=cfg.max_body_bytes)

    def _authz(token_header_value: str | None, cfg: InboxServerSettings) -> None:
        # When auth is not required, allow anonymous regardless of whether a token is configured
        if not cfg.require_auth:
            return
        expected_env = cfg.bearer_token_env_var or "AGENTCONNECT_INBOX_BEARER_TOKEN"
        expected = os.getenv(expected_env)
        # Strict mode: require configured token and matching header
        if not expected:
            logger.debug(
                "Inbox auth failed: require_auth enabled but no expected token configured"
            )
            raise HTTPException(
                status_code=401,
                detail="Unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )
        hv = token_header_value or ""
        if hv.lower().startswith("bearer "):
            hv = hv[7:].strip()
        if hv != expected:
            logger.debug("Inbox auth failed: bearer token mismatch (policy)")
            raise HTTPException(status_code=401, detail="Unauthorized")

    def _validate_uuid4(value: str) -> bool:
        try:
            parsed = uuid.UUID(value, version=4)
            return str(parsed) == value
        except Exception:
            return False

    @app.post(cfg.path)
    async def post_collaboration(
        request: Request,
        authorization: str | None = Header(default=None, alias=cfg.auth_header_name),
        idem_key: str | None = Header(default=None, alias=cfg.idempotency_header_name),
    ) -> JSONResponse:
        now = time.time()
        try:
            _authz(authorization, cfg)
        except HTTPException:
            logger.debug("Inbox POST unauthorized by auth policy")
            raise

        if cfg.require_idempotency_header and not idem_key:
            raise HTTPException(status_code=400, detail="Missing idempotency header")

        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        # Construct Message from wire
        try:
            envelope = payload.get("envelope") if isinstance(payload, dict) else None
            wire = envelope if isinstance(envelope, dict) else payload
            message = Message.from_wire_dict(wire)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid message envelope")

        # Allowed senders whitelist
        if cfg.allowed_senders:
            if message.sender_id not in cfg.allowed_senders:
                raise HTTPException(status_code=403, detail="Sender not allowed")

        # Limits: metadata size and content length
        if message.metadata is not None:
            import json as _json

            meta_bytes = len(
                _json.dumps(
                    message.metadata, sort_keys=True, separators=(",", ":")
                ).encode()
            )
            if meta_bytes > cfg.max_metadata_bytes:
                raise HTTPException(status_code=400, detail="Metadata too large")
        if (
            message.content is not None
            and len(message.content) > cfg.max_content_length
        ):
            raise HTTPException(status_code=400, detail="Content too long")

        # Rate limits (global + per-sender)
        allowed, wait = await request.app.state.global_bucket.allow()
        if not allowed:
            resp = JSONResponse({"detail": "Rate limited"}, status_code=429)
            resp.headers["Retry-After"] = str(int(max(1.0, wait)))
            return resp
        if message.sender_id:
            sender_buckets: Dict[str, _TokenBucket] = request.app.state.sender_buckets
            bucket = sender_buckets.get(message.sender_id)
            if bucket is None:
                bucket = _TokenBucket(cfg.per_sender_rate_per_sec, cfg.per_sender_burst)
                sender_buckets[message.sender_id] = bucket
            allowed2, wait2 = await bucket.allow()
            if not allowed2:
                resp = JSONResponse({"detail": "Rate limited"}, status_code=429)
                resp.headers["Retry-After"] = str(int(max(1.0, wait2)))
                return resp

        # Sanitize spoofed verified_by and enforce presence of request_id
        if message.metadata is None:
            message.metadata = {}
        message.metadata.pop("verified_by", None)
        req_id = message.metadata.get("request_id")
        if req_id is None:
            raise HTTPException(status_code=400, detail="Missing request_id")
        if not isinstance(req_id, str) or not _validate_uuid4(req_id):
            raise HTTPException(status_code=400, detail="Invalid request_id")

        # Enforce allowable clock skew based on timestamp
        try:
            ts = message.timestamp.timestamp()
            if abs(time.time() - ts) > cfg.clock_skew_seconds:
                raise HTTPException(
                    status_code=400, detail="Timestamp outside allowed skew window"
                )
        except HTTPException:
            raise
        except Exception:
            pass

        # Verify signature via registry using hub.ingest_remote_message flow
        # First do a quick verify attempt similar to hub.ingest_remote_message to fail fast
        try:
            reg = await hub.registry.get_registration(message.sender_id)
            if not reg or not reg.identity.verify_signature(
                message._get_signable_content(), message.signature or ""
            ):
                raise HTTPException(status_code=400, detail="Invalid signature")
        except HTTPException:
            raise
        except Exception:
            logger.error(
                "Signature verification error sender=%s receiver=%s request_id=%s",
                message.sender_id,
                message.receiver_id,
                req_id,
                exc_info=True,
            )
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Idempotency cache semantics:
        # - If key seen with a different request_id -> 409 conflict
        # - If key seen with same request_id and we stored a completed response -> return it deterministically
        # - Otherwise, store (request_id, expiry); on completion we also store the response for deterministic retries
        if cfg.require_idempotency_header and idem_key:
            async with request.app.state.cache_lock:
                idem_cache: Dict[str, Tuple[str | dict[str, object] | None, float]] = (
                    request.app.state.idem_cache
                )
                stored = idem_cache.get(idem_key)
                if stored is not None:
                    stored_val, _exp = stored
                    # stored_val may be a str (req_id) or a dict (completed response envelope)
                    if isinstance(stored_val, dict):
                        # Completed response cached; verify request_id matches
                        cached_req = stored_val.get("request_id")
                        if cached_req is None or cached_req != req_id:
                            raise HTTPException(
                                status_code=409, detail="Idempotency conflict"
                            )
                        # Deterministic replay response
                        logger.info(
                            "Inbox completed (replay) sender=%s receiver=%s request_id=%s",
                            message.sender_id,
                            message.receiver_id,
                            req_id,
                        )
                        return JSONResponse(stored_val, status_code=200)
                    else:
                        # Only request_id present; ensure it matches
                        stored_req = stored_val
                        if stored_req != req_id:
                            raise HTTPException(
                                status_code=409, detail="Idempotency conflict"
                            )
                else:
                    idem_cache[idem_key] = (req_id, now + float(cfg.replay_ttl_seconds))

        # Replay protection (by message.id) — applied after idempotency replay handling
        seen_ids: Dict[str, float] = request.app.state.seen_ids
        async with request.app.state.cache_lock:
            if message.id in seen_ids:
                raise HTTPException(status_code=409, detail="Duplicate message id")
            # Mark replay seen
            seen_ids[message.id] = now + float(cfg.replay_ttl_seconds)

        # Delegate to hub for ingestion and local delivery
        # hub will set verified_by='hub'
        await hub.ingest_remote_message(message)

        # Check tracker once for immediate completion
        status, response_msg = await hub.response_tracker.check(req_id)
        if status == "completed" and response_msg is not None:
            logger.info(
                "Inbox completed sender=%s receiver=%s request_id=%s",
                message.sender_id,
                message.receiver_id,
                req_id,
            )
            envelope_response = InboxResponse(
                status="completed",
                response=response_msg.to_wire_dict(),
                request_id=req_id,
            )
            # Store completed response in idempotency cache for deterministic replays
            if cfg.require_idempotency_header and idem_key:
                try:
                    async with request.app.state.cache_lock:
                        idem_cache = request.app.state.idem_cache
                        idem_cache[idem_key] = (
                            envelope_response.model_dump(),
                            now + float(cfg.replay_ttl_seconds),
                        )
                except Exception:
                    pass
            return JSONResponse(envelope_response.model_dump(), status_code=200)
        else:
            logger.info(
                "Inbox accepted sender=%s receiver=%s request_id=%s",
                message.sender_id,
                message.receiver_id,
                req_id,
            )
            envelope_response = InboxResponse(status="accepted", request_id=req_id)
            return JSONResponse(envelope_response.model_dump(), status_code=202)

    @app.get(f"{cfg.path}/{{request_id}}")
    async def get_status(
        request_id: str,
        request: Request,
        authorization: str | None = Header(default=None, alias=cfg.auth_header_name),
    ) -> JSONResponse:
        # Auth policy mirrors POST
        try:
            _authz(authorization, cfg)
        except HTTPException:
            logger.debug("Inbox GET unauthorized by auth policy")
            raise
        # Simple global rate limiting for polling too (use global bucket only)
        allowed, wait = await request.app.state.global_bucket.allow()
        if not allowed:
            resp = JSONResponse({"detail": "Rate limited"}, status_code=429)
            resp.headers["Retry-After"] = str(int(max(1.0, wait)))
            return resp

        status, response_msg = await hub.response_tracker.check(request_id)
        if status == "completed" and response_msg is not None:
            logger.info("Inbox poll completed request_id=%s", request_id)
            return JSONResponse(
                InboxResponse(
                    status="completed", response=response_msg.to_wire_dict()
                ).model_dump(),
                status_code=200,
            )
        if status == "pending":
            logger.debug("Inbox poll pending request_id=%s", request_id)
            return JSONResponse(
                InboxResponse(status="pending").model_dump(), status_code=200
            )
        logger.debug("Inbox poll not_found request_id=%s", request_id)
        return JSONResponse(
            InboxResponse(status="not_found").model_dump(), status_code=404
        )

    return app
