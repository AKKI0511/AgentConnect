# Core

Shared nouns for the Runtime and the Agent Client. This package is the Python
projection of the public schema in ``spec/schema/schema.ts``. It has no I/O
and does not import other AgentConnect packages.

```
core/
  address.py      Address grammar and same-Team resolution
  base.py         Frozen pydantic base for public objects
  primitives.py   Aliases and closed unions (ErrorCode, CollectMode, ...)
  message.py      Message kinds and Delivery
  ticket.py       Ticket union discriminated on state
  profile.py      AgentProfile and Skill
  directory.py    DirectoryEntry, DirectoryMatch, find types
  operations.py   Join, send, lease, reply, status, roster, trace
  error.py        ErrorObject
  identity.py     AgentIdentity (Ed25519 did:key), join proofs, attestations
  kinds.py        MessageKind: request, response, error, event
  projection.py   Name map used by the schema round-trip test
  types.py        Re-exports of primitives, Profile, and MessageKind
  exceptions.py   Shared exception types
```

`BaseAgent` lives in `agentconnect.agent`. The team directory lives in `agentconnect.team.directory`.

## Address

`parse_address` returns a `ParsedAddress` or `invalid_address`. `resolve_address(value, team_name)` returns a canonical `name@team` string, `invalid_address`, or `address_outside_team`.

Input may contain uppercase ASCII letters. Non-ASCII input is invalid. A valid location that is not this Team is `address_outside_team`.

## Identity

`AgentIdentity.create_key_based()` mints an Ed25519 key pair and a `did:key`.
`issue_identity_proof(identity, challenge)` builds the EdDSA JWT a network join
sends as `identity_proof`. `issue_membership_attestation` is the Team-signed
statement that this Team vouches for an Agent. The Runtime stores that JWT; it
does not verify inbound attestations in this release.

## Message kinds

`Message.kind` is one of `request`, `response`, `error`, or `event`. Application typing belongs in `content` or `metadata`. A handler receives a Message with attributes, not a dictionary.
