# MCP binding

A Team exposes AgentConnect tools through MCP. The tools are the model-facing form of Runtime operations. Their results use the public objects in [schema/schema.ts](../schema/schema.ts).

The MCP server is a Runtime Client. It authenticates the caller, performs Runtime operations on that caller's Session, and keeps no correctness state of its own.

When the Runtime is served over HTTP, this binding is mounted at `{origin}/mcp` using streamable HTTP with no sticky routing.

```text
http://127.0.0.1:9000/mcp
```

## Authentication

Every tool call MUST identify one valid member Session. The server derives the sender from that Session. Tool arguments never include `sender`, `agent_did`, or `session_token`.

```http
Authorization: Bearer <session_token>
```

A missing, malformed, expired, replaced, or revoked Session token is an MCP-level authentication failure, except for the loopback operator case below.

This Session binding applies to every tool call, including additional Team tools, and to every resource read, including the roster.

### Loopback operator

On a loopback listener, a call with no `Authorization` header is bound to a Runtime-owned principal Membership named `operator` only on a trusted loopback hosting path. That path requires an HTTP peer on loopback and no forwarded-client headers (`Forwarded`, `X-Real-IP`, or any `X-Forwarded-*` name, including empty values). The Runtime reserves the name when it starts and keeps a Session for it. Loopback HTTP Runtime routes use the same Membership. The operator has no Profile, Directory entry, or Mailbox.

A missing header by itself is not local authority. A reverse proxy in front of a loopback listener is not that path. Those calls MUST send a Session token.

The name `operator` is reserved for this Membership. A join that uses it fails with `name_conflict`.

A present `Authorization` header is never treated as the operator. It MUST name a valid Session. An empty or malformed `Authorization` header is an MCP-level authentication failure.

In-process MCP uses the same operator Membership when that server is hosted as in-process and no `Authorization` header is present. Missing HTTP request context does not imply that hosting mode.

Authenticating a Session MUST NOT extend expiry. `heartbeat` remains the Session renewal operation. It does not extend Delivery leases.

```http
POST /mcp
(no Authorization)

→ find, ask, tell, get_result, get_history, get_profiles, additional tools, and roster read run as operator
```

```http
Authorization: Bearer <session_token of writer>

→ the same tools and the roster run as writer
```

```http
POST /mcp
X-Forwarded-For: 203.0.113.10
(no Authorization)

→ MCP-level authentication failure
```

```http
POST /mcp
X-Forwarded-For:
(no Authorization)

→ MCP-level authentication failure
```

## Core tools

The tool names are:

- `find`
- `ask`
- `tell`
- `get_result`
- `get_history`
- `get_profiles`

Names and argument meanings are stable within a released contract. This set is deliberately small. A model finds a peer, reads selected Profiles, sends work and collects the result, and reloads a conversation when it needs the earlier context.

The advertised `tools/list` input schema for each of these tools is that tool's public argument type. The advertised success output schema is that tool's public result type. MCP structured content may be any JSON value; these tools return JSON objects, advertised with `type: object`. Tagged unions such as `TicketView` keep their `oneOf`/`anyOf` variants on that object. A client that validates arguments against the advertised schema MUST accept and reject the same values the server rejects as MCP invalid-params: required fields, omit-only optional fields, bounds, enumerations, identifier patterns, and undeclared properties. JSON `null` is valid only where the public type includes null, such as `content`. Setting `additionalProperties` to `false` is not enough on its own.

## `find`

`find` maps to the Runtime `find` operation.

Arguments:

```json
{
  "query": "someone who can review a contract",
  "limit": 5
}
```

- `query` is required, contains 1 to 1,000 characters, and includes at least one non-whitespace character.
- `limit` is optional, between `1` and `100`. Omit it to return every remaining member, at most 100.

The server MUST validate these arguments as sent. A string `limit`, JSON `null`, or an undeclared field is an MCP-level invalid-params failure. The advertised tool schema MUST reject the same values.

Result: `FindResult`. Matches are ordered best-first. The result does not name the embedding backend or a fallback. Each match is a light card so a model can scan a whole Team cheaply. Ranked matches are candidates, not proof of suitability. Overlapping cards need `get_profiles`. Reuse cards already read. A caller may conclude nobody fits. To read selected candidates in depth, call `get_profiles` with those Addresses.

The tool searches only the caller's Team and excludes the caller. Ranking does not choose a later `ask` or `tell` recipient.

## `get_profiles`

`get_profiles` maps to the Runtime `get_profile` operation for each requested Address.

Arguments:

```json
{
  "addresses": ["writer", "editor"]
}
```

`addresses` is required. It is a nonempty array of local or same-Team qualified Addresses, at most 20. Duplicate requested strings are read once, keeping the first. Result items follow that remaining order.

Result: `GetProfilesResult`. Each item is `ProfileFound` (`status: ok`, canonical Address, full Profile) or `ProfileMiss` (`status: error`, the requested string, and an `ErrorObject`). Missing members and principals are per-item `not_found`. `forbidden` and `address_outside_team` are also per-item. Other requested Profiles still return. An `unauthorized` lookup fails the whole call. Runtime, HTTP, and Client `get_profile` / `get_entry` still return one `DirectoryEntry`.

Advertised MCP success output schemas are the public result types for these six tools. Domain errors stay on the structured error path and are not those success schemas.

## `ask`

`ask` sends work that needs a reply. The server generates the request Message id. When `deadline_seconds` is present, the server converts it into an absolute UTC deadline. When it is omitted, the Runtime inherits a request parent's stamped deadline or applies `work_lifetime_seconds`. `collect` has the same meaning as on Runtime `send` and on Client `ask`. Prefer `ask` over `tell` when a reply is required; `tell` does not create a Ticket, so a caller that needed an answer gets none and no error from `tell` itself.

Arguments:

```json
{
  "recipient": "writer",
  "content": {
    "task": "Draft a short summary"
  },
  "deadline_seconds": 600,
  "collect": "wait",
  "thread_id": "4364a17f-80af-4db8-93e2-6ab85d174a20",
  "idempotency_key": "draft-summary-1"
}
```

| Field | Requirement |
| --- | --- |
| `recipient` | required Address |
| `content` | required JSON value |
| `deadline_seconds` | optional integer from `1` to `86400`. Omit to inherit a request parent deadline or the Runtime work lifetime |
| `collect` | optional `wait` or `ticket`, default `wait` |
| `thread_id` | optional UUID |
| `idempotency_key` | optional string, 1 to 200 characters |

The server returns the current `TicketView`. Runtime, HTTP, and Client `ask` still return the wire `Ticket`. `collect` has the same bounded-hold meaning as Runtime `send`.

- `collect=wait` (default) holds until the Ticket is terminal or `wait_hold_seconds` elapses, then returns the current TicketView, which may still be `open`.
- `collect=ticket` returns immediately with the current TicketView, which may still be `open`.
- A pending result is an `open` TicketView, not hidden MCP session state. The model keeps `ticket_id` and passes it to `get_result`. Ending the wait does not cancel work. Do not send a second `ask` to collect.
- `deadline_seconds` is a work cutoff. It is not how long this call waits and not an ETA.
- The server MUST NOT keep polling `get_result` after the Runtime wait hold ends.

### Conversation continuity

Omitting `thread_id` starts a fresh conversation. The server mints a Thread and returns it on the TicketView. A keyed retry with the same omitted `thread_id` reuses that generated Thread. Passing a returned `thread_id` back into a later `ask` or `tell` continues that conversation only with a current participant. The recipient then receives the earlier turns as Delivery history.

A Thread's participant set is fixed at creation. A send that names a sender or recipient outside that set fails with `forbidden` and reveals no history. To contact another peer, omit `thread_id` and put any needed context in `content`. Do not assume the new peer can read the old Thread.

`ask` with an omitted `thread_id` always starts a Thread; that is the usual way to start work. A well-formed unused `thread_id` also starts a conversation. `tell` with an omitted `thread_id` is unthreaded; that is the usual path for a notice. To start over, omit `thread_id` and omit `idempotency_key`. Reuse a returned `thread_id` to continue with a current participant.

```json
{"recipient": "writer", "content": "tighten section 2", "thread_id": "4364a17f-80af-4db8-93e2-6ab85d174a20"}
```

Same conversation with `writer`.

```json
{"recipient": "editor", "content": "tighten this draft:\n..."}
```

New peer: omit `thread_id`. Including the writer Thread id here is `forbidden`.

### Idempotency

A model tool call may be retried by the framework. Retry collapsing is opt-in.

When `idempotency_key` is present, the request Message id is UUID5 of `ask|<caller_address>|<idempotency_key>`. An omitted `thread_id` is UUID5 of `ask-thread|<caller_address>|<idempotency_key>`. A later `ask` from the same caller with the same key and the same semantic arguments recovers those generated values and returns the original TicketView, including its original stamped deadline.

Semantic arguments for `ask` are `recipient`, `content`, `collect`, a caller-supplied `thread_id`, and whether `deadline_seconds` was supplied. Changing any of them under the same key fails with `id_conflict`. Repeating the same relative `deadline_seconds` later still replays; the accepted absolute deadline does not move. Repeating an omitted `deadline_seconds` also replays.

When `idempotency_key` is omitted, the server mints a fresh UUID and, when `thread_id` is omitted, a fresh Thread. Two clients, or one client on two connections, that send identical arguments open two Tickets.

```json
{"recipient": "writer", "content": "same", "deadline_seconds": 30}
```

Two such `ask` calls produce two Tickets, even when their JSON-RPC request ids are both `1`.

```json
{"recipient": "writer", "content": "same", "deadline_seconds": 30, "idempotency_key": "draft-1"}
```

Two such `ask` calls from the same caller return one TicketView.

```json
{"recipient": "writer", "content": "other", "deadline_seconds": 30, "idempotency_key": "draft-1"}
```

After the first keyed `ask` above, this call fails with `id_conflict`. The readable message names `idempotency_key`. Retry the identical arguments unchanged, or use a new key only for new work. Do not drop the key after an uncertain accept; that can duplicate work.

## `tell`

`tell` sends work that does not need a reply and never creates a Ticket. Prefer `ask` when a reply is required, including acknowledgement that a notice was processed. A caller that needed an answer and used `tell` gets none and no error from `tell` itself. The server generates the Message id.

Arguments:

```json
{
  "recipient": "writer",
  "content": {
    "notice": "The source material changed"
  },
  "thread_id": "4364a17f-80af-4db8-93e2-6ab85d174a20",
  "idempotency_key": "source-changed-1"
}
```

`recipient` and `content` are required. `thread_id` and `idempotency_key` are optional, with the same idempotency behavior as `ask`. A keyed `tell` uses `tell|` in the UUID5 material instead of `ask|`. Changed keyed `recipient`, `content`, or `thread_id` fail with `id_conflict`. The server MUST NOT convert that conflict into a success envelope. The readable conflict message names `idempotency_key` and the same recovery rule as `ask`.

Omitting `thread_id` leaves the event unthreaded. Passing a Thread id continues that conversation only when the recipient is already a participant; otherwise the call is `forbidden`.

Result: `TellView` (`status: accepted` and `thread_id` only when the event joined a Thread). `accepted` means the Runtime queued the event, not that the recipient finished processing. A later `ask` may miss this notice if it runs before processing. If later work depends on the notice, include the fact in that ask, or ask for an acknowledgement. Runtime, HTTP, and Client `tell` still return `AcceptedSendResult`. An unthreaded notice omits `thread_id`.

## `get_result`

`get_result` maps to the Runtime operation of the same name, then returns the model-facing `TicketView`.

Arguments:

```json
{
  "ticket_id": "15c44926-4c2a-4a01-a13b-95152da9a859"
}
```

Result: the current `TicketView`. Branch on `state`. Timing is not proof of state. Open views include `deadline` (work cutoff stamped at acceptance) and `poll_interval_ms` (a get_result hint). Terminal views omit timing. The read is repeatable and does not consume the result. Only the Membership that opened the Ticket may read it, including after Session replacement for that Membership. A completed Ticket stays completed after its original deadline while it is retained.

## `get_history`

`get_history` maps to the Runtime operation of the same name. A model uses it to reload earlier turns of a long conversation that no longer fit in a Delivery's history window.

Arguments:

```json
{
  "thread_id": "4364a17f-80af-4db8-93e2-6ab85d174a20",
  "before": "2f45a4a6-9bbf-4f7b-bb8a-451a7285bf22",
  "limit": 50
}
```

- `thread_id` is required.
- `before` is optional. Omit it for the newest page, or pass `next_before` from the previous page.
- `limit` is optional, between `1` and `200`, and defaults to `50`.

Result: `HistoryView`. Turns are ordered by `seq` ascending and carry `id`, `seq`, `sender`, `created_at`, `kind`, and `content` or `error`. Response and error turns also carry `parent_id`, the request Message id they answer (the same value as that ask's `ticket_id`). The newest page is returned first; that does not reverse order inside the page. When `has_more` is true, `next_before` is the Message id to pass as the next `before`. When `has_more` is false, `next_before` is omitted; stop paging. Runtime, HTTP, and Client `get_history` still return `HistoryResult`. Only a Thread participant may read it. Any other caller receives `not_found`.

## Roster resource

The server publishes the Team roster as an MCP resource at `agentconnect://team/roster`. The body is `TeamRoster`.

Reading the resource uses the same Session binding as a tool call. A missing, malformed, expired, replaced, or revoked Session token is an MCP-level authentication failure, except for the loopback operator case above.

The resource lists every current Agent Membership. Principals, including `operator`, are omitted. It is not a search. Models that need ranking use `find`.

## Errors

Authentication and malformed tool calls use MCP-level errors. Runtime failures set the MCP error flag and return `ToolErrorResult` as structured content. The `error.code` is the unchanged Runtime code. Readable text is `code: message`. For a keyed `ask`/`tell` `id_conflict`, `message` names `idempotency_key` and how to recover; other failures keep the Runtime message.

The server MUST preserve the Runtime error code. It MUST NOT turn `busy`, `not_found`, `payload_too_large`, `address_outside_team`, or another Runtime failure into invented success text. A missing required argument remains an MCP invalid-params failure, distinct from a `failed` Ticket.

## Additional Team tools

A Team may expose its own tools beside the AgentConnect tools. Those tools are outside this specification and MUST NOT reuse the reserved names.

Every additional tool call passes the same Session boundary as `find` and the roster resource. The extra tool keeps its own arguments and result. It MUST NOT run when that boundary rejects the caller.

An additional tool that sends work to an Agent must call the Runtime as the authenticated member. It must not bypass sender attribution, Mailboxes, Deliveries, or Tickets.

## Statelessness

The MCP server may cache transport data, but correctness state belongs to the Runtime:

- Tickets remain readable after the MCP connection closes.
- Another MCP server process can serve `get_result` for the same authenticated Membership.
- Tool calls do not require sticky routing to one MCP server process.
- Losing an MCP response does not cancel an accepted Runtime operation.
