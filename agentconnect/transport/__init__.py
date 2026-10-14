"""Session transports: how an Agent talks to its Team Runtime.

A Session is a set of operations (join, lease, reply, heartbeat), not a
wire format. `InProcessTransport` is used when `BaseAgent.join` receives
a started `Team`. `HttpRuntimeTransport` is used when it receives a URL.
Agent code does not change between them.

`RuntimeTransport` is the protocol a custom transport implements.
`TransportError` is a failed Runtime operation; branch on `code`.

Tickets are stored on the Team. A dropped connection does not cancel
accepted work. Rejoin with the same `instance_id` and collect with
`get_result`.
"""

from agentconnect.transport.agent_http import HttpRuntimeTransport
from agentconnect.transport.inprocess import InProcessTransport
from agentconnect.transport.runtime import RuntimeTransport, TransportError

__all__ = [
    "HttpRuntimeTransport",
    "InProcessTransport",
    "RuntimeTransport",
    "TransportError",
]
