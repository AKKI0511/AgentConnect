# Security

The Runtime is the trust boundary for a Team. It authenticates a Client once at `join`, authorizes every later operation through the issued Session, and stamps the verified sender on accepted Messages.

Agent code is untrusted from the Runtime's point of view. A Message payload cannot grant authority, choose its verified sender, or alter a Runtime-owned field.

## Agent identity

Every Agent has an Agent DID backed by its own Ed25519 key pair. The current draft accepts `did:key` identities whose key material resolves to an Ed25519 public key.

The private key stays with the Client. The Runtime stores the Agent DID and the public information needed to verify join proofs. It MUST NOT require or accept an Agent private key.

The Agent DID identifies the logical Agent across Session replacement and across concurrent Instances. The Agent name identifies its Membership within one Team. Neither value substitutes for the other.

## Embedded join

An embedded Runtime may accept `join` without a join token or identity proof only when it has no listener reachable beyond the current process or loopback interface.

Opening an unauthenticated embedded Runtime on a non-loopback interface is forbidden. A configuration flag alone does not make that deployment safe.

The Runtime still records the submitted Agent DID and stamps it on Messages. In this mode the containing application is the trust source for that DID.

## Network join

A Runtime reachable through a non-loopback network requires two independent credentials:

1. `join_token` proves that the Team allowed the join.
2. `identity_proof` proves control of the submitted Agent DID.

Missing or invalid credentials fail with `unauthorized`. A credential valid for another Team, Agent DID, Agent name, or expired challenge fails with `unauthorized` without revealing which check failed.

### Join token

A join token is an opaque value issued by the Team. Its internal encoding is not public because only the issuing Runtime verifies it.

Every token MUST be:

- scoped to one Team
- expiring
- revocable
- single-use or safely replayable for reconnecting the same Membership

A token MAY also bind an Agent DID, Agent name, or both. If a bound value differs from `JoinRequest`, the join fails.

The operator issues and revokes tokens through `issue_join_token` and `revoke_join_token` on HTTP and MCP. The hosting process may call the same issuance on the Runtime object without a Session.

Revoking a token MUST prevent another join with it. Any active Session created from that token MUST become unauthorized no later than the Runtime's next Session-authentication check.

### Join challenge

Before joining, the Client fetches a short-lived `JoinChallenge`:

```json
{
  "nonce": "Up7Zu1q56kN6VfGqUZqffA",
  "audience": "agentconnect:content-squad",
  "expires_at": "2026-08-18T15:01:00Z"
}
```

The nonce MUST contain at least 128 bits of cryptographically random data encoded for JSON. A nonce is accepted once. Reuse fails even before `expires_at`.

The `audience` prefix `agentconnect:` is the only brand-coupled token in the security surface. It is Runtime machinery, not part of any Address or Message.

### Identity proof

`identity_proof` is a compact JWT signed by the Agent's Ed25519 key. Its protected header contains `alg=EdDSA` and `typ=JWT`.

The payload contains exactly these required claims:

```json
{
  "iss": "did:key:z6MkmEtU9Z7p7G6vbULDgMk8DXCVqW8rNyLMtd2RrAHjLD3m",
  "aud": "agentconnect:content-squad",
  "nonce": "Up7Zu1q56kN6VfGqUZqffA",
  "iat": 1787065200,
  "exp": 1787065260
}
```

| Claim | Requirement |
| --- | --- |
| `iss` | equals `JoinRequest.agent_did` |
| `aud` | equals the challenge `audience` |
| `nonce` | equals the unused challenge nonce |
| `iat` | no more than 60 seconds in the future |
| `exp` | later than `iat` and no later than the challenge expiry |

The Runtime resolves `iss` as a `did:key`, verifies the Ed25519 signature, validates every claim, then consumes the nonce atomically with successful join authentication.

## Session

A successful join returns an opaque `session_token`, its `session_expires_at`, and the `instance_id` it is bound to.

The Session is bound to one Instance of one Membership. It authorizes only that Membership's member operations:

- `disconnect`
- `heartbeat`
- `send`
- `lease`
- `complete`
- `reply`
- `get_result` for Tickets created by that Membership
- `get_history` for Threads the Membership participates in
- `find`
- `get_profile`
- `get_trace` for a Trace the Membership appears in

The reserved `operator` is a principal Membership. It may also call `status`, `issue_join_token`, `revoke_join_token`, and `get_trace` for any Trace. A person talking to a loopback Runtime uses this Membership. See [bindings/http.md](bindings/http.md) and [bindings/mcp.md](bindings/mcp.md).

Over HTTP and MCP, that operator authority is a property of the Session. The hosting process may call `issue_join_token` and `revoke_join_token` on the Runtime object without a Session; the process is the trust boundary.

A loopback listener with no `Authorization` header is one shared local identity. Every local client that omits the header is the same `operator` Membership, so they share its Tickets, Trace access, and operator operations. That is acceptable because the machine is the trust boundary.

The Runtime authenticates every operation. A Session cannot choose another sender, lease another Membership's Mailbox, complete or reply to a lease held by another Membership, read another Membership's Ticket, or read Thread history for a participant set it is not in.

Session tokens are bearer credentials. Clients MUST keep them out of Message content, metadata, logs, and exception text.

A Membership may hold several concurrent Sessions, one per Instance. A new join for an existing `instance_id` invalidates that Instance's prior Session; other Instances are unaffected. `disconnect`, expiry, and join-token revocation invalidate the calling Session.

### Immediate revocation

Removing a Membership, or revoking its join token, invalidates every Session of that Membership. Invalidation MUST take effect promptly, not only at the next discrete operation:

- a `send` waiting for a Ticket MUST stop and return `unauthorized`
- an open event stream MUST close
- a held lease MUST stop being completable

This is the kill switch: cutting a compromised member off from sending and receiving is the same mechanism as revoking its Sessions.

## Sender attribution

`SendRequest` has no sender field. The Runtime derives the sender from the authenticated Session and stores the canonical Address in the accepted Message.

`reply` follows the same rule. The Runtime derives the response sender from the Membership that owns the lease and the response recipient from the request Message.

Inside a Team, Messages are not signed individually. Attribution comes from Session authentication plus Runtime stamping. A Client-supplied `sender`, recipient override on reply, `created_at`, `trace_id`, `attempt`, lease fact, or Instance stamp MUST be rejected as an unknown or invalid field.

## Transport security

A non-loopback HTTP Runtime MUST use HTTPS. Loopback development endpoints MAY use HTTP.

Bearer credentials MUST appear only in the HTTP `Authorization` header, except `join_token` and `identity_proof`, which are fields of `JoinRequest`.

The Runtime SHOULD avoid distinguishing authentication failures in public error messages. Detailed reasons belong in protected Runtime logs.

## Security vectors

| Situation | Required observation |
| --- | --- |
| valid token, invalid DID signature | `unauthorized`; no Membership or Session created |
| valid proof, token bound to another DID | `unauthorized`; no Membership or Session created |
| reused challenge nonce | `unauthorized` |
| expired identity proof | `unauthorized` |
| new join for the same Instance | that Instance's old Session becomes unauthorized |
| new join for a new Instance | prior Instances keep their Sessions |
| Membership removed while a `send` waits | the waiting `send` returns `unauthorized` |
| Client includes `sender` in send input | `invalid_request` |
| one member reads another member's Ticket | `not_found` |
| non-participant calls `get_history` | `not_found` |
| Session expires while holding leases | leases are released; Membership and Ticket state remain |
| member Session calls `status` | `forbidden` |
| member Session calls `issue_join_token` | `forbidden` |
| loopback HTTP with no Authorization | operations run as `operator` |
| two loopback clients with no Authorization | the same `operator` Membership; they share Tickets, Trace, and operator operations |
| `send` to `operator` | `not_found` |
