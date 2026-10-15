"""Create an agent, join a Team, and handle deliveries."""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Optional, Protocol, TypeGuard, runtime_checkable

from agentconnect.agent.context import Context
from agentconnect.agent.errors import SessionError
from agentconnect.agent.identity import load_or_create_identity
from agentconnect.agent.session import Session
from agentconnect.agent.tools import TeamTools
from agentconnect.core.address import parse_agent_name
from agentconnect.core.base import JsonValue
from agentconnect.core.directory import DirectoryEntry, FindResult
from agentconnect.core.identity import AgentIdentity
from agentconnect.core.message import MailboxMessage
from agentconnect.core.operations import (
    AcceptedSendResult,
    HistoryResult,
    JoinTokenIssued,
)
from agentconnect.transport.runtime import RuntimeOperations
from agentconnect.core.primitives import CollectMode, DeliveryHistoryForm
from agentconnect.core.profile import AgentProfile
from agentconnect.core.ticket import Ticket


@runtime_checkable
class _EmbeddedAdmission(RuntimeOperations, Protocol):
    @property
    def require_join_auth(self) -> bool: ...

    async def issue_join_token(
        self, *, name: str | None = None, agent_did: str | None = None
    ) -> JoinTokenIssued: ...


logger = logging.getLogger(__name__)


class BaseAgent:
    """Connect an independent agent to a Team and handle incoming work.

    Implement `handle` in a subclass to use your harness. Call `join`
    before sending work or finding teammates, and `leave` to close the
    connection. Leaving preserves the agent's membership and Tickets.
    """

    profile: AgentProfile
    """Profile published to the Directory at join."""

    name: str
    """Agent name, unique in the Team."""

    identity: AgentIdentity
    """Key for this Agent. Saving this key, or reusing `identity_path`, keeps the DID."""

    agent_did: str
    """DID taken from `identity`."""

    join_token: Optional[str]
    """Token from the constructor, `AGENTCONNECT_JOIN_TOKEN`, or the latest `join`."""

    instance_id: str
    """UUID for this running copy. Two copies must not share one."""

    max_in_flight: int
    """How many Deliveries this Session handles at once, including deferred replies."""

    delivery_history: DeliveryHistoryForm
    """`bodies` includes earlier Message bodies. `ids` includes only their ids."""

    _session_ttl_hint: float

    def __init__(
        self,
        name: str,
        *,
        profile: AgentProfile | Mapping[str, object] | None = None,
        identity: Optional[AgentIdentity] = None,
        identity_path: Optional[str | Path] = None,
        instance_id: Optional[str] = None,
        max_in_flight: int = 1,
        delivery_history: DeliveryHistoryForm = "bodies",
        join_token: Optional[str] = None,
    ) -> None:
        """Create an Agent that has not joined a Team.

        Args:
            name: Agent name, unique in the Team.
            profile: `AgentProfile`, or a mapping with the same fields.
                When omitted, a class attribute named `profile` is used.
                When both are omitted, join publishes a generic summary
                and a skill named `generic`.
            identity: Key to reuse. A valid `did:key` on it is kept.
                Otherwise the SDK mints one. Do not also pass
                `identity_path`. Load a saved key with `load_identity`
                and pass it here when you store the file yourself.
            identity_path: JSON file for the Agent key. The file is loaded
                when it exists, and created when it does not. The same
                path keeps the same DID across restarts.
            instance_id: UUID for this running copy. Generated when omitted.
                Two copies must not share one.
            max_in_flight: How many Deliveries this Session handles at
                once, from 1 to 100. Deferred replies that still hold a
                lease count toward this limit.
            delivery_history: `bodies` puts earlier Messages on each
                Delivery. `ids` puts only their ids. Page the bodies
                with `get_history`.
            join_token: Token from the operator. Also read from
                `AGENTCONNECT_JOIN_TOKEN` when this argument is omitted.
                A URL join to a Team with `require_join_auth=True` needs
                this token. `join` on that Team object mints one, bound
                to this name and DID, when no token is configured.

        Raises:
            ValueError: `name` is not a valid Agent name, both `identity`
                and `identity_path` were passed, `instance_id` is not a
                UUID, or `max_in_flight` or `delivery_history` is invalid.
        """
        canonical = parse_agent_name(name)
        if canonical is None:
            raise ValueError("name is not a valid Agent name")
        self._agent_name = canonical
        self.name = canonical
        if identity is not None and identity_path is not None:
            raise ValueError("pass identity or identity_path, not both")
        if identity_path is not None:
            self.identity = load_or_create_identity(identity_path)
        else:
            self.identity = identity or AgentIdentity.create_key_based()
        try:
            if not self.identity.matches_did():
                from agentconnect.core.identity import did_key_from_public_bytes

                self.identity.did = did_key_from_public_bytes(
                    self.identity.public_bytes()
                )
        except Exception as exc:
            raise ValueError("identity must be an Ed25519 did:key") from exc
        self.agent_did = self.identity.did
        env_token = os.environ.get("AGENTCONNECT_JOIN_TOKEN")
        self.join_token = join_token if join_token is not None else env_token
        self._join_token_explicit = self.join_token is not None
        self._issued_team_id: int | None = None
        self.profile = _discovery_profile(
            profile if profile is not None else _class_profile(type(self)),
            self._agent_name,
        )
        if instance_id is None:
            self.instance_id = str(uuid.uuid4())
        else:
            try:
                self.instance_id = str(uuid.UUID(str(instance_id)))
            except ValueError as exc:
                raise ValueError("instance_id must be a UUID") from exc
        try:
            in_flight = int(max_in_flight)
        except (TypeError, ValueError) as exc:
            raise ValueError("max_in_flight must be an integer") from exc
        if in_flight < 1 or in_flight > 100:
            raise ValueError("max_in_flight must be between 1 and 100")
        self.max_in_flight = in_flight
        if delivery_history not in {"bodies", "ids"}:
            raise ValueError("delivery_history must be 'bodies' or 'ids'")
        self.delivery_history = delivery_history
        self._session: Optional[Session] = None
        self._session_ttl_hint = 300.0

    @property
    def address(self) -> Optional[str]:
        """Qualified Address after `join`, or `None` before it."""
        if self._session is None:
            return None
        return self._session.address

    @property
    def connected(self) -> bool:
        """True while this copy has a live Session."""
        return self._session is not None and self._session.connected

    async def join(
        self, team_or_url: RuntimeOperations | str, *, join_token: Optional[str] = None
    ) -> "BaseAgent":
        """Join a started Team, or a URL that Team is serving.

        The call retries while the Team is down. After a disconnect, the
        same `instance_id` and the same join token are used again. A
        rejected token is not replaced. Two copies must not share an
        `instance_id`. Joining again closes the current connection first.

        Pass a Team object that has `require_join_auth=True`, and omit
        the token, to mint one bound to this Agent's name and DID.
        That minted token is reused only when joining the same Team
        object again. A different in-process Team drops it, and mints
        another when that Team requires auth. A URL never mints a token.
        A token from the constructor, the environment, or this call is
        kept as given. `Team.issue_join_token` remains the operator call
        for a token you want to hand out.

        Args:
            team_or_url: A started `Team` in this process, or a Runtime
                origin such as `http://127.0.0.1:9000`.
            join_token: Token for this join. Replaces the constructor
                or environment token. A configured token is sent as
                given, including when it is expired or revoked.

        Returns:
            This Agent, now connected.

        Raises:
            SessionError: The Team rejected the join. Read `code`.
                Common codes are `unauthorized` and `name_conflict`.
        """
        if join_token is not None:
            self.join_token = join_token
            self._join_token_explicit = True
            self._issued_team_id = None
        elif not self._join_token_explicit and _in_process_team(team_or_url):
            if self._issued_team_id != id(team_or_url):
                self.join_token = None
                self._issued_team_id = None
                if team_or_url.require_join_auth:
                    issued = await team_or_url.issue_join_token(
                        name=self.name,
                        agent_did=self.agent_did,
                    )
                    self.join_token = issued.token
                    self._issued_team_id = id(team_or_url)
        elif not self._join_token_explicit:
            self.join_token = None
            self._issued_team_id = None
        if self._session is not None:
            await self.leave()
        session = Session(
            self,
            team_or_url,
            instance_id=self.instance_id,
            agent_did=self.agent_did,
            profile=self.profile,
            max_in_flight=self.max_in_flight,
            delivery_history=self.delivery_history,
        )
        self._session = session
        await session.start()
        return self

    async def leave(self) -> None:
        """Close this Session.

        Membership, the Mailbox, and Tickets stay on the Team. Join
        again with the same Membership to call `get_result` for an open
        Ticket. `leave` does not remove the Membership. Use
        `Team.remove_membership` for that.
        """
        session = self._session
        self._session = None
        if session is not None:
            await session.close(disconnect=True)

    async def ask(
        self,
        recipient: str,
        content: JsonValue,
        *,
        deadline_seconds: Optional[float] = None,
        collect: CollectMode = "wait",
        thread_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Mapping[str, JsonValue]] = None,
    ) -> Ticket:
        """Send a request and return a `Ticket`.

        The returned Ticket may still be `open`. Accepted work keeps
        running after this call returns.

        Read `content` only when `state` is `completed`. Call `get_result`
        with `id` while `state` is `open`. A `failed` or `expired` Ticket
        has `error`. A `declined` Ticket has no reply body.

        Args:
            recipient: Local name or same-Team Address, such as `writer`
                or `writer@content-squad`.
            content: The work, as text or JSON.
            deadline_seconds: Work cutoff in seconds. This does not change
                how long `collect="wait"` waits. Omit it outside `handle`
                to use the Team's `work_lifetime_seconds`. Inside
                `handle`, omit it to inherit the parent request deadline.
                The Team rejects a later child deadline.
            collect: `wait` waits until the Ticket is terminal or
                `wait_hold_seconds` elapses. `ticket` returns the current
                Ticket without waiting.
            thread_id: Thread to continue with the same recipient. Omit it
                outside `handle` to leave the request unthreaded. Inside
                `handle`, omit it to continue the current Thread when
                `recipient` is the sender and the Message has a
                `thread_id`. Otherwise a new Thread starts.
            parent_id: Message this request answers. Omit it outside
                `handle` to send with no parent. Inside `handle`, the
                omitted value is the current Message id.
            metadata: JSON object stored on the Message. Omit to store none.

        Returns:
            The current Ticket. It can still be `open`.

        Raises:
            SessionError: The Agent has not joined, or the Team rejected
                the send. Read `code`.

        Examples:
            In an async application, `agent` has joined the Team and
            `release_findings` contains your research notes. Keep the
            Ticket id to collect the same work later.

            ```python
            ticket = await agent.ask(
                "writer",
                {"task": "Draft a release note.", "findings": release_findings},
                collect="ticket",
            )
            if ticket.state == "completed":
                print(ticket.content)
            ```
        """
        return await self._require_session().ask(
            recipient,
            content,
            deadline_seconds=deadline_seconds,
            collect=collect,
            thread_id=thread_id,
            parent_id=parent_id,
            metadata=metadata,
        )

    async def tell(
        self,
        recipient: str,
        content: JsonValue,
        *,
        thread_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Mapping[str, JsonValue]] = None,
    ) -> AcceptedSendResult:
        """Send a notice. No Ticket is created.

        Acceptance means the Team queued the event. It does not mean the
        recipient finished handling it.

        Omit `thread_id` outside `handle` to leave the notice unthreaded.
        Inside `handle`, an omitted `thread_id` follows the same continue
        or start rule as `ask`. Omit `parent_id` outside `handle` to send
        with no parent. Inside `handle`, the omitted value is the current
        Message id.

        Args:
            recipient: Local name or same-Team Address.
            content: The notice, as text or JSON.
            thread_id: Thread to continue with a current participant.
                Omit it outside `handle` for an unthreaded notice. Inside
                `handle`, omit it to follow the same rule as `ask`.
            parent_id: Message this notice answers. Omit it outside
                `handle` to send with no parent. Inside `handle`, the
                omitted value is the current Message id.
            metadata: JSON object stored on the Message. Omit to store none.

        Returns:
            An acknowledgement that the Team accepted the event.

        Raises:
            SessionError: The Agent has not joined, or the Team rejected
                the send. Read `code`.
        """
        return await self._require_session().tell(
            recipient,
            content,
            thread_id=thread_id,
            parent_id=parent_id,
            metadata=metadata,
        )

    async def find(self, query: str, *, limit: int | None = None) -> FindResult:
        """Search this Team's Directory, excluding this Agent.

        Each match is a short card with Address, summary, skill names,
        and Profile tags. Rank is a candidate order, not proof that the
        peer can do the work. Call `get_entry` for one full Profile.

        Args:
            query: Description of the work, in ordinary language.
            limit: Maximum matches, from 1 to 100. Omit it to receive
                every other member, at most 100.

        Returns:
            Ranked matches, best first.

        Raises:
            SessionError: The Agent has not joined.

        Examples:
            In an async application, `agent` has joined the Team and
            `release_findings` contains your research notes. Ask a
            matching teammate for a draft if discovery finds one.

            ```python
            found = await agent.find("someone who can draft from notes")
            if found.matches:
                ticket = await agent.ask(
                    found.matches[0].address,
                    {"task": "Draft a release note.", "findings": release_findings},
                )
                if ticket.state == "completed":
                    print(ticket.content)
            ```
        """
        return await self._require_session().find(query, limit=limit)

    async def get_entry(self, address: str) -> DirectoryEntry:
        """Return the Directory entry for one Membership.

        The entry includes Address, DID, and Profile.

        Args:
            address: Local name or same-Team Address.

        Returns:
            The Directory entry for that Membership.

        Raises:
            SessionError: The Agent has not joined, or no Membership
                has that Address.
        """
        return await self._require_session().get_entry(address)

    async def get_result(self, ticket_id: str) -> Ticket:
        """Return a Ticket this Membership opened.

        The call is repeatable and does not consume the result. When
        `state` is `open`, call again with the same id. Do not send
        another `ask` to collect that work. Read the body with the same
        state checks as `ask`.

        Args:
            ticket_id: `Ticket.id` from `ask`. It equals the request
                Message id.

        Returns:
            The current Ticket. It can still be `open`.

        Raises:
            SessionError: The Agent has not joined, or this Membership
                did not open that Ticket.

        Examples:
            In an async application, `agent` is connected and `pending`
            is a Ticket from an earlier `ask`.

            ```python
            ticket = await agent.get_result(pending.id)
            if ticket.state == "completed":
                print(ticket.content)
            ```
        """
        return await self._require_session().get_result(ticket_id)

    async def get_history(
        self,
        thread_id: str,
        *,
        before: Optional[str] = None,
        limit: int = 50,
    ) -> HistoryResult:
        """Return one page of retained Thread history.

        The first page is the newest. Messages inside a page run from
        oldest to newest. Omit `before` for that newest page. A `before`
        id that the transcript does not contain also returns the newest
        page, even after retention has deleted that id. Only a
        participant can read the Thread.

        Args:
            thread_id: Conversation id from a Ticket or Message.
            before: Return Messages older than this id. Use `next_before`
                from the previous page.
            limit: Page size, from 1 to 200. Defaults to 50.

        Returns:
            One page. Pass `next_before` as `before` when `has_more` is true.

        Raises:
            SessionError: The Agent has not joined, or is not a participant.
        """
        return await self._require_session().get_history(
            thread_id, before=before, limit=limit
        )

    def team_tools(self) -> TeamTools:
        """Return Team tool descriptors for a Python harness.

        The descriptors are `find`, `ask`, `tell`, `get_result`,
        `get_history`, and `get_profiles`. Attach these descriptors
        through your harness's tool interface. Calling `team_tools`
        before `join` is safe; handlers need a live connection.
        `ask` and `get_result` return JSON with `ticket_id`. Read
        `content` only when `state` is `completed`. An MCP client
        connects to `{origin}/mcp`. `agentconnect.agent.tools`
        documents extra `Tool` callables.

        Returns:
            A `TeamTools` sequence.
        """
        return TeamTools(self._require_session)

    async def handle(self, message: MailboxMessage, ctx: Context) -> object:
        """Handle one Delivery. Override this.

        `message` is the delivered request or event. `ctx` is the
        `Context` for this attempt. At-least-once delivery can call
        `handle` more than once for the same Message. `ctx.attempt`
        starts at 1.

        A handler finishes the Delivery in one of four ways:

        - Return a JSON value to reply to a request.
        - Return `None` to decline a request, or to finish an event.
        - Raise to fail a request. The requester sees code
          `handler_failed` and the message `The handler failed.`
          The exception text stays in this process log. An event has
          no Ticket. Raising while handling an event finishes that
          Delivery without a reply.
        - Call `ctx.defer()` and return from `handle` to answer later.
          The return value is not the reply. Finish through `DeferredReply`.

        Args:
            message: The delivered request or event.
            ctx: Facts about this Delivery, plus `ask`, `tell`,
                `get_history`, and `defer`.

        Returns:
            A reply body, or `None` to decline a request or finish an event.
        """
        return None

    def _require_session(self) -> Session:
        if self._session is None or not self._session.session_token:
            raise SessionError("unauthorized", "Agent has not joined a Team")
        return self._session


def _in_process_team(target: RuntimeOperations | str) -> TypeGuard[_EmbeddedAdmission]:
    """Recognize the optional embedded admission capability."""
    return isinstance(target, _EmbeddedAdmission)


def _class_profile(cls: type[BaseAgent]) -> AgentProfile | Mapping[str, object] | None:
    """Return a Profile declared on the Agent class, if any."""
    for klass in cls.__mro__:
        if "profile" not in klass.__dict__:
            continue
        value = klass.__dict__["profile"]
        if isinstance(value, (AgentProfile, Mapping)):
            return value
    return None


def _discovery_profile(
    profile: AgentProfile | Mapping[str, object] | None, name: str
) -> AgentProfile:
    """Return the discovery Profile the Runtime accepts on join."""
    fallback = {
        "summary": f"{name} handles work for this team.",
        "skills": [{"name": "generic", "description": f"Work handled by {name}."}],
    }
    if profile is None:
        return AgentProfile.model_validate(fallback)
    if isinstance(profile, AgentProfile):
        return profile
    return AgentProfile.model_validate(profile)
