"""Operational defaults for a Team Runtime."""

from __future__ import annotations

DEFAULT_MAX_MESSAGE_BYTES = 1_048_576
DEFAULT_MAX_MAILBOX_DEPTH = 1000
DEFAULT_DELIVERY_HISTORY_LIMIT = 50

# Seconds a collect=wait send may stay open. After this the Runtime
# returns the current Ticket (possibly still open) and the caller uses
# get_result. Proxies drop idle HTTP well before a 24h deadline.
DEFAULT_WAIT_HOLD_SECONDS = 25.0

DEFAULT_SESSION_TTL_SECONDS = 300
DEFAULT_LEASE_TTL_SECONDS = 60
DEFAULT_MAX_IN_FLIGHT = 1
DEFAULT_MAX_INSTANCES = 100

# Open Tickets are kept until at least their deadline. Terminal Tickets are
# kept this long after they close (or until the deadline, whichever is later).
DEFAULT_TERMINAL_TICKET_RETENTION_SECONDS = 24 * 60 * 60

# Thread history is trimmed to this many Messages once no open Ticket
# still references an older Message.
DEFAULT_THREAD_MESSAGE_LIMIT = 10_000

SWEEP_INTERVAL_SECONDS = 0.5

DEFAULT_JOIN_CHALLENGE_TTL_SECONDS = 60
DEFAULT_JOIN_TOKEN_TTL_SECONDS = 3600

COLLECT_IMPLEMENTED = frozenset({"wait", "ticket"})
COLLECT_NAMED = frozenset({"wait", "ticket", "callback", "stream"})
MESSAGE_KINDS_SEND = frozenset({"request", "event"})
TICKET_TERMINAL = frozenset({"completed", "failed", "expired", "declined"})

# Reserved for the loopback MCP operator Membership.
OPERATOR_NAME = "operator"
RESERVED_MCP_TOOL_NAMES = frozenset(
    {"find", "ask", "tell", "get_result", "get_history"}
)

OPERATOR_PROFILE = {
    "summary": "Person using this Team from an MCP client.",
    "skills": [
        {
            "name": "operate",
            "description": "Ask teammates to do work and collect their results.",
        }
    ],
    "tags": ["operator"],
}
