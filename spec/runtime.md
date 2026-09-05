# Runtime

A Runtime serves one Team. It owns Memberships, Sessions, Mailboxes, Deliveries, Tickets, Thread history, and the Directory. Agents remain in Client processes and pull work through Runtime operations.

The Runtime MUST NOT store Agent objects or invoke Agent methods. An embedded Client may call Runtime operations in process, but the ownership boundary stays the same.

Exact request and result shapes are in [schema/schema.ts](schema/schema.ts). Message, Delivery, Ticket, and Thread behavior is in [messaging.md](messaging.md).

## State ownership

| State | Owner | Lifetime |
| --- | --- | --- |
| Membership | Runtime | until the Team removes it |
| Session | Runtime | until disconnect, replacement, expiry, or token revocation |
| Mailbox | Runtime | the Agent Membership's lifetime |
| Delivery lease | Runtime | until reply, completion, or lease expiry |
| Ticket | Runtime | open: at least until `deadline`; terminal: until the later of `deadline` and a documented interval after close |
| Trace events | Runtime | at least while any Message or Ticket that carries that `trace_id` is retained; MAY persist longer; MAY drop the oldest events past a cap |
| Thread history | Runtime | until the documented retention limit removes it; Messages still needed by an open Ticket are kept |
| Agent working memory | Client | outside this specification |

Membership is durable with respect to Client presence. An offline Agent keeps its Address, Profile, Mailbox, Tickets, and retained Thread history.

## Memberships, Instances, and Mailboxes

A Membership is one identity in one Team. It has one Address.

A Membership that may be hired is an **Agent**. An Agent Membership has a Profile, a Directory entry, and one logical Mailbox.

A **principal** Membership holds an identity and a Session and may `send`, `find`, `get_result`, `get_history`, and `get_trace`. It has no Profile, no Directory entry, and no Mailbox. A `send` naming it fails with `not_found`. It stays visible in `status`, so an operator can see who is acting. Sessions, attribution, and Ticket ownership are unchanged.

The reserved `operator` is a principal. The Runtime reserves that name when it starts. A `join` that uses it fails with `name_conflict`. `remove_membership` refuses the operator.

An Agent Membership may have several concurrent **Instances**, each a running copy of the Agent holding one Session. Instances share the Membership's Mailbox and compete for its Deliveries; each Delivery is leased to exactly one Instance. Consecutive turns of one Thread MAY land on different Instances; the retained transcript is what a later Instance reads. Correlation never lives in an Instance: a Ticket is a Runtime record, so any Instance can complete work another Instance was handling after a lease is released.

The Mailbox is one logical queue. A Runtime MAY partition it internally to scale a single busy Agent. Partitioning changes no observable rule except that the Runtime does not promise a total order across the Mailbox.

## Persistence

Every Runtime reports one `persistence` value in `JoinResult`.

| Value | Required behavior |
| --- | --- |
| `volatile` | Shared state survives Client disconnects but may be lost when the Runtime process exits. |
| `durable` | Memberships, Sessions, Mailboxes, accepted Messages, open Tickets, Trace events, and retained Thread history survive a Runtime restart. |

A Runtime MUST NOT report `durable` unless all listed state survives restart as one consistent state. A partially persistent Runtime reports `volatile`.

## Reported limits

`JoinResult.limits` reports the fixed operational limits a Client must respect:

- `max_message_bytes`, the largest accepted `send` body, and the byte budget for a Delivery `history` window of Message bodies
- `max_mailbox_depth`, queued plus leased Mailbox items past which `send` returns `busy`
- `delivery_history_limit`, the Message-count cap for a Delivery history window
- `wait_hold_seconds`, how long `collect=wait` may keep `send` open
- `max_held_waits`, how many `collect=wait` sends one Membership may hold at once

## Operations

| Operation | Caller | Result |
| --- | --- | --- |
| `join` | unauthenticated Client with join credentials, or embedded Client | Membership plus Session for one Instance |
| `disconnect` | member Session | Session closed; Membership retained |
| `heartbeat` | member Session | renewed Session expiry |
| `send` | member Session | accepted Message and, when the Message is a request, a Ticket |
| `lease` | member Session | zero or more exclusive Deliveries |
| `complete` | member Session | an event Delivery finished, or a request declined |
| `reply` | member Session | a request Delivery finished with a response or error |
| `get_result` | Ticket owner | current Ticket |
| `get_history` | Thread participant | one page of Thread history |
| `find` | member Session | ordered Directory matches |
| `get_profile` | member Session | one Directory entry |
| `status` | operator Session | members, online state, Mailbox depths, open Tickets |
| `get_trace` | operator Session (full list), or a member Session that appears in the trace (events that name that member) | ordered Trace events for one `trace_id` |
| `issue_join_token` | operator Session | a join token scoped to this Team |
| `revoke_join_token` | operator Session | the token revoked; Sessions created from it unauthorized |

HTTP and MCP operations except `join` require a valid Session. A request with an expired, replaced, disconnected, or revoked Session MUST fail with `unauthorized` and MUST NOT change shared state.

The reserved `operator` Membership may call every member operation and the operator operations above. A non-operator Session that calls `status`, `issue_join_token`, or `revoke_join_token` fails with `forbidden`.

Over HTTP and MCP, operator authority is the Session. The hosting process may call `issue_join_token` and `revoke_join_token` on the Runtime object without a Session; the process is the trust boundary.

## `join`

`join` creates a Membership or reconnects one, then opens a Session for one Instance. A join that uses the reserved name `operator` fails with `name_conflict`.

The Runtime applies these rules using insert-if-absent on the name and DID bindings:

1. Validate the contract version, Agent name, Profile, and identity.
2. If neither the name nor Agent DID belongs to a Membership, create a Membership and Mailbox. Inserting a name or DID that another join already bound fails with `name_conflict`.
3. If the name and Agent DID identify the same Membership, reuse it and replace its Profile with the submitted Profile.
4. If the name and Agent DID do not identify the same Membership, fail with `name_conflict`. This includes a name bound to another DID and a DID bound to another name.
5. Open a Session for the Instance:
   - If `instance_id` matches an active Instance of this Membership, replace that Instance's Session. Its prior Session becomes unauthorized and its leases are released, so their Messages become available again with a higher `attempt`.
   - Otherwise open an additional concurrent Instance. Assign an `instance_id` when the Client omitted one.
6. Return the canonical Address, the Instance's `instance_id`, the reported limits, and a new Session.

`instance_id` MUST be unique per running copy. Two copies that share one value keep replacing each other's Session. Clients SHOULD generate a fresh UUID when the caller does not supply a stable id. The Runtime assigns one when `instance_id` is omitted.

A Runtime MUST support at least one Instance per Membership. It MAY cap concurrent Instances and reject one past the cap with `busy`. A Client that reconnects without a stable `instance_id` opens a fresh Instance; the Session it lost expires on its own.

`JoinRequest.max_in_flight` declares how many Deliveries this Session can handle concurrently. It defaults to `1`. The Runtime MUST NOT lease more active Deliveries to the Session than this value.

`JoinRequest.delivery_history` selects how each Delivery carries Thread history. Omit it, or send `bodies`, to receive earlier Message objects. Send `ids` to receive only earlier Message ids. The default is `bodies`.

A network Runtime requires both credentials defined in [security.md](security.md). An embedded Runtime may omit them only when it exposes no non-loopback listener.

### Example result

```json
{
  "session_token": "opaque-session-token",
  "session_expires_at": "2026-08-18T15:05:00Z",
  "address": "researcher@content-squad",
  "team_name": "content-squad",
  "agent_did": "did:key:z6MkmEtU9Z7p7G6vbULDgMk8DXCVqW8rNyLMtd2RrAHjLD3m",
  "instance_id": "8f0d3e6a-6b1f-4d1e-9a2c-2f0b7c9d1e5a",
  "persistence": "durable",
  "limits": {
    "max_message_bytes": 1048576,
    "max_mailbox_depth": 1000,
    "delivery_history_limit": 50,
    "wait_hold_seconds": 25,
    "max_held_waits": 16
  },
  "spec_version": "1.0.0-draft"
}
```

## `disconnect`

`disconnect` closes the calling Session and retains the Membership.

The Runtime MUST release the Session's active leases immediately. Their Messages become available again with a higher `attempt`. Open Tickets remain open until a reply, failure, or deadline makes them terminal. Other Instances of the Membership are unaffected.

Disconnecting does not remove the Membership, Profile, Address, Mailbox, or retained history.

## `heartbeat`

`heartbeat` proves that the Client still holds its Session. The Runtime MAY extend the Session before returning its current `session_expires_at`.

A missed heartbeat may let the Session expire. Session expiry releases active leases and has the same shared-state behavior as `disconnect`.

## Expiry

Sessions, Delivery leases, open Ticket deadlines, terminal Ticket retention, join challenges, and join tokens expire from a time-ordered index. Each sweep processes items whose time is due.

| Situation | Required observation |
| --- | --- |
| one Session past `expires_at` among many unexpired Sessions | the expired Session is `unauthorized`; the others remain valid |

## `send`

`send` accepts one request or event for one recipient in the Team.

Before acceptance, the Runtime MUST:

- authenticate the Session
- validate the request against the schema
- reject a body larger than `max_message_bytes` with `payload_too_large`
- reject `collect=callback` or `collect=stream` with `unsupported_collect_mode`
- resolve the recipient within the Team
- reject a principal recipient, including `operator`, with `not_found`
- require a future `deadline` on any request
- validate any `parent_id` and Thread participation
- reject a full recipient Mailbox with `busy`
- reject a `collect=wait` `send` that would exceed `max_held_waits` for the sender's Membership with `wait_limit`
- apply the Message idempotency rules below

After acceptance, the Runtime MUST:

- set the verified `sender`
- canonicalize `sender` and `recipient` as qualified Addresses
- set `created_at`
- set `seq` when `thread_id` is present
- set `trace_id` by the propagation rules in [messaging.md](messaging.md)
- store the immutable Message
- append it to retained Thread history when `thread_id` is present
- enqueue it in the recipient's Mailbox

The result depends on the request:

| Input | Ticket | Return behavior |
| --- | --- | --- |
| event | none | return after acceptance |
| request with `collect=ticket` | created | return the current Ticket immediately |
| request with `collect=wait` | created | hold `send` until the Ticket is terminal or `wait_hold_seconds` elapses, then return the current Ticket |

Every request MUST include `collect` and a future `deadline`. A missing or past deadline, or a missing `collect`, fails with `invalid_request`. When the deadline passes, the Ticket becomes `expired`, the Delivery stops being leaseable, and an active lease for that Message is no longer valid.

`wait_hold_seconds` is a bound on the `send` call, not on the Ticket. A `wait` that returns an `open` Ticket has already accepted the Message. The Client collects the terminal result with `get_result`.

`max_held_waits` bounds how many `collect=wait` sends one Membership may hold at once. A new `send` with `collect=wait` past that cap fails with `wait_limit` and creates nothing. `busy` is only a full Mailbox. A replay of an already accepted `wait` that cannot obtain a hold slot returns the current Ticket immediately.

Transport disconnect after acceptance does not undo the send. The Client recovers the result by calling `get_result` with the request Message id.

The Runtime wakes a waiting `send` when the Ticket becomes terminal. It MUST NOT poll the Ticket on a short interval while the hold remains.

### Message idempotency

`SendRequest.id` is Client-generated and becomes the accepted Message id. A Ticket, when created, uses the same id.

Message ids are unique across the Team. The Runtime applies these rules:

- replaying the same id from the original sender with the same semantic request returns the existing Message and follows the original collection behavior: an event returns the accepted Message, `collect=ticket` returns the current Ticket, and `collect=wait` holds until the Ticket is terminal or `wait_hold_seconds` elapses
- using an existing id from another Membership fails with `id_conflict`
- replaying the original sender's id with different content, recipient, kind, deadline, collection strategy, Thread, parent, or metadata fails with `id_conflict`
- a replay MUST NOT create another Delivery

Address canonicalization does not make an otherwise identical replay different.

Semantic equality is SHA-256 of one canonical JSON encoding of the semantic request. Object keys are sorted. Array order is kept. Missing optional fields stay missing. Numbers that are whole values in IEEE-754 binary64 normalize to the same integer, so `1`, `1.0`, and `1e0` match. Canonical Addresses and parsed deadline instants are compared after canonicalization. The collection strategy is part of the semantic request even though it is not stored on the Message. The Runtime compares those hashes. It does not walk `content` on each replay.

## `lease`

`lease` pulls available work from the calling Membership's Mailbox.

The Mailbox is a lease-based pull port. Claim an item with a timeout, extend that timeout, acknowledge it on `complete` or `reply`, and return it to the ready set when a lease expires or a Session is lost. That is the same shape as a visibility timeout. A backend that can perform those four operations per item can implement a Mailbox. A partitioned log without per-message leases cannot.

`max_items` defaults to `1` and MUST be between `1` and `100`. The Runtime may return fewer items because of Mailbox depth or the Session's `max_in_flight` limit. An empty Mailbox returns an empty `deliveries` array.

Each returned Delivery has an exclusive `lease_id` and `lease_expires_at`, and a bounded Thread history window. The same Delivery MUST NOT be leased to another Session while that lease remains valid, including to another Instance of the same Membership. Lease acquisition is a compare-and-set on the Mailbox item. Two concurrent `lease` calls MUST NOT both receive the same item.

If a lease expires before `complete` or `reply` succeeds:

- the Message becomes available again unless its Ticket is terminal
- its next Delivery has the same Message id and a higher `attempt`
- a later operation using the expired lease fails with `lease_expired`

First attempts are offered in Message acceptance order per partition. Recovered attempts become available at recovery time. The Runtime does not promise a total order across the Mailbox, nor FIFO between a recovered attempt and Messages that arrived while it was leased.

## `complete`

`complete` finishes a Delivery without creating a response Message. Its effect depends on the delivered Message:

- for an event, the Delivery just ends and no Ticket exists
- for a request, the Runtime declines it, moves the Ticket to `declined`, and returns that Ticket in `CompleteResult`

Declining is a benign, explicit outcome, not a failure. It is how a recipient states that it read the request and chose not to answer, distinct from a handler failure and from a deadline expiring.

The Runtime first verifies that the retained lease belongs to the caller's Membership. An unknown lease or a lease owned by another Membership returns `not_found`. It then applies these checks in order:

1. A replay of an already accepted `CompleteRequest` returns its stored result.
2. A request whose Ticket is already terminal returns `ticket_closed`.
3. An inactive lease returns `lease_expired`.

## `reply`

`reply` finishes a request Delivery with either successful content or an `ErrorObject`. The Runtime creates an immutable response or error Message whose `parent_id` is the request Message id, whose `thread_id` matches the request, whose `seq` is the next Thread sequence when the request has a `thread_id`, and whose `trace_id` is copied from the request.

Only a request accepts `reply`. Calling `reply` for an event fails with `invalid_request` and leaves the Delivery active.

`ReplyRequest.id` is the response Message id and is unique across the Team. Replaying the accepted reply with the same id and semantic data returns the existing result. Reusing it for different reply data or from another Membership fails with `id_conflict`.

Reply semantic data is `outcome` plus `content` or `error`, using the same JSON equality as `send`. A successful reply with `content=null` is how a handler completes with no content. `lease_id` authorizes the attempt but is not part of the immutable reply Message.

The Runtime first verifies that the retained lease belongs to the caller's Membership. An unknown lease or a lease owned by another Membership returns `not_found`. It then checks reply idempotency, terminal Ticket state, and active lease state in that order. This makes an accepted replay stable and makes a distinct reply after Ticket expiry return `ticket_closed`.

The Runtime accepts a new reply only when:

- the lease belongs to the caller's Membership and is active
- the request Ticket is still `open`

The accepted reply completes the Delivery and moves the Ticket to `completed` or `failed` with a compare-and-set on the Ticket document. The first writer to observe `open` and store a terminal state wins. A later writer MUST NOT replace that outcome and fails with `ticket_closed`. The response or error Message is stored for the Ticket and retained Thread history; it MUST NOT be enqueued in the requester's Mailbox.

## `get_result`

`get_result` returns the Ticket whose id equals the original request Message id.

Only the requesting Membership may read the Ticket. A request from another Membership returns `not_found` so Ticket existence and contents are not disclosed.

The operation is read-only. Reading an open or terminal Ticket any number of times returns its current stored state without consuming it.

## `get_history`

`get_history` returns one page of a Thread's retained history, ordered by `seq` ascending.

- `before` names a Message id; the page contains the Messages immediately older than it. Omit `before` to read the newest page.
- a `before` value that is a UUID and is not in the retained transcript, including an evicted id, returns the newest page
- a `before` value that is not a UUID fails with `invalid_request`
- `limit` is between `1` and `200` and defaults to `50`.
- `has_more` is `true` when older retained Messages remain before this page.

Only a Membership in the Thread's participant set may read it. Any other caller receives `not_found`, revealing no history. When retention has removed the oldest Messages, `get_history` returns the oldest that remain.

## `find`

`find` searches the current Team's Directory. It excludes the caller's own Membership. Principals, including `operator`, are not in the Directory and MUST NOT appear in the result.

The Runtime MUST:

- accept a natural-language `query` containing 1 to 1,000 characters and at least one non-whitespace character
- consider every other Agent Membership in the Team
- order matches by relevance, best first
- break equal-relevance ties by canonical Address
- when `limit` is omitted, return every remaining member, at most 100
- when `limit` is present, return at most that many matches; `limit` MUST be between `1` and `100`
- return each match at the requested `detail`

`detail` is `summary` or `full` and defaults to `summary`; `full` adds `agent_did` and the complete Profile to each match. Search MUST work without optional infrastructure. Ranking implementation is outside the specification, and changing it MUST NOT change the request or result shape.

A future addition may widen `find` to reach beyond the local Team. That is an added scope, not a reshape: the result stays a list of ranked matches whose Addresses are already qualified.

## `get_profile`

`get_profile` resolves an Address in the current Team and returns its full `DirectoryEntry`. It may return the caller's own entry. A principal, including `operator`, returns `not_found`.

The Runtime MUST NOT place the returned Profile into another handler's input unless that handler explicitly called `find` or `get_profile` and passed the data itself.

| Situation | Required observation |
| --- | --- |
| teammate `find` | the result contains no Address for `operator` |
| `send` to `operator` | `not_found` |
| `join` as `operator` on a fresh Store | `name_conflict`, in any call order |

## `status`

`status` is a snapshot of this Team for an operator. It is read-only.

The result MUST include:

- the Team name and reported `persistence`
- HTTP origin when the Runtime is serving, omitted when it is not
- every Membership, including `operator`
- the number of open Tickets in the Team

Each member row MUST include `kind`, the canonical name and Address, and whether the Membership has at least one unexpired Session (`online`). `online` is read from stored Sessions. A durable restart keeps `online` true for any Membership that still has an unexpired Session. An Agent row (`kind` `agent`) also includes current Mailbox depth and the number of open Tickets whose recipient is that Membership. A principal row (`kind` `principal`) MUST omit those counts.

Mailbox depth counts queued and leased items, matching the busy limit.

```json
{
  "team_name": "content-squad",
  "persistence": "volatile",
  "origin": "http://127.0.0.1:9000",
  "open_tickets": 1,
  "members": [
    {
      "kind": "principal",
      "name": "operator",
      "address": "operator@content-squad",
      "online": true
    },
    {
      "kind": "agent",
      "name": "writer",
      "address": "writer@content-squad",
      "online": true,
      "mailbox_depth": 1,
      "open_tickets": 1
    }
  ]
}
```

| Situation | Required observation |
| --- | --- |
| `status` with `operator` and an idle Agent | the operator row has `kind` `principal` and no `mailbox_depth`; the Agent row has `kind` `agent` and `mailbox_depth` `0` |
| durable Runtime restart, Agent Session still unexpired | that Agent row has `online` true |

## `get_trace`

`get_trace` returns the stored timeline for one `trace_id`, oldest event first.

The Runtime records a Trace event when it accepts a Message, opens a Ticket, leases a Delivery, finishes a Delivery with `complete` or `reply`, or expires a Ticket. A replay of an already accepted `send`, `complete`, or `reply` MUST NOT append another event. A `send` that fails before acceptance creates no Trace.

When the Message named by an event has a `parent_id`, the event copies it. A Client rebuilds the request tree from that field. The result stays an ordered list.

An unknown `trace_id`, and a non-operator caller that does not appear in the Trace, both return `not_found`. Appearing in the Trace means the caller's Address is an event `actor` or a Message `sender` or `recipient` named by an event.

A member Session that appears in the Trace receives only the events that name that Membership: the event `actor`, a `sender` or `recipient` in `detail`, or the sender or recipient of the Message named by `message_id`. An operator Session receives the full list.

Events for one `trace_id` are retained at least while any Message or Ticket that carries that id is retained. A Runtime MAY keep them longer. A Runtime MAY cap the stored list; when the cap is reached it drops the oldest events.

```json
{
  "trace_id": "e26e64ce-f7f1-47c4-a323-e3a3867e7d28",
  "events": [
    {
      "at": "2026-08-18T15:00:00Z",
      "type": "accepted",
      "trace_id": "e26e64ce-f7f1-47c4-a323-e3a3867e7d28",
      "actor": "researcher@content-squad",
      "message_id": "15c44926-4c2a-4a01-a13b-95152da9a859",
      "detail": {
        "kind": "request",
        "sender": "researcher@content-squad",
        "recipient": "writer@content-squad"
      }
    },
    {
      "at": "2026-08-18T15:00:00Z",
      "type": "ticket_opened",
      "trace_id": "e26e64ce-f7f1-47c4-a323-e3a3867e7d28",
      "actor": "researcher@content-squad",
      "message_id": "15c44926-4c2a-4a01-a13b-95152da9a859",
      "ticket_id": "15c44926-4c2a-4a01-a13b-95152da9a859",
      "detail": {}
    }
  ]
}
```

| Situation | Required observation |
| --- | --- |
| accepted request, never leased, then expired | events `accepted`, `ticket_opened`, `ticket_closed` with `detail.state=expired`; no `leased` |
| handler returns an error | `leased` then `replied` with `detail.outcome=failed` |
| recipient `complete`s a request | `completed` then the Ticket is `declined` |
| member Session reads a Trace it does not appear in | `not_found` |
| operator Session reads that same Trace | `TraceResult` with every event |
| member at the tail of a fan-out Trace | only events that name that member; the head-leg `accepted` is absent |
| fan-out request with `parent_id` | the child `accepted` event carries that `parent_id` |

## `issue_join_token` and `revoke_join_token`

`issue_join_token` creates a join token as defined in [security.md](security.md). The operator MAY bind `name`, `agent_did`, both, or neither. `ttl_seconds` defaults to the Runtime's join-token lifetime. `single_use` defaults to `false`.

The result includes the secret `token`. It MUST NOT be written into Message content, metadata, or Trace `detail`.

`revoke_join_token` revokes that secret if it exists. Revoking an unknown token is a no-op success. Revoking MUST invalidate every Session created from the token, with the same promptness as [security.md](security.md) immediate revocation.

## Mailbox limits

A Runtime MUST have a finite Mailbox limit reported as `max_mailbox_depth`. It MUST apply the same documented limit to every Agent Membership unless Team configuration explicitly sets per-member limits. Principals have no Mailbox.

Depth is the exact count of queued plus leased items the Runtime records for that Mailbox. `send` returns `busy` when acceptance would move that count past the limit. The Runtime records the count as part of enqueue. It does not take an approximate queue-depth metric from a backend.

When acceptance would exceed the limit, `send` fails with `busy`. The Runtime MUST NOT create a Message, Delivery, or Ticket for the rejected request.

Enqueue cost MUST NOT grow with current depth. The Mailbox stores one document per item behind a time-ordered index. A send against a full Mailbox and a send against an empty Mailbox do the same amount of work up to the depth check.

| Situation | Required observation |
| --- | --- |
| two concurrent `send`s into an empty Mailbox | both accepted; depth 2 |
| `send` that would pass `max_mailbox_depth` | `busy`; no Message, Delivery, or Ticket |
| two concurrent `lease` calls on one ready item | one Delivery; the other call does not receive that item |
| new `collect=wait` while the Membership holds `max_held_waits` | `wait_limit`; nothing created |

## Work notification

A Runtime MAY notify a Session that work is available so the Client can `lease` without polling. This is only a hint. Mailbox and Ticket correctness MUST NOT depend on it; a Client that ignores every notification and polls `lease` loses nothing. The notification channel is defined in [bindings/http.md](bindings/http.md).

## Errors

| Code | Meaning |
| --- | --- |
| `unsupported_version` | Client and Runtime contract drafts differ. |
| `unsupported_collect_mode` | A collection strategy is named but not implemented yet. |
| `unauthorized` | Session or join authentication failed. |
| `forbidden` | Authenticated caller lacks authority for the operation. |
| `invalid_request` | Request shape or a conditional requirement is invalid. |
| `invalid_address` | Address syntax is invalid. |
| `address_outside_team` | Address is valid but does not name the current Team. |
| `not_found` | Named resource is absent or intentionally undisclosed. |
| `name_conflict` | The requested Agent name and DID conflict with an existing Membership binding. |
| `id_conflict` | A reused Message id carries different data. |
| `busy` | Recipient Mailbox is full, or no more Instances may join. |
| `wait_limit` | The Membership already holds `max_held_waits` `collect=wait` sends. |
| `payload_too_large` | A `send` body exceeds `max_message_bytes`. |
| `lease_expired` | Delivery lease is no longer active. |
| `ticket_closed` | `reply` tried to change a terminal Ticket. |
| `unavailable` | Runtime cannot currently perform the operation. |
| `internal` | Runtime failed without a more specific public error. |
| `handler_failed` | Ticket contains an Agent handler failure. |
| `deadline_exceeded` | Ticket expired before a reply was accepted. |

`handler_failed` and `deadline_exceeded` normally appear inside a failed or expired Ticket. The other codes normally describe a failed Runtime operation.

`ErrorObject.code` is always one of the codes above. An Agent application failure code belongs in `ErrorObject.details` of a `handler_failed` error, whose shape the Agent owns.
