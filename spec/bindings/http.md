# HTTP binding

This binding maps Runtime operations to HTTP. It does not change the behavior defined in [runtime.md](../runtime.md), [messaging.md](../messaging.md), [addressing.md](../addressing.md), or [security.md](../security.md).

## Base path

All routes use the Runtime origin plus `/agentconnect/v1`.

Example:

```text
https://content-squad.example.com/agentconnect/v1
```

The `agentconnect` segment is Runtime machinery, and `v1` is this binding's major version, independent of the `spec_version` draft carried in `join`.

Request and response bodies use UTF-8 JSON with:

```http
Content-Type: application/json
```

Every schema-defined public object rejects fields not declared on that object.

## Routes

| Runtime operation | Method and path | Request | Success result |
| --- | --- | --- | --- |
| join challenge | `GET /join/challenge` | none | `JoinChallenge` |
| `join` | `POST /join` | `JoinRequest` | `JoinResult` |
| `disconnect` | `POST /session/disconnect` | none | `204 No Content` |
| `heartbeat` | `POST /session/heartbeat` | none | `HeartbeatResult` |
| `send` | `POST /messages` | `SendRequest` | `SendResult` |
| `lease` | `POST /mailbox/lease` | `LeaseRequest` | `LeaseResult` |
| `complete` | `POST /deliveries/complete` | `CompleteRequest` | `CompleteResult` |
| `reply` | `POST /deliveries/reply` | `ReplyRequest` | `ReplyResult` |
| `get_result` | `GET /tickets/{ticket_id}` | none | `Ticket` |
| `get_history` | `GET /threads/{thread_id}/history` | query `before`, `limit` | `HistoryResult` |
| `find` | `POST /directory/find` | `FindRequest` | `FindResult` |
| `get_profile` | `GET /directory/members/{address}` | none | `DirectoryEntry` |
| `status` | `GET /status` | none | `StatusResult` |
| `get_trace` | `GET /traces/{trace_id}` | none | `TraceResult` |
| `issue_join_token` | `POST /tokens` | `IssueJoinTokenRequest` | `JoinTokenIssued` |
| `revoke_join_token` | `POST /tokens/revoke` | `RevokeJoinTokenRequest` | `204 No Content` |

`GET /traces/events` is the operator watch stream. It is not `get_trace` for a `trace_id` of `events`.

Schema names refer to [schema/schema.ts](../schema/schema.ts).

`{address}` is a local or same-Team qualified Address encoded as one URL path segment. `{ticket_id}`, `{thread_id}`, and `{trace_id}` are UUIDs. The `get_history` query parameters `before` and `limit` map to the fields of `GetHistoryRequest`.

Every successful route MUST return `200 OK` with the listed JSON result, except `disconnect` and `revoke_join_token`, which MUST return `204 No Content` with no body.

## Authentication

`join/challenge` and `join` do not use a Session. Every other route requires a Session.

```http
Authorization: Bearer <session_token>
```

The join token and identity proof remain inside `JoinRequest`. They MUST NOT be copied into the `Authorization` header.

Missing, malformed, expired, replaced, or revoked Session credentials return `401` with `code=unauthorized`.

### Loopback operator

On a loopback listener, a call with no `Authorization` header is bound to the reserved `operator` Membership, the same Membership loopback MCP uses. A present `Authorization` header is never treated as the operator. It MUST name a valid Session.

A non-loopback listener MUST NOT bind a missing header to `operator`. That request returns `401`.

Responses from `/join/challenge`, `/join`, and `/session/heartbeat` MUST include `Cache-Control: no-store`.

## Error responses

Every non-success response has an `ErrorObject` body.

```json
{
  "code": "busy",
  "message": "The recipient mailbox is full.",
  "retryable": true
}
```

| Error code | HTTP status |
| --- | --- |
| `unsupported_version`, `invalid_request`, `invalid_address`, `address_outside_team` | `400` |
| `unauthorized` | `401` |
| `forbidden` | `403` |
| `not_found` | `404` |
| `name_conflict`, `id_conflict`, `lease_expired`, `ticket_closed` | `409` |
| `payload_too_large` | `413` |
| `busy` | `429` |
| `internal` | `500` |
| `unsupported_collect_mode` | `501` |
| `unavailable` | `503` |

Ticket failure codes such as `handler_failed` and `deadline_exceeded` are returned inside a successful `200` Ticket response. They do not describe HTTP failure.

## Send example

```http
POST /agentconnect/v1/messages HTTP/1.1
Authorization: Bearer opaque-session-token
Content-Type: application/json

{
  "id": "15c44926-4c2a-4a01-a13b-95152da9a859",
  "recipient": "writer",
  "kind": "request",
  "content": {
    "task": "Draft a two-paragraph summary"
  },
  "collect": "ticket",
  "deadline": "2026-08-18T15:10:00Z"
}
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "status": "ticketed",
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
    "deadline": "2026-08-18T15:10:00Z"
  },
  "ticket": {
    "id": "15c44926-4c2a-4a01-a13b-95152da9a859",
    "requester": "researcher@content-squad",
    "recipient": "writer@content-squad",
    "state": "open",
    "created_at": "2026-08-18T15:00:00Z",
    "updated_at": "2026-08-18T15:00:00Z",
    "deadline": "2026-08-18T15:10:00Z",
    "late_reply_count": 0
  }
}
```

`collect` is a send-time field. It selects how the sender collects the result and is not stored on the accepted Message.

## Waiting sends

For `collect=wait`, `POST /messages` stays open until the Ticket becomes terminal or `wait_hold_seconds` elapses, whichever is first. The response is HTTP `200` with `SendResult` in either case, including `open`, `failed`, `expired`, and `declined` Tickets.

If the hold elapses while the Ticket is still `open`, the body is a ticketed `SendResult` whose Ticket is `open`. The Client then calls `GET /tickets/{message_id}` until the Ticket is terminal.

If the HTTP connection closes after acceptance, the Runtime keeps the Message and Ticket. The Client calls `GET /tickets/{message_id}` after reconnecting.

Clients SHOULD set their HTTP timeout above `wait_hold_seconds`. Use `collect=ticket` when the caller does not want `send` to hold.

## Idempotency

Message ids provide idempotency for `POST /messages` and `POST /deliveries/reply`.

- same id and same semantic body follows the original collection behavior without creating another Delivery
- same id and changed semantic body, including a changed `collect`, returns `409` with `code=id_conflict`
- the Runtime MUST NOT create a second Message or Delivery

Other successful retries behave as follows:

- `complete` returns the stored `CompleteResult` while its lease record is retained
- `heartbeat` may return a later Session expiry
- `disconnect` followed by a retry with the invalidated Session returns `401`

A Client MUST NOT blindly retry a request whose acceptance is unknown unless the request has a Message id with the semantics above.

## Work notification stream

A Client MAY open:

```http
GET /agentconnect/v1/session/events
Authorization: Bearer <session_token>
Accept: text/event-stream
```

The stream carries `RuntimeEvent` values, one per SSE event, where the SSE `event:` name is the event `type` and `data:` is the event data JSON:

```text
event: work_available
data: {}
```

`work_available` is the only type defined in this draft and is a hint to call `lease`. New event types are added over time; a Client MUST ignore an event type it does not recognize. The Runtime may send comment lines as keepalives.

The response uses `Content-Type: text/event-stream` and `Cache-Control: no-store`. The Runtime MUST close the stream when the Session is invalidated.

Lost, duplicated, or delayed stream events do not lose work. A Client can ignore the stream and poll `lease`; Mailbox and Ticket correctness cannot depend on the stream.

## Trace watch stream

An operator Client MAY open:

```http
GET /agentconnect/v1/traces/events
Authorization: Bearer <operator session_token>
Accept: text/event-stream
```

On loopback the `Authorization` header MAY be omitted, as for other operator routes.

Each SSE event is a `RuntimeEvent` whose `type` is `trace` and whose `data` is one `TraceEvent`. Comment keepalives follow the Session stream rules. A non-operator Session fails with `403` and `code=forbidden` instead of opening the stream.

The stream starts at subscription time. It does not replay stored events. `GET /traces/{trace_id}` is the complete record.

The Runtime MUST close the stream when the Session is invalidated.

## HTTP transport rules

- A non-loopback Runtime MUST use HTTPS.
- A Runtime MUST NOT redirect a request carrying a Session token, `join_token`, or `identity_proof` to another origin.
- A Runtime MUST reject a `send` body larger than `max_message_bytes` with `413` and `code=payload_too_large`.
- Clients SHOULD honor `Retry-After` on `429` and `503`.
- Clients MAY retry `GET` requests and idempotent Message writes after connection failure.
- JSON timestamps use UTC RFC 3339 form with a trailing `Z`.
