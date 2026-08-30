# Messaging

AgentConnect moves immutable Messages through Runtime-owned Mailboxes. A Client handles a Message through a leased Delivery. Reply-expected work is tracked by a Ticket whose id is the request Message id.

Exact structures are in [schema/schema.ts](schema/schema.ts). Runtime operations are in [runtime.md](runtime.md).

## Message

A Message is created only after `send` or `reply` succeeds. The Client supplies the Message `id`; the Runtime sets the verified Addresses, `created_at`, and `trace_id`, then stores the Message as immutable data.

A request or event created by `send` enters the recipient's Mailbox. A response or error created by `reply` resolves the requester's Ticket and enters retained Thread history when the request had a `thread_id`. It does not enter the requester's Mailbox.

Four Message kinds exist:

| Kind | Created by | Meaning |
| --- | --- | --- |
| `request` | `send` | asks the recipient to handle work |
| `event` | `send` | delivers information without a response |
| `response` | successful `reply` | completes the parent request |
| `error` | failed `reply` | fails the parent request |

`kind` is a closed set. Application-level typing belongs in `content` or `metadata`, not in a custom kind.

`sender` and `recipient` on an accepted Message are canonical qualified Addresses. Clients do not set `sender`, `created_at`, or `trace_id` in `SendRequest`.

`content` is any JSON value. Message `metadata` is sender-controlled application data. The Runtime MUST NOT use `metadata` for authentication, routing, leases, Ticket state, or sender attribution.

### Request example

```json
{
  "id": "15c44926-4c2a-4a01-a13b-95152da9a859",
  "sender": "researcher@content-squad",
  "recipient": "writer@content-squad",
  "kind": "request",
  "content": {
    "task": "Draft a two-paragraph summary"
  },
  "created_at": "2026-08-18T15:00:00Z",
  "trace_id": "e26e64ce-f7f1-47c4-a323-e3a3867e7d28",
  "deadline": "2026-08-18T15:10:00Z",
  "thread_id": "4364a17f-80af-4db8-93e2-6ab85d174a20"
}
```

A request is **reply-expected** exactly when it carries a `deadline`. A request without a `deadline` expects no reply and creates no Ticket, the same as an event.

## Message identity and relationships

Every Message id is an RFC 9562 UUID and is unique within the Team. The id has three jobs:

- it identifies the immutable Message
- it is the idempotency key for `send` or `reply`
- for a reply-expected request, it is also the Ticket id

`parent_id` names the Message that directly caused another Message. A response or error MUST use the request Message id as `parent_id`. A follow-up request or event MAY use a prior Message id as `parent_id`.

`thread_id` groups related Messages. It does not replace `parent_id`:

- `thread_id` answers which conversation contains this Message
- `parent_id` answers which Message directly caused it

`trace_id` correlates one causal operation. The Runtime assigns it:

- a Message with a `parent_id` copies the parent Message's `trace_id`
- a `reply` copies the request Message's `trace_id`
- any other Message receives a fresh `trace_id`

### Thread versus trace

A Message carries both a `thread_id` and a `trace_id` because they group it along different axes, and both are useful to a handler.

- `thread_id` is the **conversation**: an id shared by a fixed participant set across every turn. It decides retained history and what a handler sees, and one conversation lasts across many separate exchanges over time.
- `trace_id` is one **causal operation**: a root Message and everything it causes, even across different conversations and different Agents. It answers "show me everything that happened because of this one request," which is what `get_trace` reconstructs.

They coincide in the simple case and diverge the moment work fans out:

> `researcher` asks `writer` in conversation `T1`; that request opens trace `X`. To answer, `writer` asks `editor` in a new conversation `T2`; because that request is caused by the first, it copies trace `X` while living in thread `T2`, so trace `X` now spans `T1` and `T2`. Later `researcher` asks `writer` something unrelated in `T1`, opening trace `Y`. One Thread holds several traces, and one trace spans several Threads.

So `thread_id` groups history for the participants, `trace_id` groups a debugging timeline for one operation, and `parent_id` is the single direct cause. A Delivery's Message carries `thread_id` and `trace_id` so a handler knows both which conversation it is in and which operation it serves. A Ticket carries only `thread_id`, because the conversation is what a requester continues; the request's `trace_id` is read from the request or from the stored response, not duplicated onto the Ticket.

`get_trace` reconstructs that timeline as `TraceEvent` values, in the order the Runtime recorded them. Event `type` is one of `accepted`, `ticket_opened`, `leased`, `completed`, `replied`, and `ticket_closed`. `completed` is a `complete` that finished the Delivery. `ticket_closed` is recorded when a Ticket expires without a `reply` or `complete`.

The Runtime MUST NOT invent a global sequence number. Ordering is scoped to retained Thread history. There is no total order across a Mailbox, which is what lets a Mailbox be partitioned for scale.

## Message size

The Runtime reports `max_message_bytes` in `JoinResult`. A `send` whose body exceeds that size, measured as its UTF-8 JSON encoding, fails with `payload_too_large` and creates no Message, Delivery, or Ticket. This bounds both a single Delivery and the amplification of large `content` through retained Thread history.

## Sending and collecting

Whether a reply is expected is a property of the Message. How the sender collects the result is a property of the `send` call and is not stored on the Message; the recipient never observes it.

A reply-expected request selects one `collect` strategy:

| `collect` | Ticket | Result of `send` |
| --- | --- | --- |
| `wait` | yes | accepted Message plus current Ticket; `send` stays open until the Ticket is terminal or `wait_hold_seconds` elapses |
| `ticket` | yes | accepted Message plus current Ticket, returned immediately |
| `callback` | yes | reserved; fails with `unsupported_collect_mode` in this draft |
| `stream` | yes | reserved; fails with `unsupported_collect_mode` in this draft |

An event, and a request with neither `collect` nor `deadline`, creates no Ticket and returns the accepted Message.

`wait` changes how long `send` stays open. It does not change the underlying Message, Delivery, or Ticket.

The Runtime reports `wait_hold_seconds` in `JoinResult`. `send` with `collect=wait` stays open until the first of:

- the Ticket becomes terminal
- `wait_hold_seconds` elapses after this `send` call

When the hold elapses and the Ticket is still `open`, `send` returns that Ticket. The Client then calls `get_result` with the request Message id. A Client that loses its connection during `wait` does the same.

`ticket` returns immediately even if the recipient has already replied. The returned Ticket may therefore be `open` or terminal.

`callback` and `stream` are named so their contract is fixed and adding them later is an addition, not a reshape. Until they are implemented, a `send` that requests them fails with `unsupported_collect_mode` and creates nothing.

## Delivery

A Delivery is one attempt to handle a Message. It contains:

- the immutable Message
- an exclusive `lease_id`
- the lease expiry
- the attempt number
- a bounded recent window of the Message's Thread history
- a flag stating whether that window is the complete history

The first attempt is `1`. Every recovery after lease release or expiry increments it. The Message id never changes across attempts.

### Delivery example

```json
{
  "lease_id": "f5f3ae7a-45a2-420d-992f-45812cf3018a",
  "lease_expires_at": "2026-08-18T15:02:00Z",
  "attempt": 1,
  "message": {
    "id": "15c44926-4c2a-4a01-a13b-95152da9a859",
    "sender": "researcher@content-squad",
    "recipient": "writer@content-squad",
    "kind": "request",
    "content": {
      "task": "Draft a two-paragraph summary"
    },
    "created_at": "2026-08-18T15:00:00Z",
    "trace_id": "e26e64ce-f7f1-47c4-a323-e3a3867e7d28",
    "deadline": "2026-08-18T15:10:00Z",
    "thread_id": "4364a17f-80af-4db8-93e2-6ab85d174a20"
  },
  "history": [],
  "history_complete": true
}
```

### Delivery guarantee

Within the Runtime's reported persistence boundary, an accepted Message is offered for handling at least once unless its reply deadline expires first. A `volatile` Runtime may lose pending work only when its process exits. Delivery is pull-based and lease-protected:

- one active lease grants one Session exclusive handling rights
- another Session cannot receive the same Delivery while the lease is valid
- expiry or Session loss may create another attempt
- Clients MUST treat repeated attempts with the same Message id as the same work

When several Instances share a Membership, they pull from one Mailbox and each Delivery is leased to exactly one Instance. Consecutive turns of one Thread MAY land on different Instances. Conversation state belongs to the retained Thread transcript, not to an Instance. A handler that needs earlier turns reads `history` on the Delivery and pages the rest with `get_history`. Working memory that lives only in one running copy is lost if another Instance handles the next turn.

At-least-once handling means side effects inside an Agent can repeat. An Agent that performs external side effects SHOULD make them idempotent using the Message id.

## Handler outcome

A Client maps a handler outcome according to the delivered Message:

| Delivered Message and outcome | Runtime operation | Ticket effect |
| --- | --- | --- |
| reply-expected request returns content | `reply` with `outcome=completed` | `completed` |
| reply-expected request is declined | `complete` | `declined` |
| reply-expected request raises a safe error | `reply` with `outcome=failed` | `failed` |
| event or no-reply request finishes | `complete` | no Ticket exists |

Declining is a first-class, benign outcome. A recipient may read a request and choose not to answer, the way a person ignores a message that does not warrant a reply. The Ticket becomes `declined`, which is explicit to the requester and is not a failure. A Client declines by calling `complete` on a reply-expected Delivery, so an SDK that maps a handler returning nothing to `complete` produces `declined`. To answer with deliberately empty content instead, the Client replies with `outcome=completed` and `content=null`.

A handler failure becomes an `ErrorObject` with `code=handler_failed`. The Client SHOULD include a safe message for the requester and MUST NOT expose secrets or an unfiltered stack trace.

## Ticket

A Ticket is the requester's durable result record. Its `id` equals the request Message id. The recipient does not own or read it.

Ticket states are closed and exhaustive:

| State | Required data | Terminal |
| --- | --- | --- |
| `open` | no response or error | no |
| `completed` | one response Message | yes |
| `failed` | one `ErrorObject` | yes |
| `expired` | `ErrorObject` with `code=deadline_exceeded` | yes |
| `declined` | none; the recipient chose not to answer | yes |

The only state transitions are:

```text
open -> completed
open -> failed
open -> expired
open -> declined
```

`declined` and `expired` both mean no answer, and they differ in intent: `declined` is the recipient's deliberate choice not to respond, while `expired` is the deadline passing, whether or not anyone handled the request.

A terminal Ticket MUST NOT reopen or replace its stored result.

`updated_at` initially equals `created_at`. It changes when the Ticket becomes terminal and whenever `late_reply_count` changes. A terminal outcome is immutable even though those observation fields may change.

The first accepted reply wins. Idempotent replay of that same reply returns the stored result and does not count as another reply. A distinct later reply tied to a retained Delivery for the same recipient, or such a reply racing with expiry:

- does not change the Ticket
- increments `late_reply_count`
- fails the `reply` operation with `ticket_closed`

`get_result` is repeatable. Reads with no intervening state transition or late reply return identical data while the Ticket is retained.

### Ticket retention

An open Ticket, the request Message it names, and any Thread Messages needed to resolve it MUST remain readable until at least the Ticket `deadline`. A Runtime MUST NOT evict that data because a generic retention interval elapsed while the Ticket is still `open`.

After a Ticket becomes terminal, the Runtime retains it until the later of the Ticket `deadline` and a documented interval after the terminal transition. `get_result` returns `not_found` only after that retention ends.

Count and age limits on Thread history apply only to Messages that no open Ticket still needs.

### Completed Ticket example

```json
{
  "id": "15c44926-4c2a-4a01-a13b-95152da9a859",
  "requester": "researcher@content-squad",
  "recipient": "writer@content-squad",
  "thread_id": "4364a17f-80af-4db8-93e2-6ab85d174a20",
  "state": "completed",
  "created_at": "2026-08-18T15:00:00Z",
  "updated_at": "2026-08-18T15:00:08Z",
  "deadline": "2026-08-18T15:10:00Z",
  "late_reply_count": 0,
  "response": {
    "id": "2f45a4a6-9bbf-4f7b-bb8a-451a7285bf22",
    "sender": "writer@content-squad",
    "recipient": "researcher@content-squad",
    "kind": "response",
    "content": "Draft complete.",
    "created_at": "2026-08-18T15:00:08Z",
    "trace_id": "e26e64ce-f7f1-47c4-a323-e3a3867e7d28",
    "parent_id": "15c44926-4c2a-4a01-a13b-95152da9a859",
    "thread_id": "4364a17f-80af-4db8-93e2-6ab85d174a20"
  }
}
```

## Thread and history

A Thread is an opaque UUID shared by related Messages among a fixed participant set. The set contains the first Message's sender and recipient, so it has one Membership for a self-send or two Memberships otherwise. The Runtime stores retained Messages under `thread_id`.

The first accepted Message using a `thread_id` fixes that participant set. Later Messages may travel only within it. A send that introduces another sender or recipient fails with `forbidden` and reveals no history.

When `parent_id` and `thread_id` are both present, the parent MUST exist in the same Thread. A sender may name only a parent Message it was authorized to receive or created itself. A missing or unauthorized parent returns `not_found`; a visible parent from another Thread returns `invalid_request`.

### Delivered history window

A Delivery carries a bounded recent window of its Thread, not the whole transcript:

- `history` contains Messages accepted before the delivered Message
- it is ordered by `created_at`, then Message id
- it excludes the currently delivered Message
- it holds at most `delivery_history_limit` Messages, reported in `JoinResult`
- its UTF-8 JSON encoding MUST NOT exceed `max_message_bytes`; the Runtime drops oldest Messages from the window until both caps hold
- `history_complete` is `true` when the window already contains every earlier retained Message
- an empty complete history is `[]` with `history_complete=true`

Whichever cap is hit first truncates the window. `history_complete` is `false` when either cap dropped earlier Messages.

This keeps every Delivery bounded no matter how long a Thread grows.

### Reading older history

`get_history` pages the retained Thread transcript. A participant reads a page of Messages older than a cursor, ordered by `created_at` then Message id, and `has_more` states whether older retained Messages remain. Only a Thread participant may read its history; a non-participant receives `not_found`.

`before` is a Message id. Omit it to read the newest page.

- a well-formed UUID that is missing from the retained transcript, including one retention has removed, is treated as "return the newest page"
- a value that is not a UUID fails with `invalid_request`

The Runtime MAY limit Thread retention by age or Message count. It MUST document the limit. It MUST NOT drop a Message that an open Ticket still needs in order to resolve. When retention has removed the oldest Messages, `get_history` returns the oldest that remain and MUST NOT fabricate the missing ones. Retention removes history only; it does not change Message, Delivery, or Ticket state.

The current draft defines grouping, the delivered window, and paged retrieval. It does not define an explicit Thread object or a close operation; a Thread ends by retention.

## Behavioral vectors

These vectors are normative summaries. An implementation test may express them in any test framework.

| Situation | Required observation |
| --- | --- |
| same `send` id, same request | original Message and current Ticket; one Delivery only |
| same `send` id, changed content | `id_conflict`; original state unchanged |
| `send` body over `max_message_bytes` | `payload_too_large`; no Message, Delivery, or Ticket |
| Session disconnect with open Ticket | Ticket remains readable; Message becomes leaseable again if unfinished |
| lease expires | next attempt has the same Message id and a higher `attempt` |
| reply copies request `trace_id` | response and request share one `trace_id` |
| two replies race | one terminal result; loser receives `ticket_closed`; `late_reply_count` increases |
| deadline wins a race | Ticket is `expired`; later reply cannot replace it |
| `get_result` twice with no intervening write | identical stored Ticket |
| reply-expected request declined via `complete` | Ticket `declined`; not a failure |
| reply with `content=null` | Ticket `completed` with null content |
| `complete` for an event or no-reply request | Delivery finished; no Ticket |
| Thread longer than the window | Delivery `history_complete=false`; `get_history` pages the remainder |
| Thread window exceeds `max_message_bytes` | Delivery `history` truncated by size; `history_complete=false` |
| `get_history` for a non-participant | `not_found`; no history revealed |
| `get_history` `before` a well-formed UUID not in the retained transcript | newest page; same shape as omitting `before` |
| `get_history` `before` a non-UUID | `invalid_request` |
| open Ticket whose deadline has not passed | `get_result` returns the Ticket after the terminal-retention interval would have elapsed |
| `collect=wait` hold elapses while the Ticket is `open` | `send` returns `status=ticketed` with that Ticket; `get_result` still reads it |
| two Instances handle consecutive turns of one Thread | each Delivery is leased to one Instance; the later Delivery's `history` contains the earlier turn |
| another Membership submits a retained `lease_id` | `not_found`; no Delivery or Ticket state changes |
| `collect=callback` or `collect=stream` | `unsupported_collect_mode`; nothing created |
