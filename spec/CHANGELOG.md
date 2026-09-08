# Specification changelog

This file records changes to the public AgentConnect specification.

The specification is a single pre-1.0 draft, not versioned per package release. Before 1.0 it changes freely with no backward-compatibility guarantee; the priority is a correct, complete contract, and later capability is expected to append. The 1.0 release freezes the contract and starts the compatibility policy.

## Unreleased draft

Working draft of the Team Runtime contract (`1.0.0-draft`).

Defines:

- Agent, Team, Runtime, Client, Membership, Instance, Session, and Mailbox boundaries
- concurrent Instances that share one Membership Mailbox, and a Mailbox that may be partitioned for scale
- Agent names, Team names, canonical Addresses that already admit a remote location, Profiles, and local Directory search
- `find` with no `limit` returns every other member of a small Team, ordered, and caps a large Team at 100
- Skills as natural-language claims with examples and tags, without input or output schemas
- request, event, response, and error Messages, with `trace_id` correlating one causal operation while `thread_id` groups a conversation
- a request always expects a reply, opens a Ticket, and carries a `deadline` on the accepted Message; the send may omit `deadline` and the Runtime stamps a work cutoff
- collection strategy (`wait`, `ticket`, and reserved `callback` and `stream`) on the `send`, not on the Message
- `parent_id` may name an authorized Message from another Thread when the send creates a new Thread; that parent does not grant history of the parent's Thread
- a shared `trace_id` correlates one operation; it does not record which subset of sibling answers a merge consumed
- `heartbeat` extends Session expiry only; Delivery leases are extended by `renew`
- a child request deadline must not be after a request parent's deadline; an omitted child deadline inherits that parent's absolute deadline
- a Thread participant set of one or more Memberships, fixed at creation and seeded from the first Message
- `wait` holds `send` until the Ticket is terminal or `wait_hold_seconds` elapses, then returns the current Ticket without ending accepted work
- an omitted root deadline uses configurable `work_lifetime_seconds`; the stamped value is a cutoff, not a completion estimate
- Runtime `send`, Client `ask`, and MCP `ask` share that bounded hold; none of them polls past it for a terminal Ticket
- `collect=ticket` and an elapsed `wait` hold both return a `TicketedSendResult` whose Ticket may still be `open`
- an accepted `send` replay after the original deadline returns the retained result; new work with a past deadline is `invalid_request`
- reply idempotency includes the target request Message id; `lease_id` authorizes the attempt only
- MCP and Session-bound keyed `ask`/`tell` recover generated Thread and deadline values; changed keyed arguments fail with `id_conflict`
- ordinary HTTP operations use a finite configured timeout; `collect=wait` send may use a longer finite timeout covering `wait_hold_seconds`; the Session event stream may stay open
- an HTTP timeout is `unavailable` and does not claim the Runtime rejected or never accepted the operation; a lost send response retries the same Message id
- foreground Session reconnect while retrying is bounded; background reconnect may continue after that caller returns
- `max_held_waits` caps concurrent held `wait` sends per Membership; past the cap `send` fails with `wait_limit`
- Message idempotency compares a SHA-256 hash of canonical JSON, with `1` / `1.0` / `1e0` equal
- a Mailbox is a lease-based pull port of per-item documents; `max_mailbox_depth` is an exact count of queued plus leased items
- `join` may request Delivery history as Message ids instead of bodies
- pull delivery with exclusive leases, `renew` to extend a lease up to the request deadline, at-least-once handling, and a reported message-size limit
- requester-owned Tickets with five states, including an explicit `declined` when a recipient chooses not to answer
- Ticket and Thread retention that outlasts an open Ticket deadline
- Thread grouping, a delivered history window bounded by count and by `max_message_bytes`, and paged history retrieval with `get_history`
- `get_history` `before` an unknown or evicted Message id returns the newest page
- concurrent Instances sharing one Mailbox, with conversation state in the Thread transcript rather than in a running copy
- embedded and authenticated network joins, with an Instance-aware Session
- Runtime operations and their HTTP mapping, including a typed Session event stream
- MCP tools `find`, `ask`, `tell`, `get_result`, and `get_history`
- MCP roster resource at `agentconnect://team/roster` lists Agent Memberships only
- a Membership that may act is not the same as an Agent that may be hired: a principal has no Profile, Directory entry, or Mailbox, and a `send` naming it fails `not_found`
- the reserved `operator` is a principal; the Runtime reserves the name when it starts; `find` and the roster omit it; it stays visible in `status`
- `status` member rows are a discriminated union on `kind`; a principal omits Mailbox depth and open-Ticket counts
- MCP `ask` uses `collect` (`wait` or `ticket`) with the same meaning as Client `ask`; there is no `wait_seconds`
- loopback MCP and HTTP calls with no Authorization header bind to that shared `operator` identity; the machine is the trust boundary
- over HTTP and MCP, operator authority is the Session; the hosting process may issue and revoke join tokens on the Runtime object without a Session
- `ErrorObject.code` is the closed `ErrorCode` set; an Agent application failure code belongs in `details` of a `handler_failed` error
- `TeamRoster.team_name` is a `TeamName`
- operator operations `status`, `issue_join_token`, and `revoke_join_token`
- `get_trace` reconstructs the timeline for one `trace_id`; a member reads only events that name that Membership, the operator reads any Trace
- HTTP trace watch stream at `GET /traces/events`
- MCP `ask`/`tell` mint a fresh Message id unless the caller supplies `idempotency_key`
- `TraceEvent.parent_id` copies the named Message's parent so a Client can draw the request tree
- Sessions survive a `durable` restart; `status` `online` is read from stored Sessions
- Expiry for Sessions, leases, Tickets, and join credentials is processed from a time-ordered index of due items
- documented TypeScript structures and generated JSON Schema
- send and reply acceptance is one transition: a Mailbox item is not leaseable until its Message (and Ticket, for a request) exist; Message ids are reserved across `send` and `reply`
- each Membership has an immutable identity distinct from its Address and Agent DID; removing a name and admitting another DID creates a new Membership that cannot inherit Tickets, history, Trace visibility, or queued work
- `sender_did` is stamped on every accepted Message from the Session at acceptance, including work sent by a principal
- `get_result` authorizes the requesting Membership across Session replacement, in the Runtime, HTTP, MCP, and the Client
- join challenge nonces and single-use tokens are consumed in the same store transition as a successful join; concurrent use of one token admits at most one Membership; revoke versus join has a defined winner
- MCP Session binding covers the five tools, additional Team tools, and the roster resource; a missing Authorization header is operator only on an explicitly trusted loopback or in-process hosting path
- a reverse proxy in front of a loopback listener is not that path; any forwarded-client header, including an empty `X-Forwarded-*` value, with no Session token is unauthorized
- an empty or malformed Authorization header is unauthorized and is never treated as operator
- missing HTTP request context does not imply in-process operator trust
- authenticating a Session does not renew expiry; `heartbeat` is the Session renewal operation and does not extend Delivery leases
- generated JSON Schema and the Python projection reject a Message that has `thread_id` without `seq`, or `seq` without `thread_id`
- Python models require the same wire fields as JSON Schema, including discriminators such as Message `kind`
- `Uuid` is a pattern as well as `format: uuid`, so validators that skip optional formats still reject a non-UUID string
- untrusted HTTP and MCP bodies validate against the public schema once; extra fields, coercible wrong types, and invalid tags fail at that edge
- MCP tool arguments are checked in their original form before SDK coercion or default insertion
- advertised MCP tool schemas are the public argument types, so omit-only fields, bounds, enumerations, identifier patterns, and undeclared properties agree with `tools/call`
- shared schema rejection vectors live in [`schema/rejection.json`](schema/rejection.json); tests also derive structural mutations from the valid controls

This is a draft. No implementation may claim conformance yet.
