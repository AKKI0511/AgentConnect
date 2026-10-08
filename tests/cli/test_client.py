"""RuntimeClient keeps finite HTTP timeouts; watch stays unbounded."""

from __future__ import annotations

from typing import Any

import httpx

from agentconnect.cli.client import DEFAULT_TIMEOUT, RuntimeClient


class _FakeResponse:
    status_code = 200
    content = b"{}"

    def json(self) -> dict[str, Any]:
        return {}


def test_find_and_token_use_client_timeout_not_none() -> None:
    seen: list[dict[str, Any]] = []
    client = RuntimeClient("http://127.0.0.1:9", timeout=DEFAULT_TIMEOUT)

    def fake_request(method: str, path: str, **kwargs: Any) -> _FakeResponse:
        seen.append({"method": method, "path": path, **kwargs})
        return _FakeResponse()

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
        return _FakeResponse()

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
