# Runtime

A Runtime serves one Team. It owns Memberships, Sessions, Mailboxes, Deliveries, Tickets, Thread history, and the Directory. Agents remain in Client processes and pull work through Runtime operations.

The Runtime MUST NOT store Agent objects or invoke Agent methods. An embedded Client may call Runtime operations in process, but the ownership boundary stays the same.

Exact request and result shapes are in [schema/schema.ts](schema/schema.ts). Message, Delivery, Ticket, and Thread behavior is in [messaging.md](messaging.md).

## State ownership

| State | Owner | Lifetime |
| --- | --- | --- |
| Membership | Runtime | until the Team removes it |
| Session | Runtime | until disconnect, replacement, expiry, or token revocation |
| Mailbox | Runtime | the Membership's lifetime |
| Delivery lease | Runtime | until reply, completion, or lease expiry |
| Ticket | Runtime | open: at least until `deadline`; terminal: until the later of `deadline` and a documented interval after close |
| Thread history | Runtime | until the documented retention limit removes it; Messages still needed by an open Ticket are kept |
| Agent working memory | Client | outside this specification |

Membership is durable with respect to Client presence. An offline Agent keeps its Address, Profile, Mailbox, Tickets, and retained Thread history.

## Memberships, Instances, and Mailboxes

A Membership is one Agent in one Team. It has one identity, one Address, one Profile, and one logical Mailbox.

A Membership may have several concurrent **Instances**, each a running copy of the Agent holding one Session. Instances share the Membership's Mailbox and compete for its Deliveries; each Delivery is leased to exactly one Instance. Consecutive turns of one Thread MAY land on different Instances; the retained transcript is what a later Instance reads. Correlation never lives in an Instance: a Ticket is a Runtime record, so any Instance can complete work another Instance was handling after a lease is released.

The Mailbox is one logical queue. A Runtime MAY partition it internally to scale a single busy Agent. Partitioning changes no observable rule except that the Runtime does not promise a total order across the Mailbox.

## Persistence

Every Runtime reports one `persistence` value in `JoinResult`.

| Value | Required behavior |
| --- | --- |
| `volatile` | Shared state survives Client disconnects but may be lost when the Runtime process exits. |
| `durable` | Memberships, Mailboxes, accepted Messages, open Tickets, and retained Thread history survive a Runtime restart. |

A Runtime MUST NOT report `durable` unless all listed state survives restart as one consistent state. A partially persistent Runtime reports `volatile`.

## Reported limits

`JoinResult.limits` reports the fixed operational limits a Client must respect:

- `max_message_bytes`, the largest accepted `send` body, and the byte budget for a Delivery `history` window
- `max_mailbox_depth`, the point past which `send` returns `busy`
- `delivery_history_limit`, the Message-count cap for a Delivery `history` window
- `wait_hold_seconds`, how long `collect=wait` may keep `send` open

## Operations

| Operation | Caller | Result |
| --- | --- | --- |
| `join` | unauthenticated Client with join credentials, or embedded Client | Membership plus Session for one Instance |
| `disconnect` | member Session | Session closed; Membership retained |
| `heartbeat` | member Session | renewed Session expiry |
| `send` | member Session | accepted Message and, when reply-expected, a Ticket |
| `lease` | member Session | zero or more exclusive Deliveries |
| `complete` | member Session | an event or no-reply Delivery finished, or a reply-expected request declined |
| `reply` | member Session | a reply-expected Delivery finished with a response or error |
| `get_result` | Ticket owner | current Ticket |
| `get_history` | Thread participant | one page of Thread history |
| `find` | member Session | ordered Directory matches |
| `get_profile` | member Session | one Directory entry |

All operations except `join` require a valid Session. A request with an expired, replaced, disconnected, or revoked Session MUST fail with `unauthorized` and MUST NOT change shared state.

## `join`

`join` creates a Membership or reconnects one, then opens a Session for one Instance.

The Runtime applies these rules atomically:

1. Validate the contract version, Agent name, Profile, and identity.
2. If neither the name nor Agent DID belongs to a Membership, create a Membership and Mailbox.
3. If the name and Agent DID identify the same Membership, reuse it and replace its Profile with the submitted Profile.
4. If the name and Agent DID do not identify the same Membership, fail with `name_conflict`. This includes a name bound to another DID and a DID bound to another name.
5. Open a Session for the Instance:
   - If `instance_id` matches an active Instance of this Membership, replace that Instance's Session. Its prior Session becomes unauthorized and its leases are released, so their Messages become available again with a higher `attempt`.
   - Otherwise open an additional concurrent Instance. Assign an `instance_id` when the Client omitted one.
6. Return the canonical Address, the Instance's `instance_id`, the reported limits, and a new Session.

`instance_id` MUST be unique per running copy. Two copies that share one value keep replacing each other's Session. Clients SHOULD generate a fresh UUID when the caller does not supply a stable id. The Runtime assigns one when `instance_id` is omitted.

A Runtime MUST support at least one Instance per Membership. It MAY cap concurrent Instances and reject one past the cap with `busy`. A Client that reconnects without a stable `instance_id` opens a fresh Instance; the Session it lost expires on its own.

`JoinRequest.max_in_flight` declares how many Deliveries this Session can handle concurrently. It defaults to `1`. The Runtime MUST NOT lease more active Deliveries to the Session than this value.

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
    "wait_hold_seconds": 25
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

## `send`

`send` accepts one request or event for one recipient in the Team.

Before acceptance, the Runtime MUST:

- authenticate the Session
- validate the request against the schema
- reject a body larger than `max_message_bytes` with `payload_too_large`
- reject `collect=callback` or `collect=stream` with `unsupported_collect_mode`
- resolve the recipient within the Team
- require a future `deadline` on any reply-expected request
- validate any `parent_id` and pairwise Thread participation
- reject a full recipient Mailbox with `busy`
- apply the Message idempotency rules below

After acceptance, the Runtime MUST:

- set the verified `sender`
- canonicalize `sender` and `recipient` as qualified Addresses
- set `created_at`
- set `trace_id` by the propagation rules in [messaging.md](messaging.md)
- store the immutable Message
- append it to retained Thread history when `thread_id` is present
- enqueue it in the recipient's Mailbox

The result depends on the request:

| Input | Ticket | Return behavior |
| --- | --- | --- |
| event | none | return after acceptance |
| no-reply request | none | return after acceptance |
| reply-expected request with `collect=ticket` | created | return the current Ticket immediately |
| reply-expected request with `collect=wait` | created | hold `send` until the Ticket is terminal or `wait_hold_seconds` elapses, then return the current Ticket |

Every reply-expected request MUST include a future `deadline`. A missing or past deadline fails with `invalid_request`. When the deadline passes, the Ticket becomes `expired`, the Delivery stops being leaseable, and an active lease for that Message is no longer valid.

`wait_hold_seconds` is a bound on the `send` call, not on the Ticket. A `wait` that returns an `open` Ticket has already accepted the Message. The Client collects the terminal result with `get_result`.

Transport disconnect after acceptance does not undo the send. The Client recovers the result by calling `get_result` with the request Message id.

### Message idempotency

`SendRequest.id` is Client-generated and becomes the accepted Message id. A Ticket, when created, uses the same id.

Message ids are unique across the Team. The Runtime applies these rules:

- replaying the same id from the original sender with the same semantic request returns the existing Message and follows the original collection behavior: an event or no-reply request returns the accepted Message, `collect=ticket` returns the current Ticket, and `collect=wait` holds until the Ticket is terminal or `wait_hold_seconds` elapses
- using an existing id from another Membership fails with `id_conflict`
- replaying the original sender's id with different content, recipient, kind, deadline, collection strategy, Thread, parent, or metadata fails with `id_conflict`
- a replay MUST NOT create another Delivery

Address canonicalization does not make an otherwise identical replay different.

For idempotency, semantic equality compares canonical Addresses and parsed deadline instants. JSON objects compare recursively by key and value without considering key order; array order remains significant; numbers compare by value. The presence or absence of an optional field remains significant. The collection strategy is part of the semantic request even though it is not stored on the Message.

## `lease`

`lease` pulls available work from the calling Membership's Mailbox.

`max_items` defaults to `1` and MUST be between `1` and `100`. The Runtime may return fewer items because of Mailbox depth or the Session's `max_in_flight` limit. An empty Mailbox returns an empty `deliveries` array.

Each returned Delivery has an exclusive `lease_id` and `lease_expires_at`, and a bounded Thread history window. The same Delivery MUST NOT be leased to another Session while that lease remains valid, including to another Instance of the same Membership.

If a lease expires before `complete` or `reply` succeeds:

- the Message becomes available again unless its Ticket is terminal
- its next Delivery has the same Message id and a higher `attempt`
- a later operation using the expired lease fails with `lease_expired`

First attempts are offered in Message acceptance order per partition. Recovered attempts become available at recovery time. The Runtime does not promise a total order across the Mailbox, nor FIFO between a recovered attempt and Messages that arrived while it was leased.

## `complete`

`complete` finishes a Delivery without creating a response Message. Its effect depends on the delivered Message:

- for an event or no-reply request, the Delivery just ends and no Ticket exists
- for a reply-expected request, the Runtime declines it, moves the Ticket to `declined`, and returns that Ticket in `CompleteResult`

Declining is a benign, explicit outcome, not a failure. It is how a recipient states that it read the request and chose not to answer, distinct from a handler failure and from a deadline expiring.

The Runtime first verifies that the retained lease belongs to the caller's Membership. An unknown lease or a lease owned by another Membership returns `not_found`. It then applies these checks in order:

1. A replay of an already accepted `CompleteRequest` returns its stored result.
2. A reply-expected request whose Ticket is already terminal returns `ticket_closed`.
3. An inactive lease returns `lease_expired`.

## `reply`

`reply` finishes a reply-expected Delivery with either successful content or an `ErrorObject`. The Runtime creates an immutable response or error Message whose `parent_id` is the request Message id, whose `thread_id` matches the request, and whose `trace_id` is copied from the request.

Only a reply-expected request accepts `reply`. Calling `reply` for an event or a no-reply request fails with `invalid_request` and leaves the Delivery active.

`ReplyRequest.id` is the response Message id and is unique across the Team. Replaying the accepted reply with the same id and semantic data returns the existing result. Reusing it for different reply data or from another Membership fails with `id_conflict`.

Reply semantic data is `outcome` plus `content` or `error`, using the same JSON equality as `send`. A successful reply with `content=null` is how a handler completes with no content. `lease_id` authorizes the attempt but is not part of the immutable reply Message.

The Runtime first verifies that the retained lease belongs to the caller's Membership. An unknown lease or a lease owned by another Membership returns `not_found`. It then checks reply idempotency, terminal Ticket state, and active lease state in that order. This makes an accepted replay stable and makes a distinct reply after Ticket expiry return `ticket_closed`.

The Runtime accepts a new reply only when:

- the lease belongs to the caller's Membership and is active
- the request Ticket is still `open`

The accepted reply completes the Delivery and moves the Ticket to `completed` or `failed`. The response or error Message is stored for the Ticket and retained Thread history; it MUST NOT be enqueued in the requester's Mailbox. A reply after a terminal Ticket MUST NOT replace its outcome and fails with `ticket_closed`.

## `get_result`

`get_result` returns the Ticket whose id equals the original request Message id.

Only the requesting Membership may read the Ticket. A request from another Membership returns `not_found` so Ticket existence and contents are not disclosed.

The operation is read-only. Reading an open or terminal Ticket any number of times returns its current stored state without consuming it.

## `get_history`

`get_history` returns one page of a Thread's retained history, ordered by `created_at` then Message id, ascending.

- `before` names a Message id; the page contains the Messages immediately older than it. Omit `before` to read the newest page.
- a `before` value that is a UUID and is not in the retained transcript, including an evicted id, returns the newest page
- a `before` value that is not a UUID fails with `invalid_request`
- `limit` is between `1` and `200` and defaults to `50`.
- `has_more` is `true` when older retained Messages remain before this page.

Only a Membership in the Thread's participant set may read it. Any other caller receives `not_found`, revealing no history. When retention has removed the oldest Messages, `get_history` returns the oldest that remain.

## `find`

`find` searches the current Team's Directory. It excludes the caller's own Membership.

The Runtime MUST:

- accept a natural-language `query` containing 1 to 1,000 characters and at least one non-whitespace character
- consider every other Membership in the Team
- order matches by relevance, best first
- break equal-relevance ties by canonical Address
- when `limit` is omitted, return every remaining member, at most 100
- when `limit` is present, return at most that many matches; `limit` MUST be between `1` and `100`
- return each match at the requested `detail`

`detail` is `summary` or `full` and defaults to `summary`; `full` adds `agent_did` and the complete Profile to each match. Search MUST work without optional infrastructure. Ranking implementation is outside the specification, and changing it MUST NOT change the request or result shape.

A future addition may widen `find` to reach beyond the local Team. That is an added scope, not a reshape: the result stays a list of ranked matches whose Addresses are already qualified.

## `get_profile`

`get_profile` resolves an Address in the current Team and returns its full `DirectoryEntry`. It may return the caller's own entry.

The Runtime MUST NOT place the returned Profile into another handler's input unless that handler explicitly called `find` or `get_profile` and passed the data itself.

## Mailbox limits

A Runtime MUST have a finite Mailbox limit reported as `max_mailbox_depth`. It MUST apply the same documented limit to every Membership unless Team configuration explicitly sets per-member limits.

When acceptance would exceed the limit, `send` fails with `busy`. The Runtime MUST NOT create a Message, Delivery, or Ticket for the rejected request.

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
| `payload_too_large` | A `send` body exceeds `max_message_bytes`. |
| `lease_expired` | Delivery lease is no longer active. |
| `ticket_closed` | `reply` tried to change a terminal Ticket. |
| `unavailable` | Runtime cannot currently perform the operation. |
| `internal` | Runtime failed without a more specific public error. |
| `handler_failed` | Ticket contains an Agent handler failure. |
| `deadline_exceeded` | Ticket expired before a reply was accepted. |

`handler_failed` and `deadline_exceeded` normally appear inside a failed or expired Ticket. The other codes normally describe a failed Runtime operation.
