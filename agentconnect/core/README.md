# Core

Shared nouns for the runtime and the agent client. This package has no I/O and does not import other AgentConnect packages.

```
core/
  address.py     Address grammar and same-Team resolution
  message.py     Immutable Message
  kinds.py       MessageKind: request, response, error, event
  identity.py    AgentIdentity and verification status
  profile.py     AgentProfile, Skill, Capability
  types.py       Enumerations (provider, agent type, protocol version)
  exceptions.py  Shared exception types
```

`BaseAgent` lives in `agentconnect.agent`. The team directory lives in `agentconnect.team.directory`.

## Address

`parse_address` returns a `ParsedAddress` or `invalid_address`. `resolve_address(value, team_name)` returns a canonical `name@team` string, `invalid_address`, or `address_outside_team`.

Input may contain uppercase ASCII letters. Non-ASCII input is invalid. A valid location that is not this Team is `address_outside_team`.

## Message kinds

`Message.kind` is one of `request`, `response`, `error`, or `event`. Application typing belongs in `content` or `metadata`. Control labels such as `stop` and `cooldown` are stored as `metadata["control"]`.
