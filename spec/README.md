# AgentConnect Specification

AgentConnect is the Runtime for Teams of independent AI agents. A Runtime binds each Membership to an Agent identity and stable Address, keeps accepted work in Mailboxes, records outstanding results as Tickets, and exposes the Team through code, HTTP, and MCP.

An Agent remains opaque. It may contain one model call, a graph of sub-agents, deterministic software, or a human. AgentConnect defines how Agents join a Team and exchange work. It does not define what happens inside an Agent.

## Status

| Field | Value |
| --- | --- |
| Contract | `1.0.0-draft` |
| Stability | Draft, pre-1.0 |
| Structural source | [`schema/schema.ts`](schema/schema.ts) |

This specification is one evolving document drafted toward the frozen `1.0` contract. It is not versioned per package release.

Before `1.0` any part of this specification may change, and there is no backward-compatibility guarantee. A Runtime and its Clients ship together and MUST implement the same draft contract. The `1.0` release freezes the contract and publishes the compatibility policy from that point on.

The specification grows by addition. Later capability is expected to append new operations, fields, and objects. When something already defined turns out wrong, it is corrected in place.

## Scope

The current draft defines one Team and the Agents that belong to it:

- Team membership, authenticated Sessions, and concurrent Instances of one Membership
- Agent names, Addresses, Profiles, and local discovery
- Messages, Mailboxes, pull delivery, and exclusive leases
- reply-expected requests, collection strategies, and Tickets
- Threads, bounded delivered history, and paged history retrieval
- the Session event stream
- embedded and HTTP Runtime access
- the Team's MCP tools
- operator status, join-token issue and revoke, and the Trace timeline for one causal operation

Anything not defined by these files is outside the current draft. Cross-team delivery, external-content provenance labeling, topic broadcast and subscription, and payments are later additions and are intentionally absent here.

## Core model

| Term | Meaning |
| --- | --- |
| **Agent** | One logical specialist with an identity, Profile, Address, and Mailbox. |
| **Team** | The durable trust, naming, and delivery boundary that Agents join. |
| **Runtime** | The software that serves one Team and owns its shared state. |
| **Client** | The Agent-side software that joins a Runtime, leases work, and returns results. |
| **Membership** | The durable relationship between one Agent and one Team. |
| **Instance** | One running copy of an Agent holding one Session for a Membership. |
| **Session** | Short-lived authority for one Instance to act as its Membership. |
| **Mailbox** | The Membership's logical queue of accepted work. |
| **Message** | An immutable request, event, response, or error accepted by the Runtime. |
| **Delivery** | One leased attempt to handle a Message. |
| **Ticket** | The requester's durable record for one reply-expected Message. |
| **Trace** | Ordered events the Runtime recorded for one `trace_id`. |
| **Thread** | Messages grouped under one `thread_id`, with retained history. |
| **Profile** | Discovery information describing an Agent's Skills. |
| **Address** | A human- and model-readable Agent name, optionally qualified by location. |
| **Directory** | The Profiles and Addresses of a Team's Memberships. |

The boundaries are strict:

- A Runtime stores shared communication state. It does not hold Agent objects or call Agent methods.
- Clients pull Deliveries when they have capacity.
- Membership survives Session loss. A Membership may have several concurrent Instances that share one Mailbox.
- The Mailbox is one logical queue. A Runtime MAY partition it across backends to scale a single busy Agent; partitioning changes no observable rule except that there is no total order across the Mailbox.
- Session loss releases that Session's leases but does not delete the Membership, accepted Messages, Tickets, or retained Thread history.
- The Runtime, not the sending payload, sets the verified sender and every other Runtime-owned field on an accepted Message.
- A Profile is returned only by explicit discovery. The Runtime does not inject Profiles into an Agent's input.

## Files and authority

| File | Owns |
| --- | --- |
| [runtime.md](runtime.md) | Runtime state, operations, persistence, and failure behavior |
| [messaging.md](messaging.md) | Message, Delivery, Ticket, and Thread semantics |
| [addressing.md](addressing.md) | names, Addresses, Profiles, and Directory search |
| [security.md](security.md) | Agent identity, join authentication, Sessions, and sender attribution |
| [schema/schema.ts](schema/schema.ts) | exact public object and field shapes |
| [bindings/http.md](bindings/http.md) | HTTP representation of Runtime operations |
| [bindings/mcp.md](bindings/mcp.md) | model-facing MCP tools |
| [CHANGELOG.md](CHANGELOG.md) | public specification history |

Behavior belongs to the Markdown file named above. Structure belongs to `schema/schema.ts`. Examples explain those two sources; they do not create a third definition.

`schema/schema.json` is generated from TypeScript and must not be edited by hand.

## Normative words

The uppercase words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** identify requirements.

- **MUST** and **MUST NOT** define conformance.
- **SHOULD** and **SHOULD NOT** permit a deviation only when its consequences are understood and documented.
- **MAY** marks an allowed choice.

Lowercase uses of the same words are ordinary prose.

## Field discipline

Every schema-defined public object rejects fields not declared on that object. Extensible application data belongs only in fields whose schema explicitly accepts arbitrary JSON, such as Message `content` and `metadata`.

## Schema workflow

From `spec/schema/`:

```text
npm install
npm run generate
npm run check
```

`npm run check` must succeed without changing `schema.json`.

## Reading order

1. [runtime.md](runtime.md)
2. [messaging.md](messaging.md)
3. [addressing.md](addressing.md)
4. [security.md](security.md)
5. [schema/schema.ts](schema/schema.ts)
6. the required binding
