"""Operational defaults for a Team Runtime."""

from __future__ import annotations

DEFAULT_MAX_MESSAGE_BYTES = 1_048_576
DEFAULT_MAX_MAILBOX_DEPTH = 1000
DEFAULT_DELIVERY_HISTORY_LIMIT = 50

# Seconds a collect=wait send may stay open. After this the Runtime
# returns the current Ticket (possibly still open) and the caller uses
# get_result. Proxies drop idle HTTP well before a 24h deadline.
DEFAULT_WAIT_HOLD_SECONDS = 25.0
DEFAULT_MAX_HELD_WAITS = 16

# Finite work cutoff stamped on a new request whose send omitted
# deadline and that has no request parent to inherit from.
DEFAULT_WORK_LIFETIME_SECONDS = 3600.0

# Farthest a new request deadline may be from acceptance.
DEFAULT_MAX_DEADLINE_SECONDS = 24 * 60 * 60

# Open Tickets one Membership may hold as requester.
DEFAULT_MAX_OPEN_TICKETS = 1000

# UTF-8 JSON bytes of retained Message bodies.
DEFAULT_MAX_RETAINED_BYTES = 64 * 1024 * 1024

# Unused join challenges kept at once.
DEFAULT_MAX_JOIN_CHALLENGES = 128

# Due items processed in one expiry sweep.
SWEEP_BATCH = 256

DEFAULT_SESSION_TTL_SECONDS = 300
DEFAULT_LEASE_TTL_SECONDS = 60
DEFAULT_MAX_IN_FLIGHT = 1
DEFAULT_MAX_INSTANCES = 100

# Open Tickets are kept until at least their deadline. Terminal Tickets,
# request replay records, and event send replays are kept this long after
# the obligation ends (or until the Ticket deadline, whichever is later).
DEFAULT_REPLAY_HORIZON_SECONDS = 24 * 60 * 60
DEFAULT_TERMINAL_TICKET_RETENTION_SECONDS = DEFAULT_REPLAY_HORIZON_SECONDS

# Thread history is trimmed to this many Messages once no live Delivery
# or Ticket window still references an older Message.
DEFAULT_THREAD_MESSAGE_LIMIT = 10_000

SWEEP_INTERVAL_SECONDS = 0.5

DEFAULT_JOIN_CHALLENGE_TTL_SECONDS = 60
DEFAULT_JOIN_TOKEN_TTL_SECONDS = 3600

COLLECT_MODES = frozenset({"wait", "ticket"})
MESSAGE_KINDS_SEND = frozenset({"request", "event"})
TICKET_TERMINAL = frozenset({"completed", "failed", "expired", "declined"})

# Reserved for the loopback operator Membership (CLI and MCP).
OPERATOR_NAME = "operator"
RESERVED_MCP_TOOL_NAMES = frozenset(
    {"find", "ask", "tell", "get_result", "get_history"}
)
