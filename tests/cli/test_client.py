"""RuntimeClient keeps finite HTTP timeouts; watch stays unbounded."""

from __future__ import annotations

from typing import Any

import httpx

from agentconnect.cli.client import DEFAULT_TIMEOUT, RuntimeClient


class _FakeResponse:
    status_code = 200
    content = b"{}"

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def json(self) -> dict[str, Any]:
        return self.payload


def test_find_and_token_use_client_timeout_not_none() -> None:
    seen: list[dict[str, Any]] = []
    client = RuntimeClient("http://127.0.0.1:9", timeout=DEFAULT_TIMEOUT)

    def fake_request(method: str, path: str, **kwargs: Any) -> _FakeResponse:
        seen.append({"method": method, "path": path, **kwargs})
        if path.endswith("/directory/find"):
            return _FakeResponse({"matches": []})
        return _FakeResponse(
            {
                "token": "join-token",
                "expires_at": "2026-08-18T15:10:00Z",
                "single_use": False,
                "name": "writer",
            }
        )

    client._client.request = fake_request  # type: ignore[method-assign]
    client.find("someone who can draft")
    client.issue_token(name="writer")
    assert len(seen) == 2
    for call in seen:
        assert "timeout" not in call


def test_ask_passes_finite_deadline_budget() -> None:
    seen: list[dict[str, Any]] = []
    client = RuntimeClient("http://127.0.0.1:9", timeout=DEFAULT_TIMEOUT)

    def fake_request(method: str, path: str, **kwargs: Any) -> _FakeResponse:
        seen.append(kwargs)
        body = kwargs["json"]
        message = {
            "id": body["id"],
            "sender": "operator@content-squad",
            "sender_did": "did:key:z6MkmEtU9Z7p7G6vbULDgMk8DXCVqW8rNyLMtd2RrAHjLD3m",
            "recipient": body["recipient"],
            "kind": "request",
            "content": body["content"],
            "created_at": "2026-08-18T15:00:00Z",
            "trace_id": "e26e64ce-f7f1-47c4-a323-e3a3867e7d28",
            "deadline": "2026-08-18T15:10:00Z",
        }
        ticket = {
            "id": body["id"],
            "requester": "operator@content-squad",
            "recipient": body["recipient"],
            "state": "open",
            "created_at": "2026-08-18T15:00:00Z",
            "updated_at": "2026-08-18T15:00:00Z",
            "deadline": "2026-08-18T15:10:00Z",
            "late_reply_count": 0,
            "trace_id": message["trace_id"],
        }
        return _FakeResponse(
            {"status": "ticketed", "message": message, "ticket": ticket}
        )

    client._client.request = fake_request  # type: ignore[method-assign]
    client.ask("writer@content-squad", "hello", deadline_seconds=60)
    assert seen[0]["timeout"] == 70.0
    client.ask("writer@content-squad", "hello")
    assert seen[1]["timeout"] == DEFAULT_TIMEOUT


def test_watch_keeps_explicit_unbounded_stream() -> None:
    seen: list[dict[str, Any]] = []
    client = RuntimeClient("http://127.0.0.1:9", timeout=DEFAULT_TIMEOUT)

    class _Stream:
        def __enter__(self):
            raise httpx.ConnectError("skip")

        def __exit__(self, *args: object) -> None:
            return None

    def fake_stream(*args: Any, **kwargs: Any) -> _Stream:
        seen.append(kwargs)
        return _Stream()

    client._client.stream = fake_stream  # type: ignore[method-assign]
    try:
        list(client.watch())
    except Exception:
        pass
    assert seen
    assert seen[0]["timeout"] is None
