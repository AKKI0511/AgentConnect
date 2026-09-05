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
- a request always expects a reply, carries a `deadline`, and opens a Ticket; an event is the fire-and-forget kind
- collection strategy (`wait`, `ticket`, and reserved `callback` and `stream`) on the `send`, not on the Message
- Thread history ordered by a per-Thread `seq` assigned on acceptance; `parent_id` names the reply or continuation target
- a Thread participant set of one or more Memberships, fixed at creation and seeded from the first Message
- `wait` holds `send` until the Ticket is terminal or `wait_hold_seconds` elapses, then returns the current Ticket
- `max_held_waits` caps concurrent held `wait` sends per Membership; past the cap `send` fails with `wait_limit`
- Message idempotency compares a SHA-256 hash of canonical JSON, with `1` / `1.0` / `1e0` equal
- a Mailbox is a lease-based pull port of per-item documents; `max_mailbox_depth` is an exact count of queued plus leased items
- `join` may request Delivery history as Message ids instead of bodies
- pull delivery with exclusive leases, at-least-once handling, and a reported message-size limit
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

This is a draft. No implementation may claim conformance yet.
