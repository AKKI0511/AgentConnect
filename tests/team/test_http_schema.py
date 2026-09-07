"""HTTP bodies reject extra fields and coercible wrong types."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from tests.core.test_schema_mutations import _generated_cases
from tests.team.conftest import join_member

pytestmark = pytest.mark.asyncio

PREFIX = "/agentconnect/v1"
_CORPUS = Path(__file__).resolve().parents[2] / "spec" / "schema" / "rejection.json"
_HTTP_TYPES = {
    "FindRequest": ("POST", PREFIX + "/directory/find"),
    "LeaseRequest": ("POST", PREFIX + "/mailbox/lease"),
    "CompleteRequest": ("POST", PREFIX + "/deliveries/complete"),
    "RequestSendRequest": ("POST", PREFIX + "/messages"),
    "EventSendRequest": ("POST", PREFIX + "/messages"),
    "JoinRequest": ("POST", PREFIX + "/join"),
}


def _vectors() -> list[dict]:
    payload = json.loads(_CORPUS.read_text(encoding="utf-8"))
    return [item for item in payload["vectors"] if item["type"] in _HTTP_TYPES]


async def test_http_schema_vectors_match_corpus(team):
    writer = await join_member(team, "writer")
    origin = await team.serve()
    writer_headers = {"Authorization": f"Bearer {writer['session_token']}"}
    async with httpx.AsyncClient() as client:
        for vector in _vectors():
            method, path = _HTTP_TYPES[vector["type"]]
            headers = {}
            if vector["type"] in {
                "LeaseRequest",
                "CompleteRequest",
                "RequestSendRequest",
                "EventSendRequest",
            }:
                headers = writer_headers
            response = await client.request(
                method, origin + path, json=vector["instance"], headers=headers
            )
            if vector["accept"]:
                assert response.status_code == 200, vector["id"]
                body = response.json()
                if vector["type"] == "FindRequest":
                    assert "matches" in body
                    assert any(
                        str(item.get("address", "")).startswith("writer@")
                        for item in body["matches"]
                    )
                elif vector["type"] == "LeaseRequest":
                    assert isinstance(body.get("deliveries"), list)
                elif vector["type"] == "EventSendRequest":
                    assert body.get("status") == "accepted"
                    assert body.get("message", {}).get("kind") == "event"
            else:
                assert response.status_code == 400, vector["id"]
                assert response.json()["code"] in {
                    "invalid_request",
                    "unsupported_version",
                }


async def test_http_generated_mutations_are_invalid_request(team):
    writer = await join_member(team, "writer")
    origin = await team.serve()
    writer_headers = {"Authorization": f"Bearer {writer['session_token']}"}
    async with httpx.AsyncClient() as client:
        for case_id, name, instance in _generated_cases():
            if name not in _HTTP_TYPES:
                continue
            method, path = _HTTP_TYPES[name]
            headers = {}
            if name in {
                "LeaseRequest",
                "CompleteRequest",
                "RequestSendRequest",
                "EventSendRequest",
            }:
                headers = writer_headers
            response = await client.request(
                method, origin + path, json=instance, headers=headers
            )
            assert response.status_code == 400, case_id
            assert response.json()["code"] in {
                "invalid_request",
                "unsupported_version",
            }


async def test_forwarded_client_header_is_not_operator(team):
    origin = await team.serve()
    async with httpx.AsyncClient() as client:
        status = await client.get(
            origin + PREFIX + "/status",
            headers={"X-Forwarded-For": "203.0.113.10"},
        )
        assert status.status_code == 401
        assert status.json()["code"] == "unauthorized"

        empty_forwarded = await client.get(
            origin + PREFIX + "/status",
            headers=[("x-forwarded-for", "")],
        )
        assert empty_forwarded.status_code == 401

        forwarded_prefix = await client.get(
            origin + PREFIX + "/status",
            headers=[("x-forwarded-host", "")],
        )
        assert forwarded_prefix.status_code == 401

        forwarded = await client.post(
            origin + PREFIX + "/directory/find",
            json={"query": "someone who can draft a summary"},
            headers={"Forwarded": "for=203.0.113.10"},
        )
        assert forwarded.status_code == 401


async def test_empty_or_malformed_authorization_is_not_operator(team):
    origin = await team.serve()
    async with httpx.AsyncClient() as client:
        empty = await client.get(
            origin + PREFIX + "/status",
            headers=[("authorization", "")],
        )
        assert empty.status_code == 401

        bearer_only = await client.get(
            origin + PREFIX + "/status",
            headers=[("authorization", "Bearer")],
        )
        assert bearer_only.status_code == 401

        basic = await client.get(
            origin + PREFIX + "/status",
            headers=[("authorization", "Basic abc")],
        )
        assert basic.status_code == 401
