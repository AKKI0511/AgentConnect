"""Public projection omits Runtime Membership ids without rewriting Agent JSON."""

from agentconnect.team.projection import (
    public_event,
    public_history_result,
    public_lease_result,
    public_message,
    public_send_result,
    public_ticket,
    public_ticket_result,
    public_trace_result,
)

_USER_KEYS = {
    "sender_membership_id": "keep-sender",
    "recipient_membership_id": "keep-recipient",
    "requester_membership_id": "keep-requester",
    "actor_membership_id": "keep-actor",
}


def test_public_message_keeps_matching_keys_inside_content_and_metadata():
    message = {
        "id": "11111111-1111-4111-8111-111111111111",
        "sender": "researcher@content-squad",
        "sender_did": "did:key:z6MkmEtU9Z7p7G6vbULDgMk8DXCVqW8rNyLMtd2RrAHjLD3m",
        "sender_membership_id": "mid-1",
        "recipient": "writer@content-squad",
        "recipient_membership_id": "mid-2",
        "kind": "event",
        "content": dict(_USER_KEYS),
        "metadata": {"nested": dict(_USER_KEYS)},
    }
    public = public_message(message)
    assert "sender_membership_id" not in public
    assert "recipient_membership_id" not in public
    assert public["content"] == _USER_KEYS
    assert public["metadata"]["nested"] == _USER_KEYS
    assert public["sender_did"] == message["sender_did"]


def test_public_ticket_projects_nested_response_and_keeps_error_payload():
    ticket = {
        "id": "11111111-1111-4111-8111-111111111111",
        "requester_membership_id": "mid-1",
        "recipient_membership_id": "mid-2",
        "state": "completed",
        "response": {
            "sender_membership_id": "mid-2",
            "recipient_membership_id": "mid-1",
            "kind": "response",
            "content": dict(_USER_KEYS),
            "error": {"nested": dict(_USER_KEYS)},
        },
    }
    public = public_ticket(ticket)
    assert "requester_membership_id" not in public
    assert "recipient_membership_id" not in public
    assert "sender_membership_id" not in public["response"]
    assert public["response"]["content"] == _USER_KEYS
    assert public["response"]["error"]["nested"] == _USER_KEYS


def test_envelope_helpers_project_known_record_boundaries():
    message = {
        "sender_membership_id": "mid-1",
        "content": dict(_USER_KEYS),
    }
    ticket = {"requester_membership_id": "mid-1", "state": "open"}
    event = {"actor_membership_id": "mid-1", "type": "accepted"}
    send = public_send_result(
        {"status": "accepted", "message": message, "ticket": ticket}
    )
    assert "sender_membership_id" not in send["message"]
    assert send["message"]["content"] == _USER_KEYS
    assert "requester_membership_id" not in send["ticket"]
    lease = public_lease_result(
        {
            "deliveries": [
                {
                    "message": message,
                    "history": [message],
                }
            ]
        }
    )
    assert "sender_membership_id" not in lease["deliveries"][0]["message"]
    assert lease["deliveries"][0]["history"][0]["content"] == _USER_KEYS
    assert (
        "requester_membership_id"
        not in public_ticket_result({"ticket": ticket})["ticket"]
    )
    history = public_history_result({"messages": [message], "has_more": False})
    assert history["messages"][0]["content"] == _USER_KEYS
    trace = public_trace_result({"trace_id": "t", "events": [event]})
    assert "actor_membership_id" not in trace["events"][0]
    assert public_event(event)["type"] == "accepted"
