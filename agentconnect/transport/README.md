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
