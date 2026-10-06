"""Shared names, descriptions, and schemas for MCP and Session Team tools.

``agent`` and ``mcp`` both import this module. It has no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentconnect.core.directory import (
    FindRequest,
    FindResult,
    GetProfilesRequest,
    GetProfilesResult,
)
from agentconnect.core.operations import (
    AskToolRequest,
    GetHistoryRequest,
    GetResultRequest,
    HistoryView,
    TellToolRequest,
    TellView,
)
from agentconnect.core.ticket import TicketView

FIND_DESCRIPTION = (
    "Find teammates by describing the work you need. Returns ranked "
    "candidate cards (address, summary, skill names, tags), not a "
    "guarantee of suitability. Call get_profiles when cards overlap. "
    "Reuse what you already read. You may conclude nobody fits. Omit "
    "limit to receive every other member, at most 100."
)
ASK_DESCRIPTION = (
    "Send work that needs a reply. Returns the saved request result. If "
    "state is open, keep ticket_id and call get_result; do not send another "
    "ask to collect. collect=wait bounds this call only and may still "
    "return open. deadline_seconds cuts off work, not the wait. Omit "
    "thread_id to start a conversation. Continue a returned thread_id only "
    "with the same recipient. Prefer this over tell when you need an "
    "answer, including acknowledgement that a notice was processed."
)
TELL_DESCRIPTION = (
    "Send work that does not need a reply. Returns a notice "
    "acknowledgement. status accepted means the Runtime queued the event, "
    "not that the recipient finished processing. A later ask may miss this "
    "notice if it runs before processing. If later work depends on the "
    "notice, include the fact in that ask, or ask for an acknowledgement. "
    "Does not create a Ticket. Omit thread_id for an unthreaded notice. "
    "Continue a returned thread_id only with a current participant."
)
GET_RESULT_DESCRIPTION = (
    "Return the current saved request result. Repeatable. Does not consume "
    "the result. Pass ticket_id from ask. Branch on state. Open means keep "
    "waiting with this ticket_id. A completed Ticket stays completed after "
    "its original deadline while retained."
)
GET_HISTORY_DESCRIPTION = (
    "Return one page of retained conversation history. The newest page is "
    "first; turns inside a page are oldest-to-newest. Response and error "
    "turns include parent_id, the request Message id they answer (same as "
    "that ask's ticket_id). When has_more is true, pass next_before as "
    "before. Stop when has_more is false."
)
GET_PROFILES_DESCRIPTION = (
    "Return selected teammates' Profiles by Address. Pass one or more "
    "addresses, at most 20. Duplicate addresses are read once. Missing "
    "members appear as per-item errors; other Profiles still return. "
    "Prefer this when find cards overlap."
)
TEAM_MCP_INSTRUCTIONS = (
    "You are talking to an AgentConnect Team. Use find to discover teammates "
    "by describing the work. Use get_profiles to read one or more teammates "
    "in full. Use ask to send work that needs a reply. Use tell when no "
    "reply is needed; accepted means queued, not processed. Use get_result "
    "to collect the saved request result. Use get_history to page a "
    "conversation. Addresses look like writer or writer@team-name. Keep "
    "ticket_id and thread_id from results. ask wait may return an open "
    "saved result; call get_result for the rest. Pass idempotency_key when "
    "you mean to retry the same ask."
)


@dataclass(frozen=True)
class TeamToolSpec:
    """One reserved Team tool's advertised contract."""

    name: str
    title: str
    description: str
    input_model: type[Any]
    output_model: Any


TEAM_TOOL_SPECS: tuple[TeamToolSpec, ...] = (
    TeamToolSpec(
        name="find",
        title="Find teammates",
        description=FIND_DESCRIPTION,
        input_model=FindRequest,
        output_model=FindResult,
    ),
    TeamToolSpec(
        name="ask",
        title="Ask a teammate",
        description=ASK_DESCRIPTION,
        input_model=AskToolRequest,
        output_model=TicketView,
    ),
    TeamToolSpec(
        name="tell",
        title="Tell a teammate",
        description=TELL_DESCRIPTION,
        input_model=TellToolRequest,
        output_model=TellView,
    ),
    TeamToolSpec(
        name="get_result",
        title="Collect a result",
        description=GET_RESULT_DESCRIPTION,
        input_model=GetResultRequest,
        output_model=TicketView,
    ),
    TeamToolSpec(
        name="get_history",
        title="Reload a conversation",
        description=GET_HISTORY_DESCRIPTION,
        input_model=GetHistoryRequest,
        output_model=HistoryView,
    ),
    TeamToolSpec(
        name="get_profiles",
        title="Read profiles",
        description=GET_PROFILES_DESCRIPTION,
        input_model=GetProfilesRequest,
        output_model=GetProfilesResult,
    ),
)

TEAM_TOOL_BY_NAME = {spec.name: spec for spec in TEAM_TOOL_SPECS}
RESERVED_TEAM_TOOL_NAMES = frozenset(TEAM_TOOL_BY_NAME)
