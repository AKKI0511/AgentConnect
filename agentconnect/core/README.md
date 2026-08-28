# Core

Shared nouns for the runtime and the agent client. This package has no I/O and does not import other AgentConnect packages.

```
core/
  address.py     Address grammar and same-Team resolution
  message.py     Immutable Message
  kinds.py       MessageKind: request, response, error, event
  identity.py    AgentIdentity (Ed25519 did:key), join proofs, attestations
  profile.py     AgentProfile, Skill, Capability
  types.py       Enumerations (provider, agent type, protocol version)
  exceptions.py  Shared exception types
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

`Message.kind` is one of `request`, `response`, `error`, or `event`. Application typing belongs in `content` or `metadata`. Control labels such as `stop` and `cooldown` are stored as `metadata["control"]`.
