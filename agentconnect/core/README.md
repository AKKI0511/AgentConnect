# Core models

Describe an agent with `AgentProfile` and `Skill`, then read the typed Messages
and results returned by `BaseAgent`. Discovery matches are candidate cards;
`get_entry` supplies the full Profile and Agent DID when you need them.

A handler receives a request or event Message. A Delivery is the leased attempt
to handle it. Requests open requester-owned Tickets; Threads group conversation
history for a fixed set of participants. Read a Ticket's `state` before its
content or error. Keep an open Ticket's `id` and collect it with `get_result`
rather than submitting the request again. Declined work has no reply or failure.

MCP and Session-bound tools return compact views. A TicketView uses `ticket_id`
and completed content alone; a wire Ticket uses `id` and a response Message.
History views preserve ordering, reply correlation and cursors.

Advanced clients use the operation models, parsers and serialization helpers.
Models reject extra fields and reassignment. `dump_public` leaves omitted
optional fields absent while retaining required JSON-null content.
`public_json_schema` represents those omission rules for wire consumers.

An AgentIdentity owns the Agent key. Persist it to reconnect to a retained
Membership. A fresh identity proof proves key control; a Team join invitation
authorizes admission. A Team-signed membership attestation is neither an
invitation nor a Session bearer and does not grant Runtime access.

See the [Python reference](../../docs-v2/api/core.mdx) for individual contracts
and the [public specification](../../spec/README.md) for wire structures.
