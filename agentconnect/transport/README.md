# Session transports

`BaseAgent.join` selects in-process connectivity for a started Team and HTTP
connectivity for a Runtime URL. A Session is an authenticated connection; its
Membership and accepted work can outlive it. Ordinary agent code need not build
a transport.

Advanced clients and transport authors use `RuntimeTransport`. Preserve public
request and result shapes, Session authority, Runtime error codes and caller
cancellation. An ended wait or unavailable connection does not cancel accepted
work or prove rejection. Collect retained work under its owning Membership;
reconnecting requires the original Agent identity and valid admission credentials.
Reusing `instance_id` replaces the old Session for that running Instance.

InProcessTransport uses an existing Team owned by the application. Closing it
does not stop the Team. HttpRuntimeTransport owns an HTTP client: disconnect the
Session and close the client separately. Ordinary HTTP requests have finite
timeouts; sends cover the negotiated wait hold and retry once on timeout with
the same body. SSE supplies optional work hints and does not reconnect itself.

See the [transport reference](../../docs-v2/api/transport-runtime.mdx) and
[HTTP binding](../../spec/bindings/http.md).

## Gateway adapter notes

The following describes the separate gateway adapter, not the Agent Session
transport. Its existing contract is retained for gateway consumers.

### Transport SPI

The transport Service Provider Interface (SPI) lets you add new protocols without changing the hub or agents.

## Purpose

- Decouple protocol mechanics (HTTP, WS, broker, etc.) from application logic
- Keep addressing in `TransportTarget` and hints in `RouteContext`
- Keep collaboration envelopes on `CollaborationMessage` via `to_wire_dict`/`from_wire_dict`. The Team Runtime Message lives in `agentconnect.core.message`.

## SPI contract

- `send(message, target, route) -> (ok: bool, immediate_response?: Message, request_id?: str)`
  - ok=False when the remote did not accept the request (e.g., non-retryable 4xx or tripped circuit)
  - immediate_response is present on synchronous completion (e.g., HTTP 200 with `status=completed`)
  - request_id used for deferred polling when accepted/pending
- `check(request_id, target, route) -> (status: 'completed'|'pending'|'not_found', response?: Message)`
  - status mapping: 200(completed/pending) -> same; 404/410 -> not_found; other 4xx -> pending; 5xx/transient -> pending and trip breaker
- Idempotency by `request_id` (client sets header when available)
- Resilience: retries with backoff+jitter, respect `Retry-After`, simple circuit breaker and down cache

## Addressing vs hints

- `TransportTarget` is the source of truth for addressing (`url` + `inbox_path`)
- `RouteContext` carries protocol/transport hints (e.g., `protocol_hint='agentconnect.http.v1'`, `transport_hint='http'`); must not contradict target
- `Message.metadata` is application-only; allowed reserved keys only

## HTTP adapter behavior

- Endpoints:
  - POST `{target.url}{inbox_path}` -> `{status, request_id?, response?}`
  - GET `{target.url}{inbox_path}/{request_id}` -> `{status, response?}`

- Status semantics:
  - POST:
    - 200 with `status=completed` and `response` → completed (immediate response returned)
    - 201/202 with `status=accepted|pending` (or missing/unparsable body) → accepted/pending; returns `request_id` when provided
    - Non-retryable 4xx → not accepted (no circuit trip)
    - 5xx/408/425/429 → transient failure; transport trips circuit and briefly marks down target
  - GET (polling):
    - 200 with `status=completed` and `response` → completed
    - 200 with `status=accepted|pending` (or missing/unparsable body) → pending
    - 404/410 → not_found
    - Other 4xx → pending
    - 5xx/timeout → pending; transport briefly marks down target

- Request/response details:
  - Payload compatibility (server-side): The inbox accepts either a raw `Message` wire dict
    or a wrapped payload `{ "envelope": <Message wire dict> }` for backward/forward compatibility.
  - Idempotency header: `X-Idempotency-Key` set from `metadata.request_id` when present; falls back to `metadata.response_to` for responses

- Operational:
  - Pooled clients: one `httpx.AsyncClient` per base URL; closed on hub shutdown
  - Timeouts/retries/backoff/jitter: from `config.models.CommunicationSettings.http_defaults`
  - Circuit breaker: opens on repeated failures; short down cache to avoid hot spinning
  - Metrics: basic counters/histograms (no-op if meter not configured)

Compatibility note:
- The inbox accepts both a raw `Message` wire dict and a wrapped payload `{ "envelope": <Message wire dict> }`. The HTTP adapter posts the wrapped `envelope` by default.
- Route context and any remote alias are attached only when outbound POST is accepted (ok=True).

## Extensibility

To add a new transport:

1. Implement the SPI with the same semantics (`send`, `check`).
2. Respect addressing and hints separation (`TransportTarget`, `RouteContext`).
3. Provide robust retry/backoff and a minimal circuit breaker.
4. Keep wire payloads via `CollaborationMessage.to_wire_dict()`/`from_wire_dict()` only.
