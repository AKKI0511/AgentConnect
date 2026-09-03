"""Thread history orders by seq, not by created_at or Message id."""

from __future__ import annotations

from agentconnect.team.threads import history_window, page_history, participant_set

_TS = "2026-08-18T15:00:00Z"
_FIRST_ID = "ffffffff-ffff-4fff-bfff-ffffffffffff"
_SECOND_ID = "00000000-0000-4000-8000-000000000001"


def _msg(message_id: str, seq: int, content: str) -> dict:
    return {
        "id": message_id,
        "seq": seq,
        "created_at": _TS,
        "content": content,
        "kind": "event",
    }


def test_page_history_orders_by_seq_when_created_at_and_id_would_invert():
    messages = [
        _msg(_FIRST_ID, 1, "first"),
        _msg(_SECOND_ID, 2, "second"),
    ]
    page, has_more = page_history(messages, before=None, limit=10)
    assert [msg["content"] for msg in page] == ["first", "second"]
    assert has_more is False


def test_before_cursor_uses_seq_not_id_order():
    messages = [
        _msg(_FIRST_ID, 1, "first"),
        _msg(_SECOND_ID, 2, "second"),
    ]
    page, has_more = page_history(messages, before=_SECOND_ID, limit=10)
    assert [msg["content"] for msg in page] == ["first"]
    assert has_more is False


def test_history_window_excludes_later_seq():
    delivered = _msg(_FIRST_ID, 1, "first")
    later = _msg(_SECOND_ID, 2, "second")
    window, complete = history_window(
        [delivered, later],
        delivered_id=_FIRST_ID,
        limit=10,
        max_bytes=10_000,
    )
    assert window == []
    assert complete is True


def test_participant_set_holds_three_memberships():
    thread = {
        "participants": [
            "editor@content-squad",
            "researcher@content-squad",
            "writer@content-squad",
        ]
    }
    members = participant_set(thread)
    assert len(members) == 3
    assert "editor@content-squad" in members
