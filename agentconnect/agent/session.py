"""Agent Session: join, pull work, map handler outcomes, reconnect.

A Session talks to a Runtime through a transport. Embedded Teams use
in-process calls. A URL uses HTTP POST plus an SSE work hint. Agent code
does not change between them.

``instance_id`` is generated once per running copy unless the caller
supplies a stable value. Re-joining with that same id replaces this
copy's Session. Two copies must not share an ``instance_id``.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Mapping, Optional

from agentconnect.agent.context import Context
from agentconnect.agent.errors import SessionError
from agentconnect.core.spec import SPEC_VERSION
from agentconnect.transport.agent_http import HttpRuntimeTransport
from agentconnect.transport.inprocess import InProcessTransport
from agentconnect.transport.runtime import TransportError

if TYPE_CHECKING:
    from agentconnect.agent.base import BaseAgent

logger = logging.getLogger(__name__)

_RETRY_JOIN_CODES = frozenset({"unavailable"})
_RECONNECT_CODES = frozenset({"unavailable", "unauthorized"})


def bind_transport(target: Any) -> Any:
    """Return an HTTP transport for a URL, or in-process for a Team object."""
    if isinstance(target, str):
        return HttpRuntimeTransport(target)
    return InProcessTransport(target)


def deadline_rfc3339(seconds: float) -> str:
    """Return a future UTC timestamp the Runtime will accept."""
    instant = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return instant.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class Session:
    """One running copy of an Agent connected to a Team."""

    def __init__(
        self,
        agent: "BaseAgent",
        target: Any,
        *,
        instance_id: str,
        agent_did: str,
        profile: Mapping[str, Any],
        max_in_flight: int,
    ) -> None:
        """Bind this copy to a Team object or a Runtime URL."""
        self._agent = agent
        self._target = target
        self.instance_id = instance_id
        self.agent_did = agent_did
        self._profile = dict(profile)
        self.max_in_flight = max_in_flight
        self._transport = bind_transport(target)
        self.session_token: Optional[str] = None
        self.address: Optional[str] = None
        self.team_name: Optional[str] = None
        self.limits: dict[str, int] = {}
        self.persistence: Optional[str] = None
        self.session_expires_at: Optional[str] = None
        self._connected = False
        self._stopped = False
        self._wake = asyncio.Event()
        self._supervisor: Optional[asyncio.Task] = None
        self._inflight: set[asyncio.Task] = set()
        self._sender_did_cache: dict[str, str] = {}
        self._reconnect_lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        """True while this copy holds a live Session token."""
        return self._connected and not self._stopped

    async def start(self) -> "Session":
        """Join (retrying until the Team is up) and start pull, heartbeat, and events."""
        await self._connect_with_retry()
        self._supervisor = asyncio.create_task(
            self._supervise(), name=f"session:{self.instance_id}"
        )
        return self

    async def close(self, *, disconnect: bool = True) -> None:
        """Stop the supervisor. Disconnect the Session when ``disconnect`` is True."""
        self._stopped = True
        self._connected = False
        self._wake.set()
        for task in list(self._inflight):
            task.cancel()
        if self._supervisor is not None:
            self._supervisor.cancel()
        pending = [task for task in self._inflight]
        if self._supervisor is not None:
            pending.append(self._supervisor)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._inflight.clear()
        self._supervisor = None
        token = self.session_token
        self.session_token = None
        if disconnect and token:
            try:
                await self._transport.disconnect(token)
            except TransportError:
                pass
        await self._transport.close()

    async def ask(
        self,
        recipient: str,
        content: Any,
        *,
        deadline_seconds: float = 30.0,
        collect: str = "wait",
        thread_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        message_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send a reply-expected request."""
        body: dict[str, Any] = {
            "id": message_id or str(uuid.uuid4()),
            "recipient": recipient,
            "kind": "request",
            "content": content,
            "collect": collect,
            "deadline": deadline_rfc3339(deadline_seconds),
        }
        if thread_id is not None:
            body["thread_id"] = thread_id
        if parent_id is not None:
            body["parent_id"] = parent_id
        if metadata is not None:
            body["metadata"] = dict(metadata)
        return await self._call("send", self._transport.send, self._token(), body)

    async def tell(
        self,
        recipient: str,
        content: Any,
        *,
        kind: str = "event",
        thread_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        message_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send an event or a no-reply request. No Ticket is created."""
        if kind not in {"event", "request"}:
            raise ValueError("tell kind must be event or request")
        body: dict[str, Any] = {
            "id": message_id or str(uuid.uuid4()),
            "recipient": recipient,
            "kind": kind,
            "content": content,
        }
        if thread_id is not None:
            body["thread_id"] = thread_id
        if parent_id is not None:
            body["parent_id"] = parent_id
        if metadata is not None:
            body["metadata"] = dict(metadata)
        return await self._call("send", self._transport.send, self._token(), body)

    async def find(
        self, query: str, *, limit: int = 10, detail: str = "summary"
    ) -> dict[str, Any]:
        """Search this Team's Directory."""
        return await self._call(
            "find",
            self._transport.find,
            self._token(),
            query,
            limit=limit,
            detail=detail,
        )

    async def get_profile(self, address: str) -> dict[str, Any]:
        """Return one Directory entry."""
        return await self._call(
            "get_profile", self._transport.get_profile, self._token(), address
        )

    async def get_result(self, ticket_id: str) -> dict[str, Any]:
        """Return the current Ticket owned by this Membership."""
        return await self._call(
            "get_result", self._transport.get_result, self._token(), ticket_id
        )

    async def get_history(
        self,
        thread_id: str,
        *,
        before: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return one page of retained Thread history."""
        return await self._call(
            "get_history",
            self._transport.get_history,
            self._token(),
            thread_id,
            before=before,
            limit=limit,
        )

    async def reply_delivery(
        self,
        delivery: Mapping[str, Any],
        *,
        outcome: str,
        content: Any = None,
        error: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Finish a leased reply-expected Delivery."""
        body: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "lease_id": delivery["lease_id"],
            "outcome": outcome,
        }
        if outcome == "completed":
            body["content"] = content
        else:
            body["error"] = dict(
                error or {"code": "handler_failed", "message": "failed"}
            )
        return await self._call("reply", self._transport.reply, self._token(), body)

    async def complete_delivery(self, delivery: Mapping[str, Any]) -> dict[str, Any]:
        """Finish a Delivery without a response Message."""
        return await self._call(
            "complete",
            self._transport.complete,
            self._token(),
            delivery["lease_id"],
        )

    def _token(self) -> str:
        token = self.session_token
        if not token:
            raise SessionError("unauthorized", "Agent is not connected to a Team")
        return token

    def _join_body(self) -> dict[str, Any]:
        return {
            "spec_version": SPEC_VERSION,
            "name": self._agent._agent_name,
            "agent_did": self.agent_did,
            "profile": dict(self._profile),
            "instance_id": self.instance_id,
            "max_in_flight": self.max_in_flight,
        }

    async def _connect_with_retry(self) -> None:
        delay = 0.05
        while not self._stopped:
            try:
                body = self._join_body()
                await self._attach_join_credentials(body)
                result = await self._transport.join(body)
                if self._stopped:
                    token = result.get("session_token")
                    if token:
                        try:
                            await self._transport.disconnect(token)
                        except TransportError:
                            pass
                    return
                self._apply_join(result)
                return
            except TransportError as exc:
                if exc.code in _RETRY_JOIN_CODES or exc.retryable:
                    logger.debug(
                        "join retry name=%s code=%s",
                        self._agent._agent_name,
                        exc.code,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 2.0)
                    continue
                raise SessionError.from_transport(exc) from exc

    async def _attach_join_credentials(self, body: dict[str, Any]) -> None:
        """Add join_token and identity_proof when this join is authenticated."""
        token = getattr(self._agent, "join_token", None)
        target_is_url = isinstance(self._target, str)
        require = bool(getattr(self._target, "require_join_auth", False))
        if not (target_is_url or token or require):
            return
        challenge_fn = getattr(self._transport, "join_challenge", None)
        if challenge_fn is None:
            return
        challenge = await challenge_fn()
        try:
            body["identity_proof"] = self._agent.prove_join(challenge)
        except ValueError as exc:
            raise SessionError(
                "unauthorized", "Join credentials are missing or invalid"
            ) from exc
        if token:
            body["join_token"] = token

    def _apply_join(self, result: Mapping[str, Any]) -> None:
        self.session_token = str(result["session_token"])
        self.address = str(result["address"])
        self.team_name = str(result["team_name"])
        self.instance_id = str(result.get("instance_id") or self.instance_id)
        self.limits = dict(result.get("limits") or {})
        self.persistence = result.get("persistence")
        self.session_expires_at = result.get("session_expires_at")
        self._connected = True
        self._wake.set()
        logger.info(
            "joined team=%s address=%s instance=%s",
            self.team_name,
            self.address,
            self.instance_id,
        )

    async def _supervise(self) -> None:
        heartbeat = asyncio.create_task(self._heartbeat_loop(), name="heartbeat")
        events = asyncio.create_task(self._events_loop(), name="events")
        pull = asyncio.create_task(self._pull_loop(), name="pull")
        try:
            await asyncio.gather(heartbeat, events, pull)
        except asyncio.CancelledError:
            raise
        finally:
            for task in (heartbeat, events, pull):
                task.cancel()
            await asyncio.gather(heartbeat, events, pull, return_exceptions=True)

    async def _heartbeat_loop(self) -> None:
        while not self._stopped:
            interval = self._heartbeat_interval()
            try:
                await asyncio.sleep(interval)
                if self._stopped or not self.session_token:
                    continue
                result = await self._transport.heartbeat(self.session_token)
                self.session_expires_at = result.get("session_expires_at")
            except asyncio.CancelledError:
                raise
            except TransportError as exc:
                if self._stopped:
                    return
                if exc.code in _RECONNECT_CODES or exc.retryable:
                    await self._reconnect()
                    continue
                logger.warning(
                    "heartbeat failed address=%s code=%s", self.address, exc.code
                )
            except Exception:
                if self._stopped:
                    return
                logger.debug("heartbeat error address=%s", self.address, exc_info=True)
                await self._reconnect()

    def _heartbeat_interval(self) -> float:
        expires = self.session_expires_at
        if not expires:
            return min(60.0, max(0.05, self._agent._session_ttl_hint / 3))
        try:
            instant = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            remaining = (instant - datetime.now(timezone.utc)).total_seconds()
            return min(60.0, max(0.05, remaining / 3))
        except ValueError:
            return 60.0

    async def _events_loop(self) -> None:
        while not self._stopped:
            token = self.session_token
            if not token:
                await asyncio.sleep(0.05)
                continue
            try:
                async for event in self._transport.events(token):
                    if self._stopped:
                        return
                    if not isinstance(event, dict):
                        continue
                    if event.get("type") == "work_available":
                        self._wake.set()
            except asyncio.CancelledError:
                raise
            except TransportError as exc:
                if self._stopped:
                    return
                if exc.code in _RECONNECT_CODES or exc.retryable:
                    await self._reconnect()
                    continue
                await asyncio.sleep(0.2)
            except Exception:
                if self._stopped:
                    return
                logger.debug(
                    "event stream error address=%s", self.address, exc_info=True
                )
                await asyncio.sleep(0.2)

    async def _pull_loop(self) -> None:
        while not self._stopped:
            if not self.session_token:
                await asyncio.sleep(0.05)
                continue
            room = max(0, self.max_in_flight - len(self._inflight))
            if room <= 0:
                if self._inflight:
                    await asyncio.wait(
                        self._inflight, return_when=asyncio.FIRST_COMPLETED
                    )
                else:
                    await asyncio.sleep(0.05)
                continue
            try:
                leased = await self._transport.lease(self.session_token, room)
            except TransportError as exc:
                if self._stopped:
                    return
                if exc.code in _RECONNECT_CODES or exc.retryable:
                    await self._reconnect()
                    continue
                logger.warning(
                    "lease failed address=%s code=%s", self.address, exc.code
                )
                await asyncio.sleep(0.2)
                continue
            deliveries = leased.get("deliveries") or []
            if not deliveries:
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
                self._wake.clear()
                continue
            for delivery in deliveries:
                task = asyncio.create_task(
                    self._handle(delivery), name=f"delivery:{delivery.get('lease_id')}"
                )
                self._inflight.add(task)
                task.add_done_callback(self._inflight.discard)

    async def _reconnect(self) -> None:
        if self._stopped:
            return
        async with self._reconnect_lock:
            if self._stopped:
                return
            if self.session_token and self._connected:
                try:
                    result = await self._transport.heartbeat(self.session_token)
                    self.session_expires_at = result.get("session_expires_at")
                    return
                except TransportError:
                    self._connected = False
            logger.info(
                "reconnecting address=%s instance=%s", self.address, self.instance_id
            )
            if isinstance(self._target, str):
                try:
                    await self._transport.close()
                except Exception:
                    pass
                self._transport = bind_transport(self._target)
            try:
                await self._connect_with_retry()
            except SessionError:
                logger.warning("reconnect failed address=%s", self.address)
                await asyncio.sleep(0.2)

    async def _handle(self, delivery: Mapping[str, Any]) -> None:
        message = dict(delivery.get("message") or {})
        ctx = await self._build_context(delivery)
        try:
            result = await _invoke_handler(self._agent, message, ctx)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception(
                "handler failed address=%s message_id=%s",
                self.address,
                message.get("id"),
            )
            await self._fail_or_complete(delivery, exc)
            return
        if ctx.ticket_taken:
            return
        await self._finish_handler(delivery, result)

    async def _build_context(self, delivery: Mapping[str, Any]) -> Context:
        message = delivery.get("message") or {}
        sender = str(message.get("sender") or "")
        sender_did = self._sender_did_cache.get(sender, "")
        if sender and sender not in self._sender_did_cache:
            try:
                entry = await self.get_profile(sender)
                sender_did = str(entry.get("agent_did") or "")
                self._sender_did_cache[sender] = sender_did
            except SessionError:
                sender_did = ""
        return Context(
            self,
            delivery,
            sender_did=sender_did,
            origin=self.team_name or "",
            external=False,
        )

    async def _finish_handler(self, delivery: Mapping[str, Any], result: Any) -> None:
        message = delivery.get("message") or {}
        reply_expected = message.get("kind") == "request" and message.get("deadline")
        content = _handler_content(result)
        try:
            if reply_expected:
                if content is _DECLINED:
                    await self.complete_delivery(delivery)
                else:
                    await self.reply_delivery(
                        delivery, outcome="completed", content=content
                    )
            else:
                await self.complete_delivery(delivery)
        except SessionError as exc:
            logger.warning(
                "finish delivery failed address=%s code=%s", self.address, exc.code
            )

    async def _fail_or_complete(
        self, delivery: Mapping[str, Any], exc: BaseException
    ) -> None:
        message = delivery.get("message") or {}
        reply_expected = message.get("kind") == "request" and message.get("deadline")
        safe = str(exc) or "handler failed"
        if len(safe) > 2000:
            safe = safe[:2000]
        try:
            if reply_expected:
                await self.reply_delivery(
                    delivery,
                    outcome="failed",
                    error={"code": "handler_failed", "message": safe},
                )
            else:
                await self.complete_delivery(delivery)
        except SessionError as finish_exc:
            logger.warning(
                "fail delivery failed address=%s code=%s",
                self.address,
                finish_exc.code,
            )

    async def _call(self, op: str, method, *args, **kwargs) -> dict[str, Any]:
        try:
            return await method(*args, **kwargs)
        except TransportError as exc:
            if exc.code in _RECONNECT_CODES or exc.retryable:
                await self._reconnect()
                if self.session_token:
                    try:
                        if op == "send":
                            return await self._transport.send(self._token(), args[-1])
                        return await method(self._token(), *args[1:], **kwargs)
                    except TransportError as retry_exc:
                        raise SessionError.from_transport(retry_exc) from retry_exc
            raise SessionError.from_transport(exc) from exc


_DECLINED = object()


def _handler_content(result: Any) -> Any:
    """Map a handler return value onto reply content, or _DECLINED."""
    if result is None:
        return _DECLINED
    content_attr = getattr(result, "content", None)
    kind_attr = getattr(result, "kind", None)
    if content_attr is not None and kind_attr is not None:
        return content_attr
    return result


async def _invoke_handler(
    agent: "BaseAgent", message: dict[str, Any], ctx: Context
) -> Any:
    method = agent.process_message
    if _accepts_ctx(method):
        return await method(message, ctx)
    return await method(message)


def _accepts_ctx(method: Any) -> bool:
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return True
    params = [
        param
        for param in signature.parameters.values()
        if param.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.KEYWORD_ONLY,
        )
        and param.name != "self"
    ]
    if any(param.kind == inspect.Parameter.VAR_POSITIONAL for param in params):
        return True
    names = [param.name for param in params]
    return "ctx" in names or len(params) >= 2
