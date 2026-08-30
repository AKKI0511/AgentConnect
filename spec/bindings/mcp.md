# MCP binding

A Team exposes five AgentConnect tools through MCP. The tools are the model-facing form of Runtime operations. Their results use the public objects in [schema/schema.ts](../schema/schema.ts).

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

### Loopback operator

On a loopback listener, a call with no `Authorization` header is bound to a Runtime-owned Membership named `operator`. The Runtime creates that Membership on first use and keeps a Session for it. Loopback HTTP Runtime routes use the same Membership.

The name `operator` is reserved for this Membership. A join that reuses it with a different DID fails with `name_conflict`.

A present `Authorization` header is never treated as the operator. It MUST name a valid Session.

```http
POST /mcp
(no Authorization)

→ find, ask, tell, get_result, and get_history run as operator
```

```http
Authorization: Bearer <session_token of writer>

→ the same tools run as writer
```

## Core tools

The tool names are:

- `find`
- `ask`
- `tell`
- `get_result`
- `get_history`

Names and argument meanings are stable within a released contract. This set is deliberately small. A model finds a peer, sends work and collects the result, and reloads a conversation when it needs the earlier context.

## `find`

`find` maps to the Runtime `find` operation.

Arguments:

```json
{
  "query": "someone who can review a contract",
  "limit": 5,
  "detail": "summary"
}
```

- `query` is required, contains 1 to 1,000 characters, and includes at least one non-whitespace character.
- `limit` is optional, between `1` and `100`. Omit it to return every remaining member, at most 100.
- `detail` is optional, `summary` or `full`, and defaults to `summary`.

Result: `FindResult`. Each match is a light card by default so a model can scan a whole Team cheaply. `detail=full` adds the Agent DID and full Profile. The model reads one candidate in depth with a follow-up `find` at `full` detail if it needs more than the card shows.

The tool searches only the caller's Team and excludes the caller.

## `ask`

`ask` sends a reply-expected request with `collect=ticket`. The server generates the request Message id and converts `deadline_seconds` into an absolute UTC deadline.

Arguments:

```json
{
  "recipient": "writer",
  "content": {
    "task": "Draft a short summary"
  },
  "deadline_seconds": 600,
  "wait_seconds": 10,
  "thread_id": "4364a17f-80af-4db8-93e2-6ab85d174a20",
  "idempotency_key": "draft-summary-1"
}
```

| Field | Requirement |
| --- | --- |
| `recipient` | required Address |
| `content` | required JSON value |
| `deadline_seconds` | required integer from `1` to `86400` |
| `wait_seconds` | optional integer from `0` to `30`, default `0` |
| `thread_id` | optional UUID |
| `idempotency_key` | optional string, 1 to 200 characters |

The server returns the current `Ticket`, and the Ticket carries its `thread_id`.

- With `wait_seconds=0`, it returns immediately.
- With a positive value, it waits up to that many seconds for the Ticket to become terminal, then returns its current state.
- A pending result is an `open` Ticket, not hidden MCP session state. The model keeps `ticket.id` and passes it to `get_result`.

### Conversation continuity

Omitting `thread_id` starts a fresh conversation. The server mints a Thread and returns it on the Ticket. Passing that `thread_id` back into a later `ask` or `tell` continues the same conversation, and the recipient receives the earlier turns as Delivery history. To start over, omit `thread_id` again. The model does not invent Thread ids. It reuses the one the server returned.

### Idempotency

A model tool call may be retried by the framework. The server MUST NOT let a retry create a second request.

When `idempotency_key` is present, the request Message id is UUID5 of `ask|<caller_address>|<idempotency_key>`. A later `ask` from the same caller with the same key returns the original Ticket.

When `idempotency_key` is omitted, the request Message id is UUID5 of `ask|<caller_address>|<recipient>|<thread_id or empty>|<canonical JSON of content>|<mcp_request_id>`. `mcp_request_id` is the JSON-RPC request id of this tool call, stringified. The omitted `thread_id` is hashed as empty even if the server later mints a Thread for the send.

A retried MCP request reuses the JSON-RPC id and therefore the same Message id. A second distinct tool call, even with identical arguments, has a different request id and MUST open a second Ticket.

```json
{"recipient": "writer", "content": "same", "deadline_seconds": 30}
```

Two such `ask` calls with different JSON-RPC ids produce two Tickets.

```json
{"recipient": "writer", "content": "same", "deadline_seconds": 30, "idempotency_key": "draft-1"}
```

Two such `ask` calls from the same caller return one Ticket.

## `tell`

`tell` sends an event and never creates a Ticket. The server generates the Message id.

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

`recipient` and `content` are required. `thread_id` and `idempotency_key` are optional, with the same idempotency behavior as `ask` (`tell|` in the UUID5 material instead of `ask|`).

Result: `AcceptedSendResult`.

## `get_result`

`get_result` maps to the Runtime operation of the same name.

Arguments:

```json
{
  "ticket_id": "15c44926-4c2a-4a01-a13b-95152da9a859"
}
```

Result: the current `Ticket`. The read is repeatable and does not consume the result. Only the Session that created the Ticket may read it.

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
- `before` is optional. Omit it for the newest page, or pass the oldest Message id already seen to page further back.
- `limit` is optional, between `1` and `200`, and defaults to `50`.

Result: `HistoryResult`. Only a Thread participant may read it. Any other caller receives `not_found`.

## Roster resource

The server publishes the Team roster as an MCP resource at `agentconnect://team/roster`. The body is `TeamRoster`.

The resource lists every current Membership, including `operator` when that Membership exists. It is not a search. Models that need ranking use `find`.

## Reserved collection strategies

`ask` always uses `collect=ticket`, which covers the model cases. Send work, optionally wait briefly, otherwise poll `get_result`. The `callback` and `stream` strategies are not exposed as MCP tools in this draft. When they are added, they will be additional arguments or tools, not a change to the five names above.

## Errors

Authentication and malformed tool calls use MCP-level errors. Runtime failures set the MCP error flag and return `ToolErrorResult`, whose `error` field is the unchanged Runtime `ErrorObject`.

The server MUST preserve the Runtime error code. It MUST NOT turn `busy`, `not_found`, `payload_too_large`, `address_outside_team`, or another Runtime failure into invented success text.

## Additional Team tools

A Team may expose its own tools beside the five AgentConnect tools. Those tools are outside this specification and MUST NOT reuse the five reserved names.

An additional tool that sends work to an Agent must call the Runtime as the authenticated member. It must not bypass sender attribution, Mailboxes, Deliveries, or Tickets.

## Statelessness

The MCP server may cache transport data, but correctness state belongs to the Runtime:

- Tickets remain readable after the MCP connection closes.
- Another MCP server process can serve `get_result` for the same authenticated member.
- Tool calls do not require sticky routing to one MCP server process.
- Losing an MCP response does not cancel an accepted Runtime operation.
