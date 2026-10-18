"""Connect an Agent to its Team in process or over HTTP.

`BaseAgent.join` selects the transport from a started Team or a Runtime URL.
Most callers need no transport construction. A Session is an authenticated
connection to the Team; its Membership and accepted work can outlive it.

Transport authors implement `RuntimeTransport`. Losing a connection does not
cancel accepted work. To collect retained Tickets after Session replacement,
rejoin the same Membership with its original identity and valid admission
credentials; reuse `instance_id` when replacing the same running Instance.
Collection remains subject to retention and access rights.
"""

from agentconnect.transport.agent_http import HttpRuntimeTransport
from agentconnect.transport.inprocess import InProcessTransport
from agentconnect.transport.runtime import (
    RuntimeOperations,
    RuntimeTransport,
    TransportError,
)

__all__ = [
    "HttpRuntimeTransport",
    "InProcessTransport",
    "RuntimeOperations",
    "RuntimeTransport",
    "TransportError",
]
