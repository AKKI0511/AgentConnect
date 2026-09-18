"""Accept one request on Redis, then exit without Runtime shutdown."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentconnect.team import Team
from agentconnect.team.store.redis import RedisStore

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _did(label: str) -> str:
    mapped = "".join(_B58[ord(ch) % len(_B58)] for ch in label)
    body = (mapped + ("1" * 48))[:48]
    return "did:key:z" + body


def _profile() -> dict[str, object]:
    return {
        "summary": "Writes short drafts from notes.",
        "skills": [
            {
                "name": "drafting",
                "description": "Turn notes into a two-paragraph draft.",
            }
        ],
    }


def _deadline(seconds: float) -> str:
    instant = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return instant.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def _join(team: Team, name: str) -> dict:
    return await team.join(name=name, agent_did=_did(name), profile=_profile())


async def _run(url: str, prefix: str, out_path: Path) -> None:
    store = RedisStore(url, prefix=prefix)
    await store.open()
    team = Team(
        "content-squad",
        store=store,
        embeddings="none",
        session_ttl_seconds=120,
        lease_ttl_seconds=30,
        sweep_interval_seconds=1.0,
    )
    await team.start()
    await _join(team, "writer")
    researcher = await _join(team, "researcher")
    sent = await team.send(
        researcher["session_token"],
        {
            "id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            "recipient": "writer",
            "kind": "request",
            "content": "persist-across-kill",
            "collect": "ticket",
            "deadline": _deadline(120),
        },
    )
    out_path.write_text(
        json.dumps({"ticket_id": sent["message"]["id"], "prefix": prefix}),
        encoding="utf-8",
    )
    os._exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    asyncio.run(_run(args.url, args.prefix, Path(args.out)))


if __name__ == "__main__":
    main()
