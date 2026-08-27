"""Operational defaults for a Team Runtime."""

from __future__ import annotations

SPEC_VERSION = "1.0.0-draft"

DEFAULT_MAX_MESSAGE_BYTES = 1_048_576
DEFAULT_MAX_MAILBOX_DEPTH = 1000
DEFAULT_DELIVERY_HISTORY_LIMIT = 50

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

COLLECT_IMPLEMENTED = frozenset({"wait", "ticket"})
COLLECT_NAMED = frozenset({"wait", "ticket", "callback", "stream"})
MESSAGE_KINDS_SEND = frozenset({"request", "event"})
TICKET_TERMINAL = frozenset({"completed", "failed", "expired", "declined"})
