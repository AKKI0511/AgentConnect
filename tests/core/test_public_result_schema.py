"""Advertised success result schemas keep tagged unions intact."""

from __future__ import annotations

from agentconnect.core.base import public_json_schema, public_result_schema
from agentconnect.core.directory import GetProfilesResult
from agentconnect.core.operations import HistoryView, TellView
from agentconnect.core.team_tools import TEAM_TOOL_SPECS
from agentconnect.core.ticket import TicketView


def test_ticket_view_result_schema_is_a_tagged_union():
    schema = public_result_schema(TicketView)
    assert schema.get("type") == "object"
    assert "anyOf" in schema or "oneOf" in schema
    assert "additionalProperties" not in schema


def test_object_result_schemas_close_undeclared_properties():
    for model in (TellView, HistoryView, GetProfilesResult):
        schema = public_result_schema(model)
        assert schema.get("type") == "object"
        assert schema.get("additionalProperties") is False
        assert schema == public_json_schema(model)


def test_team_tool_specs_cover_the_six_reserved_tools():
    names = [spec.name for spec in TEAM_TOOL_SPECS]
    assert names == [
        "find",
        "ask",
        "tell",
        "get_result",
        "get_history",
        "get_profiles",
    ]
    assert "queued" in TEAM_TOOL_SPECS[2].description.lower()
    assert "parent_id" in TEAM_TOOL_SPECS[4].description
    assert "addresses" in TEAM_TOOL_SPECS[5].description.lower()
