"""Message parse rules for request vs event."""

from __future__ import annotations

import pytest

from agentconnect.core.message import RequestMessage, is_reply_expected, parse_message
from agentconnect.core.operations import parse_send_request

_UUID = "00000000-0000-4000-8000-000000000001"
_TIMESTAMP = "2026-08-18T15:00:00Z"


def test_request_without_deadline_is_invalid():
    with pytest.raises(ValueError):
        parse_message(
            {
                "id": _UUID,
                "sender": "researcher@content-squad",
                "recipient": "writer@content-squad",
                "kind": "request",
                "content": "work",
                "created_at": _TIMESTAMP,
                "trace_id": _UUID,
            }
        )


def test_request_is_reply_expected():
    message = parse_message(
        {
            "id": _UUID,
            "sender": "researcher@content-squad",
            "recipient": "writer@content-squad",
            "kind": "request",
            "content": "work",
            "created_at": _TIMESTAMP,
            "trace_id": _UUID,
            "deadline": _TIMESTAMP,
        }
    )
    assert isinstance(message, RequestMessage)
    assert is_reply_expected(message)


def test_event_is_not_reply_expected():
    message = parse_message(
        {
            "id": _UUID,
            "sender": "researcher@content-squad",
            "recipient": "writer@content-squad",
            "kind": "event",
            "content": "note",
            "created_at": _TIMESTAMP,
            "trace_id": _UUID,
        }
    )
    assert not is_reply_expected(message)
    assert "seq" not in message


def test_send_request_requires_collect_and_deadline():
    with pytest.raises(ValueError):
        parse_send_request(
            {
                "id": _UUID,
                "recipient": "writer",
                "kind": "request",
                "content": "work",
            }
        )


def test_threaded_message_keeps_seq():
    message = parse_message(
        {
            "id": _UUID,
            "sender": "researcher@content-squad",
            "recipient": "writer@content-squad",
            "kind": "event",
            "content": "note",
            "created_at": _TIMESTAMP,
            "trace_id": _UUID,
            "thread_id": _UUID,
            "seq": 1,
        }
    )
    assert message.seq == 1
    assert message["seq"] == 1
