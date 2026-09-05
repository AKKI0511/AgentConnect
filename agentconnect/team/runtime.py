"""Team Runtime: mailboxes, tickets, threads, and routing.

A Team is a running process that serves one named Team. Agents stay in
their own processes and pull work through Runtime operations. This module
never holds Agent objects and never calls a method on an Agent.

Start, stop, serve, and join are the process API:

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

Embedded joins omit credentials. A Team started with
``require_join_auth=True`` (or any join that carries credentials) checks a
join token and an EdDSA identity proof.

    team = await Team("content-squad", require_join_auth=True).start()
    url = await team.serve()
    writer = Writer(name="writer")
    issued = await team.issue_join_token(name="writer", agent_did=writer.agent_did)
    await writer.join(url, join_token=issued["token"])

``send``, ``lease``, ``complete``, ``reply``, and the other token-taking
methods are the Session transport. HTTP, MCP, and the in-process Session
call them by name. Agent code uses ``BaseAgent``.

Pass ``store="memory"`` (the default) for a process-local Team. Pass a
Redis URL when Memberships, Sessions, mailboxes, open Tickets, and
Thread history must survive a Runtime restart.

Open Tickets are retained until at least their deadline. Terminal Tickets
are kept for 24 hours after they close, or until that deadline if it is
later. Thread history is trimmed by count once no open Ticket still
needs an older Message. A ``collect=wait`` send holds until the Ticket
is terminal or ``wait_hold_seconds`` elapses, then returns the current
Ticket. One Membership may hold at most ``max_held_waits`` of those
sends at once.

Expiry is indexed by time. The background sweep pops Sessions, leases,
Tickets, and join credentials that are due. It does not walk every
stored id. ``status`` reads presence from stored Sessions, so a durable
Runtime still reports a live Membership as online after a restart.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import timedelta
from typing import Any, Callable, Mapping, NoReturn, Optional, Sequence, Union

from pydantic import ValidationError

from agentconnect.core.address import (
    ADDRESS_OUTSIDE_TEAM,
    INVALID_ADDRESS,
    parse_agent_name,
    parse_team_name,
    resolve_address,
)

from agentconnect.core.base import dump_public, validation_message
from agentconnect.core.directory import DirectoryEntry
from agentconnect.core.identity import AgentIdentity
from agentconnect.core.operations import (
    CompleteResult,
    HeartbeatResult,
    JoinChallenge,
    JoinResult,
    JoinTokenIssued,
    ReplyResult,
    RuntimeLimits,
    StatusResult,
    TeamRoster,
    TraceResult,
    parse_history_result,
    parse_join_request,
    parse_lease_result,
    parse_reply_request,
    parse_send_request,
    parse_send_result,
)
from agentconnect.core.primitives import DeliveryHistoryForm
from agentconnect.core.error import ErrorObject
from agentconnect.core.profile import AgentProfile
from agentconnect.core.ticket import parse_ticket
from agentconnect.team.directory import Directory, MAX_FIND_LIMIT
from agentconnect.team.directory.embedder import EmbeddingsArg, resolve_embedder
import agentconnect.team.auth as auth_mod
import agentconnect.team.mailbox as mailbox_mod
import agentconnect.team.tickets as tickets_mod
import agentconnect.team.threads as threads_mod
import agentconnect.team.trace as trace_mod
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
    DEFAULT_JOIN_CHALLENGE_TTL_SECONDS,
    DEFAULT_JOIN_TOKEN_TTL_SECONDS,
    DEFAULT_LEASE_TTL_SECONDS,
    DEFAULT_MAX_HELD_WAITS,
    DEFAULT_MAX_IN_FLIGHT,
    DEFAULT_MAX_INSTANCES,
    DEFAULT_MAX_MAILBOX_DEPTH,
    DEFAULT_MAX_MESSAGE_BYTES,
    DEFAULT_SESSION_TTL_SECONDS,
    DEFAULT_TERMINAL_TICKET_RETENTION_SECONDS,
    DEFAULT_THREAD_MESSAGE_LIMIT,
    DEFAULT_WAIT_HOLD_SECONDS,
    MESSAGE_KINDS_SEND,
    OPERATOR_NAME,
    RESERVED_MCP_TOOL_NAMES,
    SWEEP_INTERVAL_SECONDS,
)
from agentconnect.team.errors import TeamError
import agentconnect.team.expiry as expiry_mod
from agentconnect.team.locks import KeyedLock
from agentconnect.team.store.base import Store
from agentconnect.team.store.memory import MemoryStore
from agentconnect.team.store.redis import RedisStore

logger = logging.getLogger(__name__)

StoreArg = Union[Store, str, None]


def _fail(code: str, message: str, **kwargs: Any) -> NoReturn:
    raise TeamError(code, message, **kwargs)


def _is_principal(member: Mapping[str, Any] | None) -> bool:
    """Return True when ``member`` may act but must not be hired."""
    if not isinstance(member, Mapping):
        return False
    if member.get("principal") is True:
        return True
    return member.get("name") == OPERATOR_NAME


class Team:
    """Runtime serving one Team.

    Process API: :meth:`start`, :meth:`stop`, :meth:`serve`, :meth:`join`,
    :meth:`issue_join_token`, :meth:`revoke_join_token`, :meth:`status`,
    :meth:`get_trace`, :meth:`remove_membership`.

    Operations that take a Session token are the Session transport. HTTP,
    MCP, and the in-process Session call them by name.

    The Team owns Memberships, Sessions, Mailboxes, Deliveries, Tickets,
    Thread history, and the Directory. ``find`` ranks other members from a
    natural-language query. :meth:`serve` also mounts the Team MCP server
    at ``{origin}/mcp``. ``status`` reports ``online`` from stored
    Sessions. Expiry is processed from a time-ordered index.
    """

    def __init__(
        self,
        name: str,
        *,
        store: StoreArg = None,
        max_message_bytes: int = DEFAULT_MAX_MESSAGE_BYTES,
        max_mailbox_depth: int = DEFAULT_MAX_MAILBOX_DEPTH,
        delivery_history_limit: int = DEFAULT_DELIVERY_HISTORY_LIMIT,
        wait_hold_seconds: float = DEFAULT_WAIT_HOLD_SECONDS,
        max_held_waits: int = DEFAULT_MAX_HELD_WAITS,
        session_ttl_seconds: float = DEFAULT_SESSION_TTL_SECONDS,
        lease_ttl_seconds: float = DEFAULT_LEASE_TTL_SECONDS,
        terminal_ticket_retention_seconds: float = DEFAULT_TERMINAL_TICKET_RETENTION_SECONDS,
        thread_message_limit: int = DEFAULT_THREAD_MESSAGE_LIMIT,
        max_instances: int = DEFAULT_MAX_INSTANCES,
        sweep_interval_seconds: float = SWEEP_INTERVAL_SECONDS,
        require_join_auth: bool = False,
        join_challenge_ttl_seconds: float = DEFAULT_JOIN_CHALLENGE_TTL_SECONDS,
        join_token_ttl_seconds: float = DEFAULT_JOIN_TOKEN_TTL_SECONDS,
        embeddings: EmbeddingsArg = "auto",
        tools: Sequence[Callable[..., Any]] | None = None,
    ) -> None:
        """Create an unstarted Runtime for Team ``name``.

        Args:
            name: Team name, a lowercase DNS label.
            store: ``"memory"`` (default), a Redis URL, or a Store.
            require_join_auth: When True, every join needs a join token and
                an identity proof, including in-process joins.
            wait_hold_seconds: How long ``collect=wait`` may keep ``send``
                open. After this the current Ticket is returned even if it
                is still open; collect the rest with ``get_result``.
            max_held_waits: How many ``collect=wait`` sends one Membership
                may hold at once. Further waits fail with ``wait_limit``.
            embeddings: How Profiles are turned into vectors for ``find``.
                ``"auto"`` uses a hosted embedding API when a key is
                already configured, a local ONNX model when
                ``agentconnect[embeddings]`` is installed, and hashed
                n-grams otherwise. ``"none"`` forces hashed n-grams.
                Pass a callable ``(list[str]) -> list[list[float]]`` to
                supply your own embeddings.
            tools: Extra MCP tools this Team serves beside find, ask, tell,
                get_result, and get_history. Each item is a callable whose
                ``__name__`` is the tool name. Those five names are reserved.
        """
        team_name = parse_team_name(name)
        if team_name is None:
            raise ValueError("name is not a valid Team name")
        self.name = team_name
        self._store_arg = store
        self._store: Optional[Store] = None
        self.max_message_bytes = int(max_message_bytes)
        self.max_mailbox_depth = int(max_mailbox_depth)
        self.delivery_history_limit = int(delivery_history_limit)
        self.wait_hold_seconds = float(wait_hold_seconds)
        self.max_held_waits = int(max_held_waits)
        self.session_ttl_seconds = float(session_ttl_seconds)
        self.lease_ttl_seconds = float(lease_ttl_seconds)
        self.terminal_ticket_retention_seconds = float(
            terminal_ticket_retention_seconds
        )
        self.thread_message_limit = int(thread_message_limit)
        self.max_instances = int(max_instances)
        self.sweep_interval_seconds = float(sweep_interval_seconds)
        self.require_join_auth = bool(require_join_auth)
        self.join_challenge_ttl_seconds = float(join_challenge_ttl_seconds)
        self.join_token_ttl_seconds = float(join_token_ttl_seconds)
        try:
            self._embedder = resolve_embedder(embeddings)
        except (TypeError, ValueError) as exc:
            raise ValueError(str(exc)) from exc
        extras = list(tools or [])
        reserved = RESERVED_MCP_TOOL_NAMES
        for fn in extras:
            name = getattr(fn, "__name__", "")
            if name in reserved:
                raise ValueError(f"tool name {name!r} is reserved")
        self._extra_tools = extras
        self._operator_token: Optional[str] = None
        self._mcp: Any = None
        self._mcp_session_cm: Any = None
        self._directory: Optional[Directory] = None
        self._identity: Optional[AgentIdentity] = None
        self._keys = KeyedLock()
        self._waiters: dict[str, list[asyncio.Event]] = {}
        self._session_wake: dict[str, list[asyncio.Event]] = {}
        self._work_waiters: dict[str, list[asyncio.Event]] = {}
        self._sse_subscribers: dict[str, list[asyncio.Queue]] = {}
        self._trace_subscribers: list[tuple[str, asyncio.Queue]] = []
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
    def limits(self) -> RuntimeLimits:
        """Runtime limits reported on ``join``."""
        return RuntimeLimits(
            max_message_bytes=self.max_message_bytes,
            max_mailbox_depth=self.max_mailbox_depth,
            delivery_history_limit=self.delivery_history_limit,
            wait_hold_seconds=self.wait_hold_seconds,
            max_held_waits=self.max_held_waits,
        )

    @property
    def identity(self) -> AgentIdentity:
        """Team Ed25519 identity. Available after :meth:`start`."""
        if self._identity is None:
            raise TeamError("unavailable", "Team has not been started")
        return self._identity

    @property
    def team_did(self) -> str:
        """Team ``did:key``. Available after :meth:`start`."""
        return self.identity.did

    async def start(self) -> "Team":
        """Open the store and start background expiry. Returns this Team."""
        if self._started:
            return self
        self._store = self._build_store()
        await self._store.open()
        self._started = True
        self._directory = Directory(self._store, self._embedder)
        await self._ensure_identity()
        await self._reserve_operator()
        await self._restore_session_index()
        loop = asyncio.get_running_loop()
        self._sweep_task = loop.create_task(self._sweep_loop())
        return self

    @property
    def url(self) -> Optional[str]:
        """HTTP origin this Runtime is serving, or None when not serving."""
        return self._http_url

    @property
    def mcp_url(self) -> Optional[str]:
        """MCP streamable-HTTP URL, or None when not serving.

        Add this URL to Cursor or any MCP client:

            url = await team.serve()
            team.mcp_url  # http://127.0.0.1:<port>/mcp
        """
        if self._http_url is None:
            return None
        return f"{self._http_url}/mcp"

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

    async def _record_trace(self, event: dict[str, Any]) -> None:
        """Persist one Trace event and notify watch subscribers."""
        store = self._ensure_started()
        stored = await trace_mod.append_event(store, event)
        for _token, queue in list(self._trace_subscribers):
            try:
                queue.put_nowait(stored)
            except asyncio.QueueFull:
                pass

    async def wait_for_work(self, session_token: str, timeout: float = 30.0) -> bool:
        """Block until this Session's Mailbox has leaseable work, or timeout.

        This is an in-process hint, not a Runtime operation. HTTP Clients
        use the SSE stream instead. Returns True when work looks available.
        """
        event = asyncio.Event()
        name = ""
        session = await self._require_session(session_token)
        name = session["membership_name"]
        self._work_waiters.setdefault(name, []).append(event)
        store = self._ensure_started()
        if await mailbox_mod.has_ready(store, session["address"], utc_now()):
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
        session = await self._require_session(session_token)
        self._session_tokens_by_member.setdefault(
            session["membership_name"], set()
        ).add(session_token)
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
        """Return a short-lived one-time challenge for an identity proof.

        Fetch this, sign it with the Agent key, then pass the JWT as
        ``identity_proof`` on :meth:`join`.
        """
        store = self._ensure_started()
        record = await auth_mod.create_join_challenge(
            store,
            self.name,
            ttl_seconds=self.join_challenge_ttl_seconds,
        )
        return JoinChallenge.model_validate(record)

    async def caller_address(self, session_token: str) -> str:
        """Return the qualified Address stamped on this Session."""
        session = await self._require_session(session_token)
        return str(session["address"])

    async def roster(self) -> TeamRoster:
        """Return every Agent Membership as a DirectoryEntry list.

        Principals, including ``operator``, are omitted. Used by the MCP
        roster resource. Not an HTTP Runtime operation.
        """
        store = self._ensure_started()
        names = await store.set_members("members")
        members: list[DirectoryEntry] = []
        for name in names:
            member = await self._get_member(name)
            if member is None or _is_principal(member) or not member.get("profile"):
                continue
            members.append(
                DirectoryEntry.model_validate(
                    {
                        "address": member["address"],
                        "agent_did": member["agent_did"],
                        "profile": member["profile"],
                    }
                )
            )
        members.sort(key=lambda item: str(item.address))
        return TeamRoster(team_name=self.name, members=members)

    async def ensure_operator_session(self) -> str:
        """Return a live Session token for the reserved ``operator`` principal.

        Loopback MCP and HTTP calls with no Authorization header use this
        Session. The name ``operator`` is reserved when the Runtime starts.
        An Agent cannot join it.
        """
        self._ensure_started()
        if self._operator_token:
            try:
                await self.heartbeat(self._operator_token)
                return self._operator_token
            except TeamError as exc:
                if exc.code != "unauthorized":
                    raise
                self._operator_token = None
        async with self._keys.acquire("operator"):
            if self._operator_token:
                try:
                    session = await self._get_session(self._operator_token)
                    if session is not None:
                        return self._operator_token
                except TeamError:
                    self._operator_token = None
            return await self._open_operator_session()

    async def serve(self, host: str = "127.0.0.1", port: int = 0) -> str:
        """Serve Runtime HTTP and the Team MCP server on a loopback address.

        Returns the origin agents pass to ``BaseAgent.join``, for example
        ``http://127.0.0.1:9000``. The MCP door is ``{origin}/mcp``.
        Non-loopback hosts are rejected.
        """
        self._ensure_started()
        async with self._keys.acquire("serve"):
            if self._http_task is not None and not self._http_task.done():
                if self._http_url is None:
                    raise TeamError("internal", "HTTP serving is starting")
                return self._http_url
            if not _is_loopback(host):
                _fail(
                    "invalid_request",
                    "Team.serve binds loopback only",
                )
            return await self._serve_http(host, port)

    async def _serve_http(self, host: str, port: int) -> str:
        await self.ensure_operator_session()
        from agentconnect.team.http import create_runtime_app
        import uvicorn

        app = create_runtime_app(self)
        config = uvicorn.Config(
            app,
            host=host,
            port=int(port),
            log_level="warning",
            lifespan="on",
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

    @staticmethod
    def _member_sessions_key(name: str) -> str:
        return f"sessions:{name}"

    async def _restore_session_index(self) -> None:
        """Rebuild the process Session map and Session expiry index from the store."""
        store = self._ensure_started()
        now = utc_now()
        restored: dict[str, set[str]] = {}
        for name in await store.set_members("members"):
            live: set[str] = set()
            for token in await store.set_members(self._member_sessions_key(name)):
                session = await self._get_session(token)
                if session is None:
                    await store.set_remove(self._member_sessions_key(name), token)
                    continue
                if parse_timestamp(session["expires_at"]) > now:
                    live.add(token)
                    await expiry_mod.schedule(
                        store, expiry_mod.SESSIONS, token, session["expires_at"]
                    )
            if live:
                restored[name] = live
        self._session_tokens_by_member = restored

    async def _member_is_online(self, name: str, now) -> bool:
        """Return True when stored Sessions for ``name`` include an unexpired one."""
        store = self._ensure_started()
        for token in await store.set_members(self._member_sessions_key(name)):
            session = await self._get_session(token)
            if session is None:
                continue
            if parse_timestamp(session["expires_at"]) > now:
                return True
        return False

    async def _append_thread_message(
        self,
        *,
        thread_id: str,
        message: dict[str, Any],
        sender: str,
        recipient: str,
    ) -> dict[str, Any]:
        store = self._ensure_started()
        keep_ids = await tickets_mod.retained_message_ids(store)
        return await threads_mod.append_message(
            store,
            thread_id=thread_id,
            message=message,
            sender=sender,
            recipient=recipient,
            max_messages=self.thread_message_limit,
            keep_ids=keep_ids,
        )

    async def _trim_thread(self, thread_id: str) -> None:
        store = self._ensure_started()
        thread = await threads_mod.load_thread(store, thread_id)
        if thread is None:
            return
        keep_ids = await tickets_mod.retained_message_ids(store)
        trimmed = threads_mod.trim_thread_ids(
            list(thread.get("message_ids") or []),
            keep_ids=keep_ids,
            max_messages=self.thread_message_limit,
        )
        if trimmed != list(thread.get("message_ids") or []):
            thread["message_ids"] = trimmed
            await threads_mod.save_thread(store, thread)

    async def _session_tokens_for(self, membership_name: str) -> list[str]:
        store = self._ensure_started()
        return await store.set_members(self._member_sessions_key(membership_name))

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
        token = session["token"]
        name = session["membership_name"]
        await store.put(f"session:{token}", session)
        await store.put(
            f"instance:{name}:{session['instance_id']}",
            token,
        )
        await store.set_add(self._member_sessions_key(name), token)
        await expiry_mod.schedule(
            store, expiry_mod.SESSIONS, token, session["expires_at"]
        )
        self._session_tokens_by_member.setdefault(name, set()).add(token)
        join_token = session.get("join_token")
        if isinstance(join_token, str) and join_token:
            await auth_mod.bind_session_to_token(store, join_token, token)

    async def _delete_session(self, session: dict[str, Any]) -> None:
        store = self._ensure_started()
        token = session["token"]
        name = session["membership_name"]
        await store.delete(f"session:{token}")
        await store.delete(f"instance:{name}:{session['instance_id']}")
        await store.set_remove(self._member_sessions_key(name), token)
        await expiry_mod.cancel(store, expiry_mod.SESSIONS, token)
        tokens = self._session_tokens_by_member.get(name)
        if tokens is not None:
            tokens.discard(token)
            if not tokens:
                self._session_tokens_by_member.pop(name, None)
        join_token = session.get("join_token")
        if isinstance(join_token, str) and join_token:
            await auth_mod.unbind_session_from_token(store, join_token, token)
        self._wake_session(token)
        for queue in self._sse_subscribers.pop(token, []):
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
        remaining: list[tuple[str, asyncio.Queue]] = []
        for queued_token, queue in self._trace_subscribers:
            if queued_token == token:
                try:
                    queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass
            else:
                remaining.append((queued_token, queue))
        self._trace_subscribers = remaining
        if self._operator_token == token:
            self._operator_token = None

    def _wake_session(self, session_token: str) -> None:
        """Wake waiters bound to this Session (waiting sends, work hints)."""
        for event in self._session_wake.pop(session_token, []):
            event.set()

    def _register_session_wake(self, session_token: str, event: asyncio.Event) -> None:
        self._session_wake.setdefault(session_token, []).append(event)

    def _drop_session_wake(self, session_token: str, event: asyncio.Event) -> None:
        waiters = self._session_wake.get(session_token)
        if waiters is None:
            return
        try:
            waiters.remove(event)
        except ValueError:
            pass
        if not waiters:
            self._session_wake.pop(session_token, None)

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

    async def _require_operator(self, session_token: Optional[str]) -> dict[str, Any]:
        """Return the Session, or fail if it is not the operator."""
        session = await self._require_session(session_token)
        if session["membership_name"] != OPERATOR_NAME:
            _fail("forbidden", "This operation is limited to the operator")
        return session

    async def _session_count(self, membership_name: str) -> int:
        store = self._ensure_started()
        now = utc_now()
        count = 0
        for token in await store.set_members(
            self._member_sessions_key(membership_name)
        ):
            session = await self._get_session(token)
            if session is None:
                await store.set_remove(
                    self._member_sessions_key(membership_name), token
                )
                continue
            if parse_timestamp(session["expires_at"]) > now:
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
            await mailbox_mod.return_item(
                store, lease["address"], lease["message_id"], lease_id, now_ts
            )
            await mailbox_mod.deactivate_lease(store, lease_id)
        session["lease_ids"] = []
        self._signal_work(session["membership_name"])

    def _join_result(
        self, session: dict[str, Any], member: dict[str, Any]
    ) -> JoinResult:
        return JoinResult(
            session_token=session["token"],
            session_expires_at=session["expires_at"],
            address=member["address"],
            team_name=self.name,
            agent_did=member["agent_did"],
            instance_id=session["instance_id"],
            persistence=self.persistence,  # type: ignore[arg-type]
            limits=self.limits,
            spec_version=SPEC_VERSION,
        )

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
        delivery_history: DeliveryHistoryForm | None = None,
        request: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create or reconnect a Membership and open a Session.

        Embedded Teams accept joins without credentials. Pass
        ``join_token`` and ``identity_proof`` when the Team was started
        with ``require_join_auth=True``, or when joining over HTTP with a
        token the operator issued.

        ``name`` is canonicalized to lowercase. A name and DID that already
        belong together reconnect; any other clash fails with
        ``name_conflict``. ``delivery_history="ids"`` puts earlier Message
        ids on each Delivery instead of Message bodies.
        """
        if request is not None:
            if not isinstance(request, Mapping):
                _fail("invalid_request", "join body must be an object")
            version = request.get("spec_version", spec_version)
            if version != SPEC_VERSION:
                _fail(
                    "unsupported_version", "Client and Runtime contract drafts differ"
                )
            try:
                parsed = parse_join_request(request)
            except ValueError as exc:
                _fail("invalid_request", str(exc))
            name = parsed.name
            agent_did = parsed.agent_did
            profile = parsed.profile.to_public_dict()
            spec_version = parsed.spec_version
            instance_id = parsed.instance_id
            if parsed.max_in_flight is not None:
                max_in_flight = parsed.max_in_flight
            join_token = parsed.join_token
            identity_proof = parsed.identity_proof
            delivery_history = parsed.delivery_history
        canonical_name = parse_agent_name(name or "")
        if canonical_name is None:
            _fail("invalid_request", "Agent name is invalid")
        async with self._keys.acquire(f"member:{canonical_name}"):
            return await self._join_locked(
                name=name,
                agent_did=agent_did,
                profile=profile,
                spec_version=spec_version,
                instance_id=instance_id,
                max_in_flight=max_in_flight,
                join_token=join_token,
                identity_proof=identity_proof,
                delivery_history=delivery_history,
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
        join_token: str | None,
        identity_proof: str | None,
        delivery_history: DeliveryHistoryForm | None,
    ) -> dict[str, Any]:
        self._ensure_started()
        if spec_version != SPEC_VERSION:
            _fail("unsupported_version", "Client and Runtime contract drafts differ")
        canonical_name = parse_agent_name(name or "")
        if canonical_name is None:
            _fail("invalid_request", "Agent name is invalid")
        if canonical_name == OPERATOR_NAME:
            _fail(
                "name_conflict",
                "The name operator is reserved for the local operator",
            )
        try:
            did = require_did(agent_did)
        except ValueError:
            _fail("invalid_request", "agent_did must be a did:key identifier")
        try:
            canonical_profile = AgentProfile.model_validate(
                profile or {}
            ).to_public_dict()
        except ValidationError as exc:
            _fail("invalid_request", validation_message(exc))
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
        history_form = delivery_history or "bodies"
        if history_form not in {"bodies", "ids"}:
            _fail("invalid_request", "delivery_history must be bodies or ids")

        store = self._ensure_started()
        now, now_ts = self._now_pair()
        token_record = await auth_mod.authenticate_join(
            store,
            team_name=self.name,
            agent_did=did,
            name=canonical_name,
            join_token=join_token,
            identity_proof=identity_proof,
            require_auth=self.require_join_auth,
            now=now,
        )

        by_name = await self._get_member(canonical_name)
        by_did = await self._get_member_by_did(did)
        if by_name is None and by_did is None:
            member = {
                "name": canonical_name,
                "address": f"{canonical_name}@{self.name}",
                "agent_did": did,
                "profile": canonical_profile,
            }
            if not await store.insert(f"member:{canonical_name}", member):
                _fail(
                    "name_conflict",
                    "Agent name and DID do not identify the same Membership",
                )
            if not await store.insert(f"did:{did}", canonical_name):
                await store.delete(f"member:{canonical_name}")
                _fail(
                    "name_conflict",
                    "Agent name and DID do not identify the same Membership",
                )
            await store.set_add("members", canonical_name)
        elif (
            by_name is not None
            and by_did is not None
            and by_name["name"] == by_did["name"]
            and by_name["agent_did"] == did
        ):
            member = dict(by_name)
            member["profile"] = canonical_profile
        else:
            _fail(
                "name_conflict",
                "Agent name and DID do not identify the same Membership",
            )

        attestation = auth_mod.mint_member_attestation(
            self.identity,
            agent_did=did,
            name=canonical_name,
            address=member["address"],
            team_name=self.name,
            now=now,
        )
        if attestation is not None:
            member["attestation"] = attestation
        await self._save_member(member)
        if self._directory is not None and not _is_principal(member):
            await self._directory.upsert(member["name"], member["profile"])

        existing_token = await store.get(f"instance:{member['name']}:{instance_id}")
        if isinstance(existing_token, str):
            async with self._keys.acquire(f"session:{existing_token}"):
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
            "delivery_history": history_form,
            "expires_at": format_timestamp(expires),
            "lease_ids": [],
        }
        if token_record is not None:
            session["join_token"] = token_record["token"]
            if token_record.get("single_use"):
                await auth_mod.mark_join_token_used(store, token_record)
        await self._save_session(session)
        return self._join_result(session, member)

    async def disconnect(self, session_token: str) -> None:
        """Close this Session. The Membership and its Mailbox remain."""
        async with self._keys.acquire(f"session:{session_token}"):
            session = await self._require_session(session_token)
            _, now_ts = self._now_pair()
            await self._release_session_leases(session, now_ts)
            await self._delete_session(session)

    async def heartbeat(self, session_token: str) -> dict[str, Any]:
        """Prove the Client still holds its Session and extend expiry."""
        async with self._keys.acquire(f"session:{session_token}"):
            session = await self._require_session(session_token)
            now = utc_now()
            session["expires_at"] = format_timestamp(
                now + timedelta(seconds=self.session_ttl_seconds)
            )
            await self._save_session(session)
            return HeartbeatResult(session_expires_at=session["expires_at"])

    async def issue_join_token(
        self,
        *,
        agent_did: str | None = None,
        name: str | None = None,
        ttl_seconds: float | None = None,
        single_use: bool = False,
    ) -> auth_mod.JoinToken:
        """Issue a join token scoped to this Team.

        Bind ``agent_did``, ``name``, or both so a leaked token cannot be
        used by a different Agent. Omit both for an invite that any
        proving Agent can consume.

            issued = await team.issue_join_token(
                name="writer", agent_did=writer.agent_did
            )
            await writer.join(url, join_token=issued["token"])
        """
        store = self._ensure_started()
        canonical_name = None
        if name is not None:
            canonical_name = parse_agent_name(name)
            if canonical_name is None:
                _fail("invalid_request", "Agent name is invalid")
        if agent_did is not None:
            try:
                agent_did = require_did(agent_did)
            except ValueError:
                _fail("invalid_request", "agent_did must be a did:key identifier")
        ttl = self.join_token_ttl_seconds if ttl_seconds is None else float(ttl_seconds)
        if ttl <= 0:
            _fail("invalid_request", "ttl_seconds must be positive")
        issued = await auth_mod.issue_join_token(
            store,
            self.name,
            agent_did=agent_did,
            name=canonical_name,
            ttl_seconds=ttl,
            single_use=bool(single_use),
        )
        return JoinTokenIssued.model_validate(issued)

    async def revoke_join_token(self, token: str) -> None:
        """Revoke ``token`` and drop every Session created from it.

        A later join with this token fails with ``unauthorized``. Waiting
        sends return ``unauthorized``. Event streams close.
        """
        store = self._ensure_started()
        record = await auth_mod.revoke_join_token_record(store, token)
        if record is None:
            return
        _, now_ts = self._now_pair()
        for session_token in await auth_mod.sessions_for_join_token(store, token):
            async with self._keys.acquire(f"session:{session_token}"):
                session = await self._get_session(session_token)
                if session is None:
                    continue
                await self._release_session_leases(session, now_ts)
                await self._delete_session(session)

    async def remove_membership(self, name: str) -> None:
        """Remove a Membership and drop every Session it holds.

        This is the kill switch. Waiting sends return ``unauthorized``.
        Held leases stop being completable. Join tokens bound to the
        name or DID are revoked.
        """
        canonical = parse_agent_name(name)
        if canonical is None:
            _fail("invalid_request", "Agent name is invalid")
        if canonical == OPERATOR_NAME:
            _fail("forbidden", "The operator Membership cannot be removed")
        store = self._ensure_started()
        async with self._keys.acquire(f"member:{canonical}"):
            member = await self._get_member(canonical)
            if member is None:
                _fail("not_found", "Membership was not found")
            _, now_ts = self._now_pair()
            for session_token in await self._session_tokens_for(canonical):
                async with self._keys.acquire(f"session:{session_token}"):
                    session = await self._get_session(session_token)
                    if session is None:
                        continue
                    await self._release_session_leases(session, now_ts)
                    await self._delete_session(session)
            for token in await auth_mod.tokens_bound_to_member(
                store, name=canonical, agent_did=member.get("agent_did")
            ):
                await auth_mod.revoke_join_token_record(store, token)
                for session_token in await auth_mod.sessions_for_join_token(
                    store, token
                ):
                    async with self._keys.acquire(f"session:{session_token}"):
                        session = await self._get_session(session_token)
                        if session is None:
                            continue
                        await self._release_session_leases(session, now_ts)
                        await self._delete_session(session)
            await store.delete(f"member:{canonical}")
            await store.set_remove("members", canonical)
            agent_did = member.get("agent_did")
            if isinstance(agent_did, str):
                await store.delete(f"did:{agent_did}")
            if self._directory is not None:
                await self._directory.drop(canonical)

    async def membership_attestation(self, name: str) -> Optional[str]:
        """Return the stored membership attestation JWT for ``name``, if any."""
        canonical = parse_agent_name(name)
        if canonical is None:
            _fail("invalid_request", "Agent name is invalid")
        member = await self._get_member(canonical)
        if member is None:
            _fail("not_found", "Membership was not found")
        token = member.get("attestation")
        return token if isinstance(token, str) else None

    async def _reserve_operator(self) -> None:
        """Bind the reserved ``operator`` name as a principal Membership."""
        store = self._ensure_started()
        record = await store.get("team:operator")
        if isinstance(record, dict) and record.get("private_key"):
            identity = AgentIdentity.from_dict(record)
            instance_id = record.get("instance_id")
            if not isinstance(instance_id, str):
                instance_id = new_uuid()
                payload = dict(record)
                payload["instance_id"] = instance_id
                await store.put("team:operator", payload)
        else:
            identity = AgentIdentity.create_key_based()
            instance_id = new_uuid()
            payload = identity.to_secret_dict()
            payload["instance_id"] = instance_id
            await store.put("team:operator", payload)
        existing = await self._get_member(OPERATOR_NAME)
        if existing is not None:
            old_did = existing.get("agent_did")
            if isinstance(old_did, str) and old_did != identity.did:
                await store.delete(f"did:{old_did}")
            if self._directory is not None:
                await self._directory.drop(OPERATOR_NAME)
        address = f"{OPERATOR_NAME}@{self.name}"
        await mailbox_mod.drop_mailbox(store, address)
        await self._save_member(
            {
                "name": OPERATOR_NAME,
                "address": address,
                "agent_did": identity.did,
                "principal": True,
            }
        )

    async def _open_operator_session(self) -> str:
        """Create or replace the loopback operator Session."""
        store = self._ensure_started()
        member = await self._get_member(OPERATOR_NAME)
        if member is None or not _is_principal(member):
            await self._reserve_operator()
            member = await self._get_member(OPERATOR_NAME)
        if member is None:
            _fail("internal", "operator Membership was not reserved")
        record = await store.get("team:operator")
        instance_id = new_uuid()
        if isinstance(record, dict) and isinstance(record.get("instance_id"), str):
            instance_id = record["instance_id"]
        now, now_ts = self._now_pair()
        existing_token = await store.get(f"instance:{OPERATOR_NAME}:{instance_id}")
        if isinstance(existing_token, str):
            async with self._keys.acquire(f"session:{existing_token}"):
                old = await self._get_session(existing_token)
                if old is not None:
                    await self._release_session_leases(old, now_ts)
                    await self._delete_session(old)
        expires = now + timedelta(seconds=self.session_ttl_seconds)
        session = {
            "token": secrets.token_urlsafe(32),
            "membership_name": member["name"],
            "address": member["address"],
            "agent_did": member["agent_did"],
            "instance_id": instance_id,
            "max_in_flight": DEFAULT_MAX_IN_FLIGHT,
            "expires_at": format_timestamp(expires),
            "lease_ids": [],
        }
        await self._save_session(session)
        self._operator_token = str(session["token"])
        return self._operator_token

    async def _ensure_identity(self) -> AgentIdentity:
        store = self._ensure_started()
        record = await store.get("team:identity")
        if isinstance(record, dict) and record.get("private_key"):
            identity = AgentIdentity.from_dict(record)
        else:
            identity = AgentIdentity.create_key_based()
            await store.put("team:identity", identity.to_secret_dict())
        self._identity = identity
        return identity

    # --- send ---

    def _held_wait_ttl(self) -> float:
        return max(60.0, float(self.wait_hold_seconds) * 2)

    async def _acquire_held_wait(self, membership_name: str) -> bool:
        store = self._ensure_started()
        return await store.increment_if_below(
            f"held_waits:{membership_name}",
            self.max_held_waits,
            ttl_seconds=self._held_wait_ttl(),
        )

    async def _release_held_wait(self, membership_name: str) -> None:
        store = self._ensure_started()
        await store.decrement_floor(
            f"held_waits:{membership_name}",
            ttl_seconds=self._held_wait_ttl(),
        )

    # Session transport. HTTP, MCP, and in-process Session call these by name.

    async def send(
        self, session_token: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Accept one request or event for one recipient in this Team.

        ``collect=wait`` holds until the Ticket is terminal or
        ``wait_hold_seconds`` elapses, then returns the current Ticket.
        """
        try:
            parsed_send = parse_send_request(request)
        except ValueError as exc:
            _fail("invalid_request", str(exc))
        request = dump_public(parsed_send)
        waiter: asyncio.Event | None = None
        ticket_id: str | None = None
        deadline_dt = None
        hold = {"acquired": False, "name": ""}
        try:
            async with self._keys.acquire(f"session:{session_token}"):
                result, wait_for = await self._send_locked(session_token, request, hold)
            if wait_for is not None:
                ticket_id, deadline_dt = wait_for
                waiter = self._register_waiter(ticket_id)
                self._register_session_wake(session_token, waiter)
            if waiter is not None and ticket_id is not None and deadline_dt is not None:
                try:
                    ticket = await self._wait_until_terminal(
                        session_token, ticket_id, deadline_dt, waiter
                    )
                    result = dict(result)
                    result["ticket"] = ticket
                finally:
                    self._drop_waiter(ticket_id, waiter)
                    self._drop_session_wake(session_token, waiter)
            try:
                return parse_send_result(result)
            except ValueError as exc:
                _fail("internal", str(exc))
        finally:
            if hold["acquired"] and hold["name"]:
                await self._release_held_wait(hold["name"])

    async def _send_locked(
        self,
        session_token: str,
        request: Mapping[str, Any],
        hold: dict[str, Any],
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
        if kind == "request":
            if collect is None or deadline_raw is None:
                _fail(
                    "invalid_request",
                    "a request needs collect and a future deadline",
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
        if recipient_member is None or _is_principal(recipient_member):
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
        send_key = f"send:{message_id}"
        membership_name = session["membership_name"]

        existing_send = await store.get(send_key)
        created_send = False
        if existing_send is not None:
            if existing_send.get("sender") != sender:
                _fail("id_conflict", "Message id is already used")
            if existing_send.get("hash") != request_hash:
                _fail("id_conflict", "Message id is already used with different data")
            result = existing_send.get("result")
            if isinstance(result, dict):
                result = dict(result)
                if result.get("status") == "ticketed":
                    ticket = await self._expire_ticket_if_due(message_id)
                    if ticket is not None:
                        result["ticket"] = ticket
                    if (
                        collect == "wait"
                        and ticket is not None
                        and ticket["state"] == "open"
                    ):
                        if await self._hold_wait_slot(
                            collect, membership_name, hold, required=False
                        ):
                            return result, (
                                message_id,
                                parse_timestamp(ticket["deadline"]),
                            )
                return result, None
        else:
            created_send = await store.insert(
                send_key,
                {
                    "sender": sender,
                    "hash": request_hash,
                    "collect": collect,
                },
            )
            if not created_send:
                existing_send = await store.get(send_key)
                if existing_send is None or existing_send.get("sender") != sender:
                    _fail("id_conflict", "Message id is already used")
                if existing_send.get("hash") != request_hash:
                    _fail(
                        "id_conflict",
                        "Message id is already used with different data",
                    )
                result = existing_send.get("result")
                if isinstance(result, dict):
                    return dict(result), None

        if collect == "wait":
            if not await self._hold_wait_slot(
                collect, membership_name, hold, required=False
            ):
                if created_send:
                    await store.delete(send_key)
                    _fail(
                        "wait_limit",
                        "this Membership already holds the maximum number of waits",
                    )

        enqueued = await mailbox_mod.enqueue(
            store,
            recipient,
            message_id,
            now_ts,
            max_depth=self.max_mailbox_depth,
        )
        if enqueued == "busy":
            if created_send:
                await store.delete(send_key)
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

        if thread_id is not None:
            await self._append_thread_message(
                thread_id=thread_id,
                message=message,
                sender=sender,
                recipient=recipient,
            )

        await store.insert(f"msg:{message_id}", message)
        self._signal_work(recipient_name)
        await self._record_trace(
            trace_mod.make_event(
                at=now_ts,
                type="accepted",
                trace_id=trace_id,
                actor=sender,
                message_id=message_id,
                parent_id=trace_mod.parent_id_of(message),
                detail={
                    "kind": kind,
                    "sender": sender,
                    "recipient": recipient,
                },
            )
        )

        if deadline_dt is None:
            result = {"status": "accepted", "message": message}
            await store.put(
                send_key,
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
        await tickets_mod.insert_ticket(store, ticket)
        await self._record_trace(
            trace_mod.make_event(
                at=now_ts,
                type="ticket_opened",
                trace_id=trace_id,
                actor=sender,
                message_id=message_id,
                parent_id=trace_mod.parent_id_of(message),
                ticket_id=message_id,
            )
        )
        result = {"status": "ticketed", "message": message, "ticket": ticket}
        await store.put(
            send_key,
            {
                "sender": sender,
                "hash": request_hash,
                "collect": collect,
                "result": result,
            },
        )
        if collect == "wait" and hold.get("acquired"):
            return result, (message_id, deadline_dt)
        return result, None

    async def _hold_wait_slot(
        self,
        collect: Any,
        membership_name: str,
        hold: dict[str, Any],
        *,
        required: bool,
    ) -> bool:
        if collect != "wait" or hold.get("acquired"):
            return bool(hold.get("acquired"))
        if await self._acquire_held_wait(membership_name):
            hold["acquired"] = True
            hold["name"] = membership_name
            return True
        if required:
            _fail(
                "wait_limit",
                "This Membership already holds the maximum number of collect=wait sends",
            )
        return False

    async def _wait_until_terminal(
        self, session_token: str, ticket_id: str, deadline_dt, event: asyncio.Event
    ) -> dict[str, Any]:
        hold_until = utc_now() + timedelta(seconds=self.wait_hold_seconds)
        while True:
            session = await self._get_session(session_token)
            if session is None:
                _fail("unauthorized", "Session is missing or invalid")
            if parse_timestamp(session["expires_at"]) <= utc_now():
                _fail("unauthorized", "Session is missing or invalid")
            ticket = await self._expire_ticket_if_due(ticket_id)
            if ticket is not None and tickets_mod.is_terminal(ticket):
                return ticket
            now = utc_now()
            remaining_deadline = (deadline_dt - now).total_seconds()
            remaining_hold = (hold_until - now).total_seconds()
            remaining = min(remaining_deadline, remaining_hold)
            if remaining <= 0:
                ticket = await self._expire_ticket_if_due(ticket_id)
                if ticket is None:
                    _fail("not_found", "Ticket was not found")
                return ticket
            try:
                await asyncio.wait_for(event.wait(), timeout=remaining)
                event.clear()
            except asyncio.TimeoutError:
                ticket = await self._expire_ticket_if_due(ticket_id)
                if ticket is None:
                    _fail("not_found", "Ticket was not found")
                return ticket

    # --- lease / complete / reply ---

    async def lease(self, session_token: str, max_items: int = 1) -> dict[str, Any]:
        """Pull available work from the calling Membership's Mailbox."""
        async with self._keys.acquire(f"session:{session_token}"):
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
            active = [
                lease_id
                for lease_id in session.get("lease_ids") or []
                if await self._lease_still_active(lease_id, now)
            ]
            session["lease_ids"] = active
            room = max(0, int(session["max_in_flight"]) - len(active))
            take = min(n, room)
            deliveries: list[dict[str, Any]] = []
            ready = await mailbox_mod.ready_ids(
                store, address, now, limit=max(take * 3, take)
            )
            history_form = session.get("delivery_history") or "bodies"
            for message_id in ready:
                if take <= 0:
                    break
                message = await store.get(f"msg:{message_id}")
                if message is None:
                    await mailbox_mod.drop_item(store, address, message_id)
                    continue
                if message.get("kind") == "request":
                    ticket = await self._expire_ticket_if_due(message["id"])
                    if ticket is None or ticket["state"] != "open":
                        await mailbox_mod.drop_item(store, address, message_id)
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
                expires_at = format_timestamp(lease_until)
                item = await mailbox_mod.claim(
                    store,
                    address,
                    message_id,
                    lease_id,
                    expires_at,
                    now,
                    now_ts,
                )
                if item is None:
                    continue
                attempt = int(item.get("attempt") or 1)
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
                payload = await self._delivery_payload(
                    message, history_form=str(history_form)
                )
                deliveries.append(
                    {
                        "lease_id": lease_id,
                        "lease_expires_at": expires_at,
                        "attempt": attempt,
                        "message": message,
                        **payload,
                    }
                )
                take -= 1
                await self._record_trace(
                    trace_mod.make_event(
                        at=now_ts,
                        type="leased",
                        trace_id=str(message["trace_id"]),
                        actor=address,
                        message_id=message["id"],
                        parent_id=trace_mod.parent_id_of(message),
                        ticket_id=(message["id"] if message.get("deadline") else None),
                        detail={"attempt": attempt},
                    )
                )
            await self._save_session(session)
            try:
                return parse_lease_result({"deliveries": deliveries})
            except ValueError as exc:
                _fail("internal", str(exc))

    async def _lease_still_active(self, lease_id: str, now) -> bool:
        store = self._ensure_started()
        record = await mailbox_mod.get_lease(store, lease_id)
        if record is None:
            return False
        return mailbox_mod.lease_is_active(record, now)

    async def _thread_messages(self, thread_id: str) -> list[dict[str, Any]]:
        store = self._ensure_started()
        thread = await threads_mod.load_thread(store, thread_id)
        if thread is None:
            return []
        messages: list[dict[str, Any]] = []
        for message_id in thread.get("message_ids") or []:
            stored = await store.get(f"msg:{message_id}")
            if stored is not None:
                messages.append(stored)
        return messages

    async def _delivery_payload(
        self, message: dict[str, Any], *, history_form: str
    ) -> dict[str, Any]:
        thread_id = message.get("thread_id")
        if not thread_id:
            payload: dict[str, Any] = {"history": [], "history_complete": True}
            if history_form == "ids":
                payload["history_ids"] = []
            return payload
        messages = await self._thread_messages(str(thread_id))
        if history_form == "ids":
            ids, complete = threads_mod.history_id_window(
                messages,
                delivered_id=message["id"],
                limit=self.delivery_history_limit,
            )
            return {
                "history": [],
                "history_ids": ids,
                "history_complete": complete,
            }
        history, complete = threads_mod.history_window(
            messages,
            delivered_id=message["id"],
            limit=self.delivery_history_limit,
            max_bytes=self.max_message_bytes,
        )
        return {"history": history, "history_complete": complete}

    async def complete(self, session_token: str, lease_id: str) -> dict[str, Any]:
        """Finish a Delivery without a response Message.

        An event just ends. A request is declined: the Ticket becomes
        ``declined``, which is not a failure.
        """
        async with self._keys.acquire(f"session:{session_token}"):
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
                return CompleteResult.model_validate(existing["result"])
            now, now_ts = self._now_pair()
            message = await store.get(f"msg:{lease['message_id']}")
            ticket = None
            if message and message.get("kind") == "request":
                ticket = await self._expire_ticket_if_due(message["id"])
                if ticket is not None and tickets_mod.is_terminal(ticket):
                    _fail("ticket_closed", "Ticket is already terminal")
            if not mailbox_mod.lease_is_active(lease, now):
                _fail("lease_expired", "Delivery lease is no longer active")
            result: dict[str, Any] = {}
            if ticket is not None and ticket["state"] == "open":
                record = await tickets_mod.load_ticket_record(store, ticket["id"])
                declined = tickets_mod.mark_declined(dict(ticket), now_ts)
                if record is not None and await tickets_mod.cas_ticket(
                    store,
                    declined,
                    record.version,
                    retention_seconds=self.terminal_ticket_retention_seconds,
                ):
                    ticket = declined
                    result["ticket"] = ticket
                    self._notify(ticket["id"])
                else:
                    current = await tickets_mod.load_ticket(store, ticket["id"])
                    if current is not None and tickets_mod.is_terminal(current):
                        _fail("ticket_closed", "Ticket is already terminal")
                    ticket = current or ticket
                    result["ticket"] = ticket
                    self._notify(ticket["id"])
            await self._finish_delivery(session, lease, now_ts)
            await store.put(f"complete:{lease_id}", {"result": result})
            if isinstance(message, dict) and message.get("trace_id"):
                detail: dict[str, Any] = {}
                if ticket is not None and ticket.get("state") == "declined":
                    detail["declined"] = True
                await self._record_trace(
                    trace_mod.make_event(
                        at=now_ts,
                        type="completed",
                        trace_id=str(message["trace_id"]),
                        actor=session["address"],
                        message_id=str(lease["message_id"]),
                        parent_id=trace_mod.parent_id_of(message),
                        ticket_id=ticket["id"] if ticket is not None else None,
                        detail=detail,
                    )
                )
            return CompleteResult.model_validate(result)

    async def reply(
        self, session_token: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Finish a reply-expected Delivery with content or an error."""
        try:
            parsed_reply = parse_reply_request(request)
        except ValueError as exc:
            _fail("invalid_request", str(exc))
        request = dump_public(parsed_reply)
        async with self._keys.acquire(f"session:{session_token}"):
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
            if message is None or message.get("kind") != "request":
                _fail(
                    "invalid_request",
                    "reply is only valid for a request",
                )
            ticket = await self._expire_ticket_if_due(message["id"])
            if ticket is not None and tickets_mod.is_terminal(ticket):
                if (
                    mailbox_mod.lease_is_active(lease, now)
                    or lease.get("membership_name") == session["membership_name"]
                ):
                    record = await tickets_mod.load_ticket_record(store, ticket["id"])
                    if record is not None:
                        late = tickets_mod.observe_late_reply(
                            dict(record.value), now_ts
                        )
                        await tickets_mod.cas_ticket(store, late, record.version)
                _fail("ticket_closed", "Ticket is already terminal")
            if not mailbox_mod.lease_is_active(lease, now):
                _fail("lease_expired", "Delivery lease is no longer active")
            if ticket is None or ticket["state"] != "open":
                _fail("ticket_closed", "Ticket is already terminal")

            if outcome == "failed":
                reply_message: dict[str, Any] = {
                    "id": reply_id,
                    "sender": session["address"],
                    "recipient": message["sender"],
                    "kind": "error",
                    "error": self._validate_error_object(payload["error"]),
                    "created_at": now_ts,
                    "trace_id": message["trace_id"],
                    "parent_id": message["id"],
                }
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
                await self._append_thread_message(
                    thread_id=message["thread_id"],
                    message=reply_message,
                    sender=reply_message["sender"],
                    recipient=reply_message["recipient"],
                )
            if outcome == "failed":
                next_ticket = tickets_mod.mark_failed(
                    dict(ticket), reply_message["error"], now_ts
                )
            else:
                next_ticket = tickets_mod.mark_completed(
                    dict(ticket), reply_message, now_ts
                )
            record = await tickets_mod.load_ticket_record(store, ticket["id"])
            if record is None or record.value.get("state") != "open":
                _fail("ticket_closed", "Ticket is already terminal")
            inserted_reply = await store.insert(f"msg:{reply_id}", reply_message)
            if not inserted_reply:
                _fail("id_conflict", "Message id is already used")
            if not await tickets_mod.cas_ticket(
                store,
                next_ticket,
                record.version,
                retention_seconds=self.terminal_ticket_retention_seconds,
            ):
                current = await tickets_mod.load_ticket(store, ticket["id"])
                if current is not None and tickets_mod.is_terminal(current):
                    late = tickets_mod.observe_late_reply(dict(current), now_ts)
                    late_rec = await tickets_mod.load_ticket_record(store, ticket["id"])
                    if late_rec is not None:
                        await tickets_mod.cas_ticket(store, late, late_rec.version)
                _fail("ticket_closed", "Ticket is already terminal")
            ticket = next_ticket
            await self._finish_delivery(session, lease, now_ts)
            result = {"ticket": ticket}
            await store.put(
                f"reply:{reply_id}",
                {"sender": session["address"], "hash": reply_hash, "result": result},
            )
            self._notify(ticket["id"])
            await self._record_trace(
                trace_mod.make_event(
                    at=now_ts,
                    type="replied",
                    trace_id=str(message["trace_id"]),
                    actor=session["address"],
                    message_id=message["id"],
                    parent_id=trace_mod.parent_id_of(message),
                    ticket_id=ticket["id"],
                    detail={
                        "outcome": ("failed" if outcome == "failed" else "completed"),
                        "reply_id": reply_id,
                    },
                )
            )
            return ReplyResult.model_validate(result)

    def _validate_error_object(self, error: Mapping[str, Any]) -> dict[str, Any]:
        try:
            return ErrorObject.model_validate(error).to_public_dict()
        except ValidationError as exc:
            _fail("invalid_request", validation_message(exc))

    async def _finish_delivery(
        self, session: dict[str, Any], lease: dict[str, Any], now_ts: str
    ) -> None:
        store = self._ensure_started()
        await mailbox_mod.acknowledge(
            store, lease["address"], lease["message_id"], lease["lease_id"]
        )
        await mailbox_mod.deactivate_lease(store, lease["lease_id"])
        lease_ids = list(session.get("lease_ids") or [])
        if lease["lease_id"] in lease_ids:
            lease_ids.remove(lease["lease_id"])
        session["lease_ids"] = lease_ids
        await self._save_session(session)

    async def get_result(self, session_token: str, ticket_id: str) -> dict[str, Any]:
        """Return the Ticket owned by the calling Membership."""
        session = await self._require_session(session_token)
        try:
            ticket_id = require_uuid(ticket_id, field="ticket_id")
        except ValueError:
            _fail("invalid_request", "ticket_id must be a UUID")
        ticket = await self._expire_ticket_if_due(ticket_id)
        if ticket is None or ticket.get("requester") != session["address"]:
            _fail("not_found", "Ticket was not found")
        return parse_ticket(ticket)

    async def get_history(
        self,
        session_token: str,
        thread_id: str,
        *,
        before: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return one page of a Thread's retained history, ordered by ``seq``.

        Omit ``before`` for the newest page. A UUID that is not in the
        retained transcript, including one retention has removed, returns
        that newest page. A non-UUID ``before`` is ``invalid_request``.
        """
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
        try:
            return parse_history_result({"messages": page, "has_more": has_more})
        except ValueError as exc:
            _fail("internal", str(exc))

    async def find(
        self,
        session_token: str,
        query: str,
        *,
        limit: int | None = None,
        detail: str = "summary",
    ) -> dict[str, Any]:
        """Search this Team's Directory. The caller is excluded from results.

        Omit ``limit`` to receive every other member, ordered by relevance,
        at most 100. Pass ``detail="full"`` to include each Profile.

            found = await team.find(token, "someone who can review a contract")
            found["matches"][0]["address"]
        """
        session = await self._require_session(session_token)
        if not isinstance(query, str) or not query.strip() or len(query) > 1000:
            _fail(
                "invalid_request",
                "query must be 1 to 1000 non-whitespace characters",
            )
        cap: int | None
        if limit is None:
            cap = None
        else:
            try:
                cap = int(limit)
            except (TypeError, ValueError):
                _fail("invalid_request", "limit must be an integer")
            if cap < 1 or cap > MAX_FIND_LIMIT:
                _fail(
                    "invalid_request",
                    f"limit must be between 1 and {MAX_FIND_LIMIT}",
                )
        if detail not in {"summary", "full"}:
            _fail("invalid_request", "detail must be summary or full")
        store = self._ensure_started()
        names = await store.set_members("members")
        members: list[dict[str, Any]] = []
        for name in names:
            member = await self._get_member(name)
            if member is not None and not _is_principal(member):
                members.append(member)
        exclude = session["address"]
        directory = self._directory
        if directory is None:
            _fail("unavailable", "Team has not been started")
        return await directory.search(
            query,
            members,
            exclude_address=exclude,
            limit=cap,
            detail=detail,
        )

    async def get_profile(self, session_token: str, address: str) -> dict[str, Any]:
        """Return one Directory entry by local or same-Team Address."""
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
        if member is None or _is_principal(member) or not member.get("profile"):
            _fail("not_found", "Membership was not found")
        return DirectoryEntry.model_validate(
            {
                "address": member["address"],
                "agent_did": member["agent_did"],
                "profile": member["profile"],
            }
        )

    async def status(self, session_token: str) -> dict[str, Any]:
        """Return members, online state, and Agent Mailbox depths.

        Operator only. Principal rows omit Mailbox and Ticket counts.
        ``online`` is read from stored Sessions, so a durable restart
        still reports a live Membership as online.

            token = await team.ensure_operator_session()
            snapshot = await team.status(token)
            snapshot["members"][0]["kind"]
        """
        await self._require_operator(session_token)
        store = self._ensure_started()
        now = utc_now()
        names = await store.set_members("members")
        open_ids = await store.set_members(tickets_mod.OPEN_TICKETS_SET)
        by_recipient: dict[str, int] = {}
        open_count = 0
        for ticket_id in open_ids:
            ticket = await tickets_mod.load_ticket(store, ticket_id)
            if ticket is None or ticket.get("state") != "open":
                continue
            open_count += 1
            recipient = str(ticket["recipient"])
            by_recipient[recipient] = by_recipient.get(recipient, 0) + 1
        members: list[dict[str, Any]] = []
        for name in names:
            member = await self._get_member(name)
            if member is None:
                continue
            address = str(member["address"])
            online = await self._member_is_online(str(member["name"]), now)
            if _is_principal(member):
                members.append(
                    {
                        "kind": "principal",
                        "name": member["name"],
                        "address": address,
                        "online": online,
                    }
                )
                continue
            members.append(
                {
                    "kind": "agent",
                    "name": member["name"],
                    "address": address,
                    "online": online,
                    "mailbox_depth": await mailbox_mod.depth(store, address),
                    "open_tickets": by_recipient.get(address, 0),
                }
            )
        members.sort(key=lambda row: str(row["address"]))
        result: dict[str, Any] = {
            "team_name": self.name,
            "persistence": self.persistence,
            "open_tickets": open_count,
            "members": members,
        }
        if self._http_url:
            result["origin"] = self._http_url
        return StatusResult.model_validate(result)

    async def get_trace(self, session_token: str, trace_id: str) -> dict[str, Any]:
        """Return the recorded timeline for one ``trace_id``.

        The operator receives every event. A member receives only events
        that name that Membership. Anyone else gets ``not_found``.

            token = await team.ensure_operator_session()
            timeline = await team.get_trace(token, message["trace_id"])
        """
        session = await self._require_session(session_token)
        try:
            trace_id = require_uuid(trace_id, field="trace_id")
        except ValueError:
            _fail("invalid_request", "trace_id must be a UUID")
        store = self._ensure_started()
        events = await trace_mod.load_events(store, trace_id)
        if not events:
            _fail("not_found", "Trace was not found")
        if session["membership_name"] != OPERATOR_NAME:
            address = str(session["address"])
            events = await trace_mod.visible_events(store, events, address)
            if not events:
                _fail("not_found", "Trace was not found")
        return TraceResult.model_validate({"trace_id": trace_id, "events": events})

    async def subscribe_trace_events(self, session_token: str) -> asyncio.Queue:
        """Attach a watch queue for new Trace events. Operator only."""
        await self._require_operator(session_token)
        queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._trace_subscribers.append((session_token, queue))
        return queue

    async def unsubscribe_trace_events(
        self, session_token: str, queue: asyncio.Queue
    ) -> None:
        """Detach a queue previously returned by ``subscribe_trace_events``."""
        self._trace_subscribers = [
            item
            for item in self._trace_subscribers
            if not (item[0] == session_token and item[1] is queue)
        ]

    async def _expire_ticket_if_due(self, ticket_id: str) -> Optional[dict[str, Any]]:
        store = self._ensure_started()
        record = await tickets_mod.load_ticket_record(store, ticket_id)
        if record is None:
            return None
        ticket = dict(record.value)
        now, now_ts = self._now_pair()
        if ticket["state"] == "open" and tickets_mod.deadline_passed(ticket, now):
            expired = tickets_mod.mark_expired(ticket, now_ts)
            if await tickets_mod.cas_ticket(
                store,
                expired,
                record.version,
                retention_seconds=self.terminal_ticket_retention_seconds,
            ):
                await mailbox_mod.drop_item(store, str(expired["recipient"]), ticket_id)
                self._notify(expired["id"])
                message = await store.get(f"msg:{ticket_id}")
                if isinstance(message, dict) and message.get("trace_id"):
                    await self._record_trace(
                        trace_mod.make_event(
                            at=now_ts,
                            type="ticket_closed",
                            trace_id=str(message["trace_id"]),
                            actor=str(expired["recipient"]),
                            message_id=ticket_id,
                            parent_id=trace_mod.parent_id_of(message),
                            ticket_id=ticket_id,
                            detail={"state": "expired"},
                        )
                    )
                thread_id = expired.get("thread_id")
                if isinstance(thread_id, str):
                    await self._trim_thread(thread_id)
                return expired
            return await tickets_mod.load_ticket(store, ticket_id)
        return ticket

    async def _sweep_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.sweep_interval_seconds)
                try:
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
        await auth_mod.sweep_join_state(store, now=now)
        for token in await expiry_mod.due(store, expiry_mod.SESSIONS, now):
            async with self._keys.acquire(f"session:{token}"):
                session = await self._get_session(token)
                if session is None:
                    await expiry_mod.cancel(store, expiry_mod.SESSIONS, token)
                    continue
                if parse_timestamp(session["expires_at"]) > now:
                    await expiry_mod.schedule(
                        store, expiry_mod.SESSIONS, token, session["expires_at"]
                    )
                    continue
                await self._release_session_leases(session, now_ts)
                await self._delete_session(session)
        for lease_id in await expiry_mod.due(store, expiry_mod.LEASES, now):
            lease = await mailbox_mod.get_lease(store, lease_id)
            if lease is None:
                await expiry_mod.cancel(store, expiry_mod.LEASES, lease_id)
                continue
            if mailbox_mod.lease_is_active(lease, now):
                await expiry_mod.schedule(
                    store, expiry_mod.LEASES, lease_id, lease["expires_at"]
                )
                continue
            await mailbox_mod.return_item(
                store, lease["address"], lease["message_id"], lease_id, now_ts
            )
            self._signal_work(lease["membership_name"])
            await mailbox_mod.deactivate_lease(store, lease_id)
        for ticket_id in await expiry_mod.due(store, expiry_mod.OPEN_TICKETS, now):
            ticket = await self._expire_ticket_if_due(ticket_id)
            if ticket is None or ticket.get("state") != "open":
                await expiry_mod.cancel(store, expiry_mod.OPEN_TICKETS, ticket_id)
            elif not tickets_mod.deadline_passed(ticket, now):
                await expiry_mod.schedule(
                    store, expiry_mod.OPEN_TICKETS, ticket_id, ticket["deadline"]
                )
        for ticket_id in await expiry_mod.due(store, expiry_mod.TERMINAL_TICKETS, now):
            ticket = await tickets_mod.load_ticket(store, ticket_id)
            if ticket is None:
                await expiry_mod.cancel(store, expiry_mod.TERMINAL_TICKETS, ticket_id)
                continue
            if ticket["state"] == "open":
                continue
            thread_id = ticket.get("thread_id")
            await tickets_mod.delete_ticket(store, ticket_id)
            if isinstance(thread_id, str):
                await self._trim_thread(thread_id)


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
