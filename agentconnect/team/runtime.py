"""Team Runtime: mailboxes, tickets, threads, and routing.

A Team is a running process that serves one named Team. Agents stay in
their own processes and pull work through Runtime operations. This module
never holds Agent objects and never calls a method on an Agent.

Start a Team, join as a member, then ``send``, ``lease``, ``complete``,
and ``reply``:

    team = await Team("content-squad").start()
    writer = await team.join(
        name="writer",
        agent_did="did:key:z6MkmEtU9Z7p7G6vbULDgMk8DXCVqW8rNyLMtd2RrAHjLD3m",
        profile={
            "summary": "Writes short drafts from notes.",
            "skills": [
                {
                    "name": "drafting",
                    "description": "Turn research notes into a two-paragraph draft.",
                }
            ],
        },
    )

Pass ``store="memory"`` (the default) for a process-local Team. Pass a
Redis URL when Memberships, mailboxes, open Tickets, and Thread history
must survive a Runtime restart.

Open Tickets are retained until at least their deadline. Terminal Tickets
are kept for 24 hours after they close, or until that deadline if it is
later. Thread history is trimmed by count once no open Ticket still
needs an older Message.
"""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
from datetime import timedelta
from typing import Any, Mapping, NoReturn, Optional, Union

from agentconnect.core.address import (
    ADDRESS_OUTSIDE_TEAM,
    INVALID_ADDRESS,
    parse_agent_name,
    parse_team_name,
    resolve_address,
)
from agentconnect.core.profile import validate_discovery_profile
import agentconnect.team.mailbox as mailbox_mod
import agentconnect.team.tickets as tickets_mod
import agentconnect.team.threads as threads_mod
from agentconnect.team.codec import (
    canonical_json,
    format_timestamp,
    json_size,
    new_uuid,
    parse_timestamp,
    require_did,
    require_uuid,
    semantic_hash,
    utc_now,
)
from agentconnect.core.spec import SPEC_VERSION
from agentconnect.team.constants import (
    COLLECT_IMPLEMENTED,
    COLLECT_NAMED,
    DEFAULT_DELIVERY_HISTORY_LIMIT,
    DEFAULT_LEASE_TTL_SECONDS,
    DEFAULT_MAX_IN_FLIGHT,
    DEFAULT_MAX_INSTANCES,
    DEFAULT_MAX_MAILBOX_DEPTH,
    DEFAULT_MAX_MESSAGE_BYTES,
    DEFAULT_SESSION_TTL_SECONDS,
    DEFAULT_TERMINAL_TICKET_RETENTION_SECONDS,
    DEFAULT_THREAD_MESSAGE_LIMIT,
    MESSAGE_KINDS_SEND,
    SWEEP_INTERVAL_SECONDS,
)
from agentconnect.team.errors import TeamError
from agentconnect.team.store.base import Store
from agentconnect.team.store.memory import MemoryStore
from agentconnect.team.store.redis import RedisStore

logger = logging.getLogger(__name__)

_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
StoreArg = Union[Store, str, None]


def _fail(code: str, message: str, **kwargs: Any) -> NoReturn:
    raise TeamError(code, message, **kwargs)


class Team:
    """Runtime serving one Team.

    The Team owns Memberships, Sessions, Mailboxes, Deliveries, Tickets,
    and Thread history. Use :meth:`join` to create or reconnect a
    Membership, then pass the returned ``session_token`` to every other
    operation.
    """

    def __init__(
        self,
        name: str,
        *,
        store: StoreArg = None,
        max_message_bytes: int = DEFAULT_MAX_MESSAGE_BYTES,
        max_mailbox_depth: int = DEFAULT_MAX_MAILBOX_DEPTH,
        delivery_history_limit: int = DEFAULT_DELIVERY_HISTORY_LIMIT,
        session_ttl_seconds: float = DEFAULT_SESSION_TTL_SECONDS,
        lease_ttl_seconds: float = DEFAULT_LEASE_TTL_SECONDS,
        terminal_ticket_retention_seconds: float = DEFAULT_TERMINAL_TICKET_RETENTION_SECONDS,
        thread_message_limit: int = DEFAULT_THREAD_MESSAGE_LIMIT,
        max_instances: int = DEFAULT_MAX_INSTANCES,
        sweep_interval_seconds: float = SWEEP_INTERVAL_SECONDS,
    ) -> None:
        """Create an unstarted Runtime for Team ``name``."""
        team_name = parse_team_name(name)
        if team_name is None:
            raise ValueError("name is not a valid Team name")
        self.name = team_name
        self._store_arg = store
        self._store: Optional[Store] = None
        self.max_message_bytes = int(max_message_bytes)
        self.max_mailbox_depth = int(max_mailbox_depth)
        self.delivery_history_limit = int(delivery_history_limit)
        self.session_ttl_seconds = float(session_ttl_seconds)
        self.lease_ttl_seconds = float(lease_ttl_seconds)
        self.terminal_ticket_retention_seconds = float(
            terminal_ticket_retention_seconds
        )
        self.thread_message_limit = int(thread_message_limit)
        self.max_instances = int(max_instances)
        self.sweep_interval_seconds = float(sweep_interval_seconds)
        self._lock = asyncio.Lock()
        self._waiters: dict[str, list[asyncio.Event]] = {}
        self._work_waiters: dict[str, list[asyncio.Event]] = {}
        self._sse_subscribers: dict[str, list[asyncio.Queue]] = {}
        self._session_tokens_by_member: dict[str, set[str]] = {}
        self._sweep_task: Optional[asyncio.Task] = None
        self._http_server: Any = None
        self._http_task: Optional[asyncio.Task] = None
        self._http_url: Optional[str] = None
        self._http_port: Optional[int] = None
        self._started = False
        self._last_now = None

    @property
    def persistence(self) -> str:
        """``volatile`` for memory, ``durable`` for Redis."""
        if self._store is None:
            return "volatile" if not self._is_redis_arg(self._store_arg) else "durable"
        return self._store.persistence

    @property
    def limits(self) -> dict[str, int]:
        """Runtime limits reported on ``join``."""
        return {
            "max_message_bytes": self.max_message_bytes,
            "max_mailbox_depth": self.max_mailbox_depth,
            "delivery_history_limit": self.delivery_history_limit,
        }

    async def start(self) -> "Team":
        """Open the store and start background expiry. Returns this Team."""
        if self._started:
            return self
        self._store = self._build_store()
        await self._store.open()
        self._started = True
        loop = asyncio.get_running_loop()
        self._sweep_task = loop.create_task(self._sweep_loop())
        return self

    @property
    def url(self) -> Optional[str]:
        """HTTP origin this Runtime is serving, or None when not serving."""
        return self._http_url

    async def stop(self) -> None:
        """Stop HTTP serving, background expiry, and the store connection."""
        await self.stop_serving()
        self._started = False
        if self._sweep_task is not None:
            self._sweep_task.cancel()
            try:
                await self._sweep_task
            except asyncio.CancelledError:
                pass
            self._sweep_task = None
        if self._store is not None:
            await self._store.close()

    async def __aenter__(self) -> "Team":
        """Start the Runtime for use as an async context manager."""
        return await self.start()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Stop the Runtime when leaving the context manager."""
        await self.stop()

    def _signal_work(self, membership_name: str) -> None:
        """Hint waiting Clients that the Membership Mailbox has work."""
        for event in list(self._work_waiters.get(membership_name) or ()):
            event.set()
        for token in list(self._session_tokens_by_member.get(membership_name) or ()):
            for queue in list(self._sse_subscribers.get(token) or ()):
                try:
                    queue.put_nowait({"type": "work_available", "data": {}})
                except asyncio.QueueFull:
                    pass

    async def wait_for_work(self, session_token: str, timeout: float = 30.0) -> bool:
        """Block until this Session's Mailbox has leaseable work, or timeout.

        This is an in-process hint, not a Runtime operation. HTTP Clients
        use the SSE stream instead. Returns True when work looks available.
        """
        event = asyncio.Event()
        name = ""
        async with self._lock:
            session = await self._require_session(session_token)
            name = session["membership_name"]
            self._work_waiters.setdefault(name, []).append(event)
            store = self._ensure_started()
            items = await mailbox_mod.load_mailbox(store, session["address"])
            if mailbox_mod.has_available_item(items, utc_now()):
                event.set()
        try:
            await asyncio.wait_for(event.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            waiters = self._work_waiters.get(name)
            if waiters is not None:
                try:
                    waiters.remove(event)
                except ValueError:
                    pass
                if not waiters:
                    self._work_waiters.pop(name, None)

    async def subscribe_events(self, session_token: str) -> asyncio.Queue:
        """Attach an SSE queue to this Session. The caller must unsubscribe."""
        async with self._lock:
            await self._require_session(session_token)
            queue: asyncio.Queue = asyncio.Queue(maxsize=32)
            self._sse_subscribers.setdefault(session_token, []).append(queue)
            return queue

    async def unsubscribe_events(
        self, session_token: str, queue: asyncio.Queue
    ) -> None:
        """Detach an SSE queue previously returned by ``subscribe_events``."""
        queues = self._sse_subscribers.get(session_token)
        if queues is None:
            return
        try:
            queues.remove(queue)
        except ValueError:
            pass
        if not queues:
            self._sse_subscribers.pop(session_token, None)

    async def join_challenge(self) -> dict[str, Any]:
        """Return a short-lived join challenge. Verification lands in identity work."""
        self._ensure_started()
        expires = utc_now() + timedelta(minutes=5)
        return {
            "nonce": secrets.token_urlsafe(24),
            "audience": f"agentconnect:{self.name}",
            "expires_at": format_timestamp(expires),
        }

    async def serve(self, host: str = "127.0.0.1", port: int = 0) -> str:
        """Serve Runtime operations over HTTP on a loopback address.

        Returns the origin agents pass to ``BaseAgent.join``, for example
        ``http://127.0.0.1:9000``. Non-loopback hosts are rejected; a
        network Runtime that accepts remote joins is later work.
        """
        self._ensure_started()
        if self._http_task is not None and not self._http_task.done():
            if self._http_url is None:
                raise TeamError("internal", "HTTP serving is starting")
            return self._http_url
        if not _is_loopback(host):
            _fail(
                "invalid_request",
                "Team.serve binds loopback only",
            )
        from agentconnect.team.http import create_runtime_app
        import uvicorn

        app = create_runtime_app(self)
        config = uvicorn.Config(
            app,
            host=host,
            port=int(port),
            log_level="warning",
            lifespan="off",
        )
        server = uvicorn.Server(config)
        server.install_signal_handlers = False
        self._http_server = server
        loop = asyncio.get_running_loop()
        self._http_task = loop.create_task(server.serve())
        waited = 0.0
        while not server.started:
            if self._http_task.done():
                exc = self._http_task.exception()
                self._http_task = None
                self._http_server = None
                if exc is not None:
                    raise TeamError("unavailable", f"HTTP serving failed: {exc}")
                raise TeamError("unavailable", "HTTP serving failed to start")
            await asyncio.sleep(0.01)
            waited += 0.01
            if waited > 5.0:
                await self.stop_serving()
                raise TeamError("unavailable", "HTTP serving timed out on start")
        bound_host, bound_port = _bound_socket(server)
        display_host = "127.0.0.1" if bound_host in {"0.0.0.0", "::"} else bound_host
        self._http_port = bound_port
        self._http_url = f"http://{display_host}:{bound_port}"
        return self._http_url

    async def stop_serving(self) -> None:
        """Stop the HTTP listener if one is running."""
        server = self._http_server
        task = self._http_task
        self._http_server = None
        self._http_task = None
        self._http_url = None
        self._http_port = None
        if server is not None:
            server.should_exit = True
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    def _ensure_started(self) -> Store:
        if not self._started or self._store is None:
            raise TeamError("unavailable", "Team has not been started")
        return self._store

    @staticmethod
    def _is_redis_arg(store: StoreArg) -> bool:
        if isinstance(store, RedisStore):
            return True
        return isinstance(store, str) and store.startswith("redis")

    def _build_store(self) -> Store:
        store = self._store_arg
        if store is None or store == "memory":
            return MemoryStore()
        if isinstance(store, Store):
            return store
        if isinstance(store, str) and store.startswith("redis"):
            return RedisStore(store, prefix=f"ac:{self.name}")
        raise ValueError("store must be 'memory', a Redis URL, or a Store")

    def _now_pair(self):
        now = utc_now()
        if self._last_now is not None and now <= self._last_now:
            now = self._last_now + timedelta(microseconds=1)
        self._last_now = now
        return now, format_timestamp(now)

    def _notify(self, ticket_id: str) -> None:
        for event in self._waiters.get(ticket_id, []):
            event.set()

    def _register_waiter(self, ticket_id: str) -> asyncio.Event:
        event = asyncio.Event()
        self._waiters.setdefault(ticket_id, []).append(event)
        return event

    def _drop_waiter(self, ticket_id: str, event: asyncio.Event) -> None:
        waiters = self._waiters.get(ticket_id)
        if waiters is None:
            return
        try:
            waiters.remove(event)
        except ValueError:
            pass
        if not waiters:
            self._waiters.pop(ticket_id, None)

    # --- sessions and memberships ---

    async def _get_member(self, name: str) -> Optional[dict[str, Any]]:
        store = self._ensure_started()
        return await store.get(f"member:{name}")

    async def _get_member_by_did(self, agent_did: str) -> Optional[dict[str, Any]]:
        store = self._ensure_started()
        name = await store.get(f"did:{agent_did}")
        if not isinstance(name, str):
            return None
        return await self._get_member(name)

    async def _save_member(self, member: dict[str, Any]) -> None:
        store = self._ensure_started()
        await store.put(f"member:{member['name']}", member)
        await store.put(f"did:{member['agent_did']}", member["name"])
        await store.set_add("members", member["name"])

    async def _get_session(self, token: str) -> Optional[dict[str, Any]]:
        store = self._ensure_started()
        record = await store.get(f"session:{token}")
        if record is None:
            return None
        return record

    async def _save_session(self, session: dict[str, Any]) -> None:
        store = self._ensure_started()
        await store.put(f"session:{session['token']}", session)
        await store.set_add("sessions", session["token"])
        await store.put(
            f"instance:{session['membership_name']}:{session['instance_id']}",
            session["token"],
        )
        self._session_tokens_by_member.setdefault(
            session["membership_name"], set()
        ).add(session["token"])

    async def _delete_session(self, session: dict[str, Any]) -> None:
        store = self._ensure_started()
        await store.delete(f"session:{session['token']}")
        await store.set_remove("sessions", session["token"])
        await store.delete(
            f"instance:{session['membership_name']}:{session['instance_id']}"
        )
        tokens = self._session_tokens_by_member.get(session["membership_name"])
        if tokens is not None:
            tokens.discard(session["token"])
            if not tokens:
                self._session_tokens_by_member.pop(session["membership_name"], None)
        for queue in self._sse_subscribers.pop(session["token"], []):
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

    async def _require_session(self, session_token: Optional[str]) -> dict[str, Any]:
        if not session_token or not isinstance(session_token, str):
            _fail("unauthorized", "Session is missing or invalid")
        session = await self._get_session(session_token)
        if session is None:
            _fail("unauthorized", "Session is missing or invalid")
        now = utc_now()
        if parse_timestamp(session["expires_at"]) <= now:
            _fail("unauthorized", "Session is missing or invalid")
        return session

    async def _session_count(self, membership_name: str) -> int:
        store = self._ensure_started()
        tokens = await store.set_members("sessions")
        count = 0
        for token in tokens:
            session = await self._get_session(token)
            if session and session["membership_name"] == membership_name:
                count += 1
        return count

    async def _release_session_leases(
        self, session: dict[str, Any], now_ts: str
    ) -> None:
        store = self._ensure_started()
        for lease_id in list(session.get("lease_ids") or []):
            lease = await mailbox_mod.get_lease(store, lease_id)
            if lease is None:
                continue
            items = await mailbox_mod.load_mailbox(store, lease["address"])
            item = mailbox_mod.find_item(items, lease["message_id"])
            if item is not None and item.get("lease_id") == lease_id:
                mailbox_mod.release_lease_on_item(item, now_ts)
                await mailbox_mod.save_mailbox(store, lease["address"], items)
            await mailbox_mod.deactivate_lease(store, lease_id)
        session["lease_ids"] = []
        self._signal_work(session["membership_name"])

    def _join_result(
        self, session: dict[str, Any], member: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "session_token": session["token"],
            "session_expires_at": session["expires_at"],
            "address": member["address"],
            "team_name": self.name,
            "agent_did": member["agent_did"],
            "instance_id": session["instance_id"],
            "persistence": self.persistence,
            "limits": self.limits,
            "spec_version": SPEC_VERSION,
        }

    async def join(
        self,
        name: str | None = None,
        agent_did: str | None = None,
        profile: Mapping[str, Any] | None = None,
        *,
        spec_version: str = SPEC_VERSION,
        instance_id: str | None = None,
        max_in_flight: int = DEFAULT_MAX_IN_FLIGHT,
        join_token: str | None = None,
        identity_proof: str | None = None,
        request: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create or reconnect a Membership and open a Session.

        Embedded Teams accept joins without credentials. ``name`` is
        canonicalized to lowercase. A name and DID that already belong
        together reconnect; any other clash fails with ``name_conflict``.
        """
        del join_token, identity_proof
        if request is not None:
            name = request.get("name", name)
            agent_did = request.get("agent_did", agent_did)
            profile = request.get("profile", profile)
            spec_version = request.get("spec_version", spec_version)
            instance_id = request.get("instance_id", instance_id)
            if "max_in_flight" in request:
                max_in_flight = request["max_in_flight"]
        async with self._lock:
            return await self._join_locked(
                name=name,
                agent_did=agent_did,
                profile=profile,
                spec_version=spec_version,
                instance_id=instance_id,
                max_in_flight=max_in_flight,
            )

    async def _join_locked(
        self,
        *,
        name: str | None,
        agent_did: str | None,
        profile: Mapping[str, Any] | None,
        spec_version: str,
        instance_id: str | None,
        max_in_flight: int,
    ) -> dict[str, Any]:
        self._ensure_started()
        if spec_version != SPEC_VERSION:
            _fail("unsupported_version", "Client and Runtime contract drafts differ")
        canonical_name = parse_agent_name(name or "")
        if canonical_name is None:
            _fail("invalid_request", "Agent name is invalid")
        try:
            did = require_did(agent_did)
        except ValueError:
            _fail("invalid_request", "agent_did must be a did:key identifier")
        try:
            canonical_profile = validate_discovery_profile(profile or {})
        except ValueError as exc:
            _fail("invalid_request", str(exc))
        if instance_id is not None:
            try:
                instance_id = require_uuid(instance_id, field="instance_id")
            except ValueError:
                _fail("invalid_request", "instance_id must be a UUID")
        else:
            instance_id = new_uuid()
        try:
            in_flight = int(max_in_flight)
        except (TypeError, ValueError):
            _fail("invalid_request", "max_in_flight must be an integer")
        if in_flight < 1 or in_flight > 100:
            _fail("invalid_request", "max_in_flight must be between 1 and 100")

        by_name = await self._get_member(canonical_name)
        by_did = await self._get_member_by_did(did)
        if by_name is None and by_did is None:
            member = {
                "name": canonical_name,
                "address": f"{canonical_name}@{self.name}",
                "agent_did": did,
                "profile": canonical_profile,
            }
            await self._save_member(member)
        elif (
            by_name is not None
            and by_did is not None
            and by_name["name"] == by_did["name"]
            and by_name["agent_did"] == did
        ):
            member = dict(by_name)
            member["profile"] = canonical_profile
            await self._save_member(member)
        else:
            _fail(
                "name_conflict",
                "Agent name and DID do not identify the same Membership",
            )

        store = self._ensure_started()
        existing_token = await store.get(f"instance:{member['name']}:{instance_id}")
        now, now_ts = self._now_pair()
        if isinstance(existing_token, str):
            old = await self._get_session(existing_token)
            if old is not None:
                await self._release_session_leases(old, now_ts)
                await self._delete_session(old)
        elif await self._session_count(member["name"]) >= self.max_instances:
            _fail("busy", "No more Instances may join this Membership")

        expires = now + timedelta(seconds=self.session_ttl_seconds)
        session = {
            "token": secrets.token_urlsafe(32),
            "membership_name": member["name"],
            "address": member["address"],
            "agent_did": member["agent_did"],
            "instance_id": instance_id,
            "max_in_flight": in_flight,
            "expires_at": format_timestamp(expires),
            "lease_ids": [],
        }
        await self._save_session(session)
        return self._join_result(session, member)

    async def disconnect(self, session_token: str) -> None:
        """Close this Session. The Membership and its Mailbox remain."""
        async with self._lock:
            session = await self._require_session(session_token)
            _, now_ts = self._now_pair()
            await self._release_session_leases(session, now_ts)
            await self._delete_session(session)

    async def heartbeat(self, session_token: str) -> dict[str, Any]:
        """Prove the Client still holds its Session and extend expiry."""
        async with self._lock:
            session = await self._require_session(session_token)
            now = utc_now()
            session["expires_at"] = format_timestamp(
                now + timedelta(seconds=self.session_ttl_seconds)
            )
            await self._save_session(session)
            return {"session_expires_at": session["expires_at"]}

    # --- send ---

    async def send(
        self, session_token: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Accept one request or event for one recipient in this Team."""
        waiter: asyncio.Event | None = None
        ticket_id: str | None = None
        deadline_dt = None
        async with self._lock:
            result, wait_for = await self._send_locked(session_token, request)
            if wait_for is not None:
                ticket_id, deadline_dt = wait_for
                waiter = self._register_waiter(ticket_id)
        if waiter is not None and ticket_id is not None and deadline_dt is not None:
            try:
                ticket = await self._wait_until_terminal(ticket_id, deadline_dt, waiter)
                result = dict(result)
                result["ticket"] = ticket
            finally:
                self._drop_waiter(ticket_id, waiter)
        return result

    async def _send_locked(
        self, session_token: str, request: Mapping[str, Any]
    ) -> tuple[dict[str, Any], Optional[tuple[str, Any]]]:
        session = await self._require_session(session_token)
        if not isinstance(request, Mapping):
            _fail("invalid_request", "send body must be an object")
        body = dict(request)
        if json_size(body) > self.max_message_bytes:
            _fail("payload_too_large", "send body exceeds max_message_bytes")

        kind = body.get("kind")
        if kind not in MESSAGE_KINDS_SEND:
            _fail("invalid_request", "kind must be request or event")
        try:
            message_id = require_uuid(body.get("id"), field="id")
        except ValueError:
            _fail("invalid_request", "id must be a UUID")
        recipient_raw = body.get("recipient")
        if not isinstance(recipient_raw, str):
            _fail("invalid_request", "recipient is required")
        resolved = resolve_address(recipient_raw, self.name)
        if resolved == INVALID_ADDRESS:
            _fail("invalid_address", "Address syntax is invalid")
        if resolved == ADDRESS_OUTSIDE_TEAM:
            _fail("address_outside_team", "Address does not name the current Team")
        recipient = resolved

        collect = body.get("collect")
        deadline_raw = body.get("deadline")
        if kind == "event":
            if collect is not None or deadline_raw is not None:
                _fail("invalid_request", "an event cannot carry collect or deadline")
        if collect is not None:
            if collect not in COLLECT_NAMED:
                _fail("invalid_request", "collect is not a known collection strategy")
            if collect not in COLLECT_IMPLEMENTED:
                _fail(
                    "unsupported_collect_mode",
                    f"collect={collect} is not implemented yet",
                )
        if kind == "request" and (collect is not None or deadline_raw is not None):
            if collect is None or deadline_raw is None:
                _fail(
                    "invalid_request",
                    "a reply-expected request needs collect and a future deadline",
                )
            try:
                deadline_dt = parse_timestamp(deadline_raw)
            except ValueError:
                _fail("invalid_request", "deadline must be RFC 3339 UTC ending in Z")
            if deadline_dt <= utc_now():
                _fail("invalid_request", "deadline must be in the future")
        else:
            deadline_dt = None
            collect = None

        if "content" not in body:
            _fail("invalid_request", "content is required")
        content = body["content"]
        try:
            canonical_json(content)
        except (TypeError, ValueError):
            _fail("invalid_request", "content must be JSON")

        thread_id = body.get("thread_id")
        if thread_id is not None:
            try:
                thread_id = require_uuid(thread_id, field="thread_id")
            except ValueError:
                _fail("invalid_request", "thread_id must be a UUID")
        parent_id = body.get("parent_id")
        if parent_id is not None:
            try:
                parent_id = require_uuid(parent_id, field="parent_id")
            except ValueError:
                _fail("invalid_request", "parent_id must be a UUID")
        metadata = body.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            _fail("invalid_request", "metadata must be an object")

        extra = set(body.keys()) - {
            "id",
            "recipient",
            "kind",
            "content",
            "thread_id",
            "parent_id",
            "metadata",
            "collect",
            "deadline",
            "callback",
        }
        if extra:
            _fail("invalid_request", "send body contains unsupported fields")

        store = self._ensure_started()
        recipient_name = recipient.split("@", 1)[0]
        recipient_member = await self._get_member(recipient_name)
        if recipient_member is None:
            _fail("not_found", "Recipient Membership was not found")

        sender = session["address"]
        now, now_ts = self._now_pair()
        trace_id = new_uuid()
        parent = None
        if parent_id is not None:
            parent = await store.get(f"msg:{parent_id}")
            if parent is None:
                _fail("not_found", "parent_id was not found")
            authorized = sender in {parent.get("sender"), parent.get("recipient")}
            if not authorized:
                _fail("not_found", "parent_id was not found")
            if thread_id is not None:
                parent_thread = parent.get("thread_id")
                if parent_thread != thread_id:
                    _fail("invalid_request", "parent_id is not in the same Thread")
            trace_id = parent["trace_id"]

        if thread_id is not None:
            thread = await threads_mod.load_thread(store, thread_id)
            if thread is not None:
                participants = threads_mod.participant_set(thread)
                if sender not in participants or recipient not in participants:
                    _fail(
                        "forbidden", "Message is outside this Thread's participant set"
                    )

        semantic = {
            "content": content,
            "recipient": recipient,
            "kind": kind,
            "deadline": deadline_raw if deadline_dt is not None else None,
            "collect": collect,
            "thread_id": thread_id,
            "parent_id": parent_id,
            "metadata": metadata,
        }
        request_hash = semantic_hash(semantic)

        existing_msg = await store.get(f"msg:{message_id}")
        existing_send = await store.get(f"send:{message_id}")
        if existing_msg is not None or existing_send is not None:
            if existing_send is None or existing_send.get("sender") != sender:
                _fail("id_conflict", "Message id is already used")
            if existing_send.get("hash") != request_hash:
                _fail("id_conflict", "Message id is already used with different data")
            result = dict(existing_send["result"])
            if result.get("status") == "ticketed":
                ticket = await self._expire_ticket_if_due(message_id)
                if ticket is not None:
                    result["ticket"] = ticket
                if (
                    collect == "wait"
                    and ticket is not None
                    and ticket["state"] == "open"
                ):
                    return result, (message_id, parse_timestamp(ticket["deadline"]))
            return result, None

        items = await mailbox_mod.load_mailbox(store, recipient)
        if mailbox_mod.mailbox_depth(items) >= self.max_mailbox_depth:
            _fail("busy", "Recipient Mailbox is full")

        message: dict[str, Any] = {
            "id": message_id,
            "sender": sender,
            "recipient": recipient,
            "kind": kind,
            "content": content,
            "created_at": now_ts,
            "trace_id": trace_id,
        }
        if deadline_dt is not None:
            message["deadline"] = deadline_raw
        if thread_id is not None:
            message["thread_id"] = thread_id
        if parent_id is not None:
            message["parent_id"] = parent_id
        if metadata is not None:
            message["metadata"] = metadata

        await store.put(f"msg:{message_id}", message)
        mailbox_mod.enqueue_item(items, message_id, now_ts)
        await mailbox_mod.save_mailbox(store, recipient, items)
        self._signal_work(recipient_name)
        if thread_id is not None:
            await threads_mod.append_message(
                store,
                thread_id=thread_id,
                message=message,
                sender=sender,
                recipient=recipient,
            )

        if deadline_dt is None:
            result = {"status": "accepted", "message": message}
            await store.put(
                f"send:{message_id}",
                {
                    "sender": sender,
                    "hash": request_hash,
                    "collect": collect,
                    "result": result,
                },
            )
            return result, None

        ticket = tickets_mod.new_open_ticket(
            ticket_id=message_id,
            requester=sender,
            recipient=recipient,
            created_at=now_ts,
            deadline=deadline_raw,
            thread_id=thread_id,
        )
        await tickets_mod.save_ticket(store, ticket)
        result = {"status": "ticketed", "message": message, "ticket": ticket}
        await store.put(
            f"send:{message_id}",
            {
                "sender": sender,
                "hash": request_hash,
                "collect": collect,
                "result": result,
            },
        )
        if collect == "wait":
            return result, (message_id, deadline_dt)
        return result, None

    async def _wait_until_terminal(
        self, ticket_id: str, deadline_dt, event: asyncio.Event
    ) -> dict[str, Any]:
        while True:
            async with self._lock:
                ticket = await self._expire_ticket_if_due(ticket_id)
                if ticket is not None and tickets_mod.is_terminal(ticket):
                    return ticket
            remaining = (deadline_dt - utc_now()).total_seconds()
            if remaining <= 0:
                async with self._lock:
                    ticket = await self._expire_ticket_if_due(ticket_id)
                    if ticket is None:
                        _fail("not_found", "Ticket was not found")
                    return ticket
            try:
                await asyncio.wait_for(
                    event.wait(), timeout=min(0.2, max(remaining, 0.01))
                )
                event.clear()
            except asyncio.TimeoutError:
                continue

    # --- lease / complete / reply ---

    async def lease(self, session_token: str, max_items: int = 1) -> dict[str, Any]:
        """Pull available work from the calling Membership's Mailbox."""
        async with self._lock:
            session = await self._require_session(session_token)
            try:
                n = int(max_items)
            except (TypeError, ValueError):
                _fail("invalid_request", "max_items must be an integer")
            if n < 1 or n > 100:
                _fail("invalid_request", "max_items must be between 1 and 100")
            store = self._ensure_started()
            now, now_ts = self._now_pair()
            address = session["address"]
            items = await mailbox_mod.load_mailbox(store, address)
            await self._expire_mailbox_leases(items, now, now_ts)
            active = [
                lease_id
                for lease_id in session.get("lease_ids") or []
                if await self._lease_still_active(lease_id, now)
            ]
            session["lease_ids"] = active
            room = max(0, int(session["max_in_flight"]) - len(active))
            take = min(n, room)
            deliveries: list[dict[str, Any]] = []
            kept: list[dict[str, Any]] = []
            for item in items:
                if take <= 0:
                    kept.append(item)
                    continue
                if item.get("state") == "leased":
                    kept.append(item)
                    continue
                available = parse_timestamp(item["available_at"])
                if available > now:
                    kept.append(item)
                    continue
                message = await store.get(f"msg:{item['message_id']}")
                if message is None:
                    continue
                if message.get("kind") == "request" and message.get("deadline"):
                    ticket = await self._expire_ticket_if_due(message["id"])
                    if ticket is None or ticket["state"] != "open":
                        continue
                    lease_until = min(
                        now + timedelta(seconds=self.lease_ttl_seconds),
                        parse_timestamp(ticket["deadline"]),
                    )
                else:
                    lease_until = now + timedelta(seconds=self.lease_ttl_seconds)
                if lease_until <= now:
                    continue
                lease_id = mailbox_mod.new_lease_id()
                attempt = int(item.get("attempt") or 0) + 1
                expires_at = format_timestamp(lease_until)
                item["state"] = "leased"
                item["attempt"] = attempt
                item["lease_id"] = lease_id
                item["lease_expires_at"] = expires_at
                await mailbox_mod.put_lease(
                    store,
                    lease_id=lease_id,
                    message_id=message["id"],
                    address=address,
                    session_token=session["token"],
                    membership_name=session["membership_name"],
                    attempt=attempt,
                    expires_at=expires_at,
                )
                session.setdefault("lease_ids", []).append(lease_id)
                history, complete = await self._delivery_history(message)
                deliveries.append(
                    {
                        "lease_id": lease_id,
                        "lease_expires_at": expires_at,
                        "attempt": attempt,
                        "message": message,
                        "history": history,
                        "history_complete": complete,
                    }
                )
                kept.append(item)
                take -= 1
            await mailbox_mod.save_mailbox(store, address, kept)
            await self._save_session(session)
            return {"deliveries": deliveries}

    async def _expire_mailbox_leases(
        self, items: list[dict[str, Any]], now, now_ts: str
    ) -> None:
        store = self._ensure_started()
        for item in items:
            lease_id = mailbox_mod.expire_item_if_needed(item, now, now_ts)
            if lease_id:
                await mailbox_mod.deactivate_lease(store, lease_id)

    async def _lease_still_active(self, lease_id: str, now) -> bool:
        store = self._ensure_started()
        record = await mailbox_mod.get_lease(store, lease_id)
        if record is None:
            return False
        return mailbox_mod.lease_is_active(record, now)

    async def _delivery_history(
        self, message: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], bool]:
        thread_id = message.get("thread_id")
        if not thread_id:
            return [], True
        store = self._ensure_started()
        thread = await threads_mod.load_thread(store, thread_id)
        if thread is None:
            return [], True
        messages: list[dict[str, Any]] = []
        for message_id in thread.get("message_ids") or []:
            stored = await store.get(f"msg:{message_id}")
            if stored is not None:
                messages.append(stored)
        return threads_mod.history_window(
            messages,
            delivered_id=message["id"],
            limit=self.delivery_history_limit,
            max_bytes=self.max_message_bytes,
        )

    async def complete(self, session_token: str, lease_id: str) -> dict[str, Any]:
        """Finish a Delivery without a response Message.

        An event or no-reply request just ends. A reply-expected request is
        declined: the Ticket becomes ``declined``, which is not a failure.
        """
        async with self._lock:
            session = await self._require_session(session_token)
            try:
                lease_id = require_uuid(lease_id, field="lease_id")
            except ValueError:
                _fail("invalid_request", "lease_id must be a UUID")
            store = self._ensure_started()
            lease = await mailbox_mod.get_lease(store, lease_id)
            if (
                lease is None
                or lease.get("membership_name") != session["membership_name"]
            ):
                _fail("not_found", "lease_id was not found")
            existing = await store.get(f"complete:{lease_id}")
            if existing is not None:
                return dict(existing["result"])
            now, now_ts = self._now_pair()
            message = await store.get(f"msg:{lease['message_id']}")
            ticket = None
            if message and message.get("kind") == "request" and message.get("deadline"):
                ticket = await self._expire_ticket_if_due(message["id"])
                if ticket is not None and tickets_mod.is_terminal(ticket):
                    _fail("ticket_closed", "Ticket is already terminal")
            if not mailbox_mod.lease_is_active(lease, now):
                _fail("lease_expired", "Delivery lease is no longer active")
            result: dict[str, Any] = {}
            if ticket is not None and ticket["state"] == "open":
                ticket = tickets_mod.mark_declined(ticket, now_ts)
                await tickets_mod.save_ticket(store, ticket)
                result["ticket"] = ticket
                self._notify(ticket["id"])
            await self._finish_delivery(session, lease, now_ts)
            await store.put(f"complete:{lease_id}", {"result": result})
            return result

    async def reply(
        self, session_token: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Finish a reply-expected Delivery with content or an error."""
        async with self._lock:
            session = await self._require_session(session_token)
            if not isinstance(request, Mapping):
                _fail("invalid_request", "reply body must be an object")
            body = dict(request)
            try:
                reply_id = require_uuid(body.get("id"), field="id")
                lease_id = require_uuid(body.get("lease_id"), field="lease_id")
            except ValueError:
                _fail("invalid_request", "id and lease_id must be UUIDs")
            outcome = body.get("outcome")
            if outcome not in {"completed", "failed"}:
                _fail("invalid_request", "outcome must be completed or failed")
            store = self._ensure_started()
            lease = await mailbox_mod.get_lease(store, lease_id)
            if (
                lease is None
                or lease.get("membership_name") != session["membership_name"]
            ):
                _fail("not_found", "lease_id was not found")

            if outcome == "completed":
                if "content" not in body:
                    _fail(
                        "invalid_request", "content is required for a completed reply"
                    )
                payload = {"outcome": "completed", "content": body.get("content")}
            else:
                error = body.get("error")
                if not isinstance(error, dict):
                    _fail("invalid_request", "error is required for a failed reply")
                payload = {"outcome": "failed", "error": error}
            try:
                reply_hash = semantic_hash(payload)
            except (TypeError, ValueError):
                _fail("invalid_request", "reply data must be JSON")

            existing_reply = await store.get(f"reply:{reply_id}")
            existing_msg = await store.get(f"msg:{reply_id}")
            if existing_reply is not None:
                if existing_reply.get("sender") != session["address"]:
                    _fail("id_conflict", "Message id is already used")
                if existing_reply.get("hash") != reply_hash:
                    _fail(
                        "id_conflict", "Message id is already used with different data"
                    )
                return dict(existing_reply["result"])
            if existing_msg is not None:
                _fail("id_conflict", "Message id is already used")

            now, now_ts = self._now_pair()
            message = await store.get(f"msg:{lease['message_id']}")
            if (
                message is None
                or message.get("kind") != "request"
                or not message.get("deadline")
            ):
                _fail(
                    "invalid_request",
                    "reply is only valid for a reply-expected request",
                )
            ticket = await self._expire_ticket_if_due(message["id"])
            if ticket is not None and tickets_mod.is_terminal(ticket):
                if (
                    mailbox_mod.lease_is_active(lease, now)
                    or lease.get("membership_name") == session["membership_name"]
                ):
                    ticket = tickets_mod.observe_late_reply(ticket, now_ts)
                    await tickets_mod.save_ticket(store, ticket)
                _fail("ticket_closed", "Ticket is already terminal")
            if not mailbox_mod.lease_is_active(lease, now):
                _fail("lease_expired", "Delivery lease is no longer active")
            if ticket is None or ticket["state"] != "open":
                _fail("ticket_closed", "Ticket is already terminal")

            if outcome == "failed":
                error_obj = self._validate_error_object(payload["error"])
                reply_message: dict[str, Any] = {
                    "id": reply_id,
                    "sender": session["address"],
                    "recipient": message["sender"],
                    "kind": "error",
                    "error": error_obj,
                    "created_at": now_ts,
                    "trace_id": message["trace_id"],
                    "parent_id": message["id"],
                }
                if message.get("thread_id"):
                    reply_message["thread_id"] = message["thread_id"]
                ticket = tickets_mod.mark_failed(ticket, error_obj, now_ts)
            else:
                reply_message = {
                    "id": reply_id,
                    "sender": session["address"],
                    "recipient": message["sender"],
                    "kind": "response",
                    "content": payload["content"],
                    "created_at": now_ts,
                    "trace_id": message["trace_id"],
                    "parent_id": message["id"],
                }
                if message.get("thread_id"):
                    reply_message["thread_id"] = message["thread_id"]
                ticket = tickets_mod.mark_completed(ticket, reply_message, now_ts)

            await store.put(f"msg:{reply_id}", reply_message)
            if message.get("thread_id"):
                await threads_mod.append_message(
                    store,
                    thread_id=message["thread_id"],
                    message=reply_message,
                    sender=reply_message["sender"],
                    recipient=reply_message["recipient"],
                )
            await tickets_mod.save_ticket(store, ticket)
            await self._finish_delivery(session, lease, now_ts)
            result = {"ticket": ticket}
            await store.put(
                f"reply:{reply_id}",
                {"sender": session["address"], "hash": reply_hash, "result": result},
            )
            self._notify(ticket["id"])
            return result

    def _validate_error_object(self, error: Mapping[str, Any]) -> dict[str, Any]:
        code = error.get("code")
        message = error.get("message")
        if not isinstance(code, str) or _ERROR_CODE.fullmatch(code) is None:
            _fail("invalid_request", "error.code is invalid")
        if not isinstance(message, str) or message.strip() == "" or len(message) > 2000:
            _fail("invalid_request", "error.message is invalid")
        out: dict[str, Any] = {"code": code, "message": message}
        if "details" in error:
            if not isinstance(error["details"], dict):
                _fail("invalid_request", "error.details must be an object")
            out["details"] = error["details"]
        if "retryable" in error:
            if not isinstance(error["retryable"], bool):
                _fail("invalid_request", "error.retryable must be a boolean")
            out["retryable"] = error["retryable"]
        return out

    async def _finish_delivery(
        self, session: dict[str, Any], lease: dict[str, Any], now_ts: str
    ) -> None:
        store = self._ensure_started()
        items = await mailbox_mod.load_mailbox(store, lease["address"])
        mailbox_mod.remove_item(items, lease["message_id"])
        await mailbox_mod.save_mailbox(store, lease["address"], items)
        await mailbox_mod.deactivate_lease(store, lease["lease_id"])
        lease_ids = list(session.get("lease_ids") or [])
        if lease["lease_id"] in lease_ids:
            lease_ids.remove(lease["lease_id"])
        session["lease_ids"] = lease_ids
        await self._save_session(session)

    async def get_result(self, session_token: str, ticket_id: str) -> dict[str, Any]:
        """Return the Ticket owned by the calling Membership."""
        async with self._lock:
            session = await self._require_session(session_token)
            try:
                ticket_id = require_uuid(ticket_id, field="ticket_id")
            except ValueError:
                _fail("invalid_request", "ticket_id must be a UUID")
            ticket = await self._expire_ticket_if_due(ticket_id)
            if ticket is None or ticket.get("requester") != session["address"]:
                _fail("not_found", "Ticket was not found")
            return ticket

    async def get_history(
        self,
        session_token: str,
        thread_id: str,
        *,
        before: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return one page of a Thread's retained history."""
        async with self._lock:
            session = await self._require_session(session_token)
            try:
                thread_id = require_uuid(thread_id, field="thread_id")
            except ValueError:
                _fail("invalid_request", "thread_id must be a UUID")
            if before is not None:
                try:
                    before = require_uuid(before, field="before")
                except ValueError:
                    _fail("invalid_request", "before must be a UUID")
            try:
                n = int(limit)
            except (TypeError, ValueError):
                _fail("invalid_request", "limit must be an integer")
            if n < 1 or n > 200:
                _fail("invalid_request", "limit must be between 1 and 200")
            store = self._ensure_started()
            thread = await threads_mod.load_thread(store, thread_id)
            if thread is None or session["address"] not in threads_mod.participant_set(
                thread
            ):
                _fail("not_found", "Thread was not found")
            messages: list[dict[str, Any]] = []
            for message_id in thread.get("message_ids") or []:
                stored = await store.get(f"msg:{message_id}")
                if stored is not None:
                    messages.append(stored)
            page, has_more = threads_mod.page_history(messages, before=before, limit=n)
            return {"messages": page, "has_more": has_more}

    async def find(
        self,
        session_token: str,
        query: str,
        *,
        limit: int = 10,
        detail: str = "summary",
    ) -> dict[str, Any]:
        """Search this Team's Directory. Ranking is lexical until discovery lands."""
        async with self._lock:
            session = await self._require_session(session_token)
            if not isinstance(query, str) or not query.strip() or len(query) > 1000:
                _fail(
                    "invalid_request",
                    "query must be 1 to 1000 non-whitespace characters",
                )
            try:
                n = int(limit)
            except (TypeError, ValueError):
                _fail("invalid_request", "limit must be an integer")
            if n < 1 or n > 100:
                _fail("invalid_request", "limit must be between 1 and 100")
            if detail not in {"summary", "full"}:
                _fail("invalid_request", "detail must be summary or full")
            store = self._ensure_started()
            names = await store.set_members("members")
            scored: list[tuple[float, str, dict[str, Any]]] = []
            query_tokens = _tokens(query)
            for name in names:
                member = await self._get_member(name)
                if member is None or member["address"] == session["address"]:
                    continue
                score = _relevance(query_tokens, member["profile"])
                scored.append((score, member["address"], member))
            scored.sort(key=lambda item: (-item[0], item[1]))
            matches = []
            for _, _, member in scored[:n]:
                profile = member["profile"]
                match: dict[str, Any] = {
                    "address": member["address"],
                    "summary": profile["summary"],
                    "skill_names": [
                        skill["name"] for skill in profile.get("skills") or []
                    ],
                }
                if profile.get("tags"):
                    match["tags"] = list(profile["tags"])
                if detail == "full":
                    match["agent_did"] = member["agent_did"]
                    match["profile"] = profile
                matches.append(match)
            return {"matches": matches}

    async def get_profile(self, session_token: str, address: str) -> dict[str, Any]:
        """Return one Directory entry by local or same-Team Address."""
        async with self._lock:
            await self._require_session(session_token)
            if not isinstance(address, str):
                _fail("invalid_request", "address is required")
            resolved = resolve_address(address, self.name)
            if resolved == INVALID_ADDRESS:
                _fail("invalid_address", "Address syntax is invalid")
            if resolved == ADDRESS_OUTSIDE_TEAM:
                _fail("address_outside_team", "Address does not name the current Team")
            name = resolved.split("@", 1)[0]
            member = await self._get_member(name)
            if member is None:
                _fail("not_found", "Membership was not found")
            return {
                "address": member["address"],
                "agent_did": member["agent_did"],
                "profile": member["profile"],
            }

    async def _expire_ticket_if_due(self, ticket_id: str) -> Optional[dict[str, Any]]:
        store = self._ensure_started()
        ticket = await tickets_mod.load_ticket(store, ticket_id)
        if ticket is None:
            return None
        now, now_ts = self._now_pair()
        if ticket["state"] == "open" and tickets_mod.deadline_passed(ticket, now):
            ticket = tickets_mod.mark_expired(ticket, now_ts)
            await tickets_mod.save_ticket(store, ticket)
            items = await mailbox_mod.load_mailbox(store, ticket["recipient"])
            mailbox_mod.remove_item(items, ticket["id"])
            await mailbox_mod.save_mailbox(store, ticket["recipient"], items)
            self._notify(ticket["id"])
        return ticket

    async def _sweep_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.sweep_interval_seconds)
                try:
                    async with self._lock:
                        await self._sweep_once()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.debug("Team sweep failed team=%s", self.name, exc_info=True)
        except asyncio.CancelledError:
            return

    async def _sweep_once(self) -> None:
        store = self._ensure_started()
        now, now_ts = self._now_pair()
        for token in list(await store.set_members("sessions")):
            session = await self._get_session(token)
            if session is None:
                continue
            if parse_timestamp(session["expires_at"]) <= now:
                await self._release_session_leases(session, now_ts)
                await self._delete_session(session)
        for lease_id in list(await store.set_members(mailbox_mod.LEASES_SET)):
            lease = await mailbox_mod.get_lease(store, lease_id)
            if lease is None:
                continue
            if mailbox_mod.lease_is_active(lease, now):
                continue
            items = await mailbox_mod.load_mailbox(store, lease["address"])
            item = mailbox_mod.find_item(items, lease["message_id"])
            if item is not None and item.get("lease_id") == lease_id:
                mailbox_mod.release_lease_on_item(item, now_ts)
                await mailbox_mod.save_mailbox(store, lease["address"], items)
                self._signal_work(lease["membership_name"])
            await mailbox_mod.deactivate_lease(store, lease_id)
        keep_ids: set[str] = set()
        for ticket_id in list(await store.set_members(tickets_mod.OPEN_TICKETS_SET)):
            ticket = await self._expire_ticket_if_due(ticket_id)
            if ticket is not None and ticket["state"] == "open":
                keep_ids.add(ticket["id"])
        retention = timedelta(seconds=self.terminal_ticket_retention_seconds)
        for ticket_id in list(await store.set_members(tickets_mod.ALL_TICKETS_SET)):
            ticket = await tickets_mod.load_ticket(store, ticket_id)
            if ticket is None or ticket["state"] == "open":
                continue
            closed_at = parse_timestamp(ticket["updated_at"])
            deadline = parse_timestamp(ticket["deadline"])
            retain_until = max(deadline, closed_at + retention)
            if retain_until <= now:
                await tickets_mod.delete_ticket(store, ticket_id)
            else:
                keep_ids.add(ticket["id"])
                if ticket.get("response"):
                    keep_ids.add(ticket["response"]["id"])
        for thread_id in list(await store.set_members(threads_mod.THREADS_SET)):
            thread = await threads_mod.load_thread(store, thread_id)
            if thread is None:
                continue
            messages_by_id: dict[str, dict[str, Any]] = {}
            for message_id in thread.get("message_ids") or []:
                stored = await store.get(f"msg:{message_id}")
                if stored is not None:
                    messages_by_id[message_id] = stored
            trimmed = threads_mod.trim_thread_ids(
                list(thread.get("message_ids") or []),
                messages_by_id,
                keep_ids=keep_ids,
                max_messages=self.thread_message_limit,
            )
            dropped = set(thread.get("message_ids") or []) - set(trimmed)
            if dropped:
                thread["message_ids"] = trimmed
                await threads_mod.save_thread(store, thread)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _relevance(query_tokens: set[str], profile: Mapping[str, Any]) -> float:
    if not query_tokens:
        return 0.0
    parts = [str(profile.get("summary") or "")]
    for skill in profile.get("skills") or []:
        parts.append(str(skill.get("name") or ""))
        parts.append(str(skill.get("description") or ""))
        parts.extend(str(example) for example in skill.get("examples") or [])
        parts.extend(str(tag) for tag in skill.get("tags") or [])
    parts.extend(str(tag) for tag in profile.get("tags") or [])
    haystack = _tokens(" ".join(parts))
    if not haystack:
        return 0.0
    return len(query_tokens & haystack) / len(query_tokens)


def _is_loopback(host: str) -> bool:
    """Return True when ``host`` is a loopback name or address."""
    import ipaddress
    import socket

    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return False
    if not infos:
        return False
    for info in infos:
        try:
            if not ipaddress.ip_address(info[4][0]).is_loopback:
                return False
        except (ValueError, IndexError):
            return False
    return True


def _bound_socket(server: Any) -> tuple[str, int]:
    """Return (host, port) for a started uvicorn Server."""
    servers = getattr(server, "servers", None) or []
    for http_server in servers:
        sockets = getattr(http_server, "sockets", None) or []
        for sock in sockets:
            name = sock.getsockname()
            if len(name) >= 2:
                return str(name[0]), int(name[1])
    raise TeamError("unavailable", "HTTP server started without a bound socket")
