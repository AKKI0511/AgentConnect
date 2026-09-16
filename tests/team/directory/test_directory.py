"""Directory ranking, default result size, and embedding backends."""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
import warnings
from typing import Sequence

import pytest
from pydantic import ValidationError
from tests.team.conftest import join_member, make_did, profile

from agentconnect.core.directory import FindResult
from agentconnect.team import Team, TeamError
from agentconnect.team.directory import HashedEmbedder, profile_text, resolve_embedder
from agentconnect.team.directory.directory import Directory, profile_windows
from agentconnect.team.directory.embedder import (
    AutoEmbedder,
    CallableEmbedder,
    FastEmbedEmbedder,
    LiteLLMEmbedder,
    OpenAIEmbedder,
    as_unit_vector,
    cosine,
    _fastembed_tokenizer,
    _select_auto_backend,
)
from agentconnect.team.directory.tokens import (
    encode_complete,
    hosted_token_count,
    local_content_tokens,
    token_windows,
)
from agentconnect.team.store.memory import MemoryStore


def _legal():
    return profile(
        summary="Reviews contracts for risk and missing terms.",
        skill="contract_review",
        description="Read a contract and list risks and missing clauses.",
        tags=["legal", "contracts"],
    )


def _writer():
    return profile(
        summary="Writes short drafts from notes.",
        skill="drafting",
        description="Turn research notes into a two-paragraph draft.",
        tags=["writing"],
    )


@pytest.mark.asyncio
async def test_find_ranks_contract_reviewer_first(team: Team):
    await join_member(team, "writer", profile=_writer())
    await join_member(team, "reviewer", profile=_legal())
    caller = await join_member(team, "researcher")
    found = await team.find(
        caller["session_token"], "someone who can verify a contract"
    )
    addresses = [match["address"] for match in found["matches"]]
    assert addresses[0] == "reviewer@content-squad"
    assert "researcher@content-squad" not in addresses
    assert "writer@content-squad" in addresses
    assert "ranking" not in found


@pytest.mark.asyncio
async def test_find_omitted_limit_returns_every_other_member():
    runtime = Team("content-squad", embeddings="none")
    await runtime.start()
    try:
        for index in range(15):
            name = f"member{index:02d}"
            await join_member(
                runtime,
                name,
                agent_did=make_did(name),
                profile=profile(summary=f"Handles task {index}."),
            )
        caller = await join_member(
            runtime, "researcher", agent_did=make_did("researcher")
        )
        found = await runtime.find(caller["session_token"], "handle a task")
        assert len(found["matches"]) == 15
        assert all(
            match["address"] != "researcher@content-squad" for match in found["matches"]
        )
        limited = await runtime.find(caller["session_token"], "handle a task", limit=3)
        assert len(limited["matches"]) == 3
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_find_detail_full_includes_profile_and_did(team: Team):
    await join_member(team, "writer", profile=_writer())
    caller = await join_member(team, "researcher")
    found = await team.find(caller["session_token"], "draft notes", detail="full")
    match = found["matches"][0]
    assert match["agent_did"]
    assert match["profile"]["skills"][0]["name"] == "drafting"
    summary = await team.find(caller["session_token"], "draft notes")
    assert "agent_did" not in summary["matches"][0]
    assert "profile" not in summary["matches"][0]
    assert "ranking" not in summary


@pytest.mark.asyncio
async def test_find_custom_embedder_orders_by_supplied_vectors():
    async def embed(texts: Sequence[str]) -> list[list[float]]:
        rows: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            legal = (
                1.0
                if any(word in lowered for word in ("contract", "legal", "clause"))
                else 0.0
            )
            writing = (
                1.0
                if any(word in lowered for word in ("draft", "writ", "notes"))
                else 0.0
            )
            rows.append([legal, writing, 0.1])
        return rows

    runtime = Team("content-squad", embeddings=embed)
    await runtime.start()
    try:
        await join_member(runtime, "writer", profile=_writer())
        await join_member(runtime, "reviewer", profile=_legal())
        caller = await join_member(runtime, "researcher")
        found = await runtime.find(
            caller["session_token"], "legal contract clause review"
        )
        assert found["matches"][0]["address"] == "reviewer@content-squad"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_find_reembeds_when_profile_changes():
    calls: list[str] = []

    async def embed(texts: Sequence[str]) -> list[list[float]]:
        rows: list[list[float]] = []
        for text in texts:
            calls.append(text)
            lowered = text.lower()
            rows.append(
                [1.0, 0.0]
                if "legal" in lowered or "contract" in lowered
                else [0.0, 1.0]
            )
        return rows

    runtime = Team("content-squad", embeddings=embed)
    await runtime.start()
    try:
        await join_member(runtime, "writer", profile=_writer())
        caller = await join_member(runtime, "researcher")
        first = await runtime.find(caller["session_token"], "legal contract")
        assert first["matches"][0]["address"] == "writer@content-squad"
        before = len(calls)
        await join_member(
            runtime,
            "writer",
            agent_did=make_did("writer"),
            profile=_legal(),
        )
        second = await runtime.find(caller["session_token"], "legal contract")
        assert second["matches"][0]["address"] == "writer@content-squad"
        assert len(calls) > before
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_find_includes_offline_members(team: Team):
    writer = await join_member(team, "writer", profile=_writer())
    caller = await join_member(team, "researcher")
    await team.disconnect(writer["session_token"])
    found = await team.find(caller["session_token"], "draft notes")
    assert found["matches"][0]["address"] == "writer@content-squad"


@pytest.mark.asyncio
async def test_find_rejects_blank_query(team: Team):
    caller = await join_member(team, "researcher")
    with pytest.raises(TeamError) as exc:
        await team.find(caller["session_token"], "   ")
    assert exc.value.code == "invalid_request"


@pytest.mark.asyncio
async def test_find_equal_scores_break_ties_by_address():
    async def embed(texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    runtime = Team("content-squad", embeddings=embed)
    await runtime.start()
    try:
        await join_member(runtime, "zeta", profile=_writer())
        await join_member(runtime, "alpha", profile=_writer())
        caller = await join_member(runtime, "researcher")
        found = await runtime.find(caller["session_token"], "anything")
        addresses = [match["address"] for match in found["matches"]]
        assert addresses == ["alpha@content-squad", "zeta@content-squad"]
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_find_ranks_one_hundred_members_quickly():
    runtime = Team("content-squad", embeddings="none")
    await runtime.start()
    try:
        for index in range(100):
            name = f"agent{index:03d}"
            kind = "contract" if index == 42 else "draft"
            await join_member(
                runtime,
                name,
                agent_did=make_did(name),
                profile=profile(
                    summary=f"{kind} specialist number {index}.",
                    skill="contract_review" if index == 42 else "drafting",
                    description=f"Work on {kind} tasks.",
                ),
            )
        caller = await join_member(
            runtime, "researcher", agent_did=make_did("researcher")
        )
        started = time.perf_counter()
        found = await runtime.find(
            caller["session_token"], "someone who can review a contract"
        )
        elapsed = time.perf_counter() - started
        assert elapsed < 0.25
        assert found["matches"][0]["address"] == "agent042@content-squad"
        assert len(found["matches"]) == 100
    finally:
        await runtime.stop()


def test_resolve_embedder_none_is_hashed():
    embedder = resolve_embedder("none")
    assert isinstance(embedder, HashedEmbedder)


def test_profile_text_includes_skills_and_examples():
    text = profile_text(
        {
            "summary": "Reviews contracts.",
            "skills": [
                {
                    "name": "contract_review",
                    "description": "List missing clauses.",
                    "examples": ["Check this MSA."],
                }
            ],
            "tags": ["legal"],
        }
    )
    assert "Reviews contracts." in text
    assert "contract_review" in text
    assert "Check this MSA." in text
    assert "legal" in text


@pytest.mark.asyncio
async def test_hashed_embedder_is_deterministic():
    embedder = HashedEmbedder()
    first = await embedder.embed(["Reviews contracts for missing terms."])
    second = await embedder.embed(["Reviews contracts for missing terms."])
    assert first == second
    assert len(first[0]) == 384


def test_as_unit_vector_rejects_non_finite_and_wrong_dim():
    with pytest.raises(ValueError):
        as_unit_vector([float("nan"), 0.0])
    with pytest.raises(ValueError):
        as_unit_vector([float("inf"), 0.0])
    with pytest.raises(ValueError):
        as_unit_vector([1.0, 0.0], expected_dim=3)
    with pytest.raises(ValueError):
        cosine([1.0, 0.0], [1.0])


def _member(name: str, member_profile: dict) -> dict:
    return {
        "name": name,
        "address": f"{name}@content-squad",
        "agent_did": make_did(name),
        "profile": member_profile,
    }


async def _legal_embed(texts: Sequence[str]) -> list[list[float]]:
    rows: list[list[float]] = []
    for text in texts:
        lowered = text.lower()
        legal = (
            1.0
            if any(word in lowered for word in ("contract", "legal", "clause"))
            else 0.0
        )
        writing = (
            1.0 if any(word in lowered for word in ("draft", "writ", "notes")) else 0.0
        )
        rows.append([legal, writing, 0.1])
    return rows


async def _writing_embed(texts: Sequence[str]) -> list[list[float]]:
    rows: list[list[float]] = []
    for text in texts:
        lowered = text.lower()
        writing = (
            1.0 if any(word in lowered for word in ("draft", "writ", "notes")) else 0.0
        )
        legal = (
            1.0
            if any(word in lowered for word in ("contract", "legal", "clause"))
            else 0.0
        )
        rows.append([writing, legal, 0.1])
    return rows


@pytest.mark.asyncio
async def test_find_rebuilds_when_custom_spaces_differ():
    store = MemoryStore()
    first = Directory(store, CallableEmbedder(_legal_embed))
    members = [_member("writer", _writer()), _member("reviewer", _legal())]
    for member in members:
        await first.upsert(member["name"], member["profile"])
    second = Directory(store, CallableEmbedder(_writing_embed))
    found = await second.search(
        "legal contract clause review",
        members,
        exclude_address="researcher@content-squad",
        limit=None,
        detail="summary",
    )
    assert "ranking" not in found
    assert found.matches[0].address == "reviewer@content-squad"


@pytest.mark.asyncio
async def test_find_ignores_malformed_stored_vectors():
    store = MemoryStore()
    directory = Directory(store, CallableEmbedder(_legal_embed))
    members = [_member("writer", _writer()), _member("reviewer", _legal())]
    for member in members:
        await directory.upsert(member["name"], member["profile"])
    record = await store.get("dirvec:reviewer")
    assert isinstance(record, dict)
    record["vector"] = [float("nan"), 0.0, 0.0]
    await store.put("dirvec:reviewer", record)
    wrong = await store.get("dirvec:writer")
    assert isinstance(wrong, dict)
    wrong["vector"] = [1.0]
    await store.put("dirvec:writer", wrong)
    found = await directory.search(
        "legal contract clause review",
        members,
        exclude_address="researcher@content-squad",
        limit=None,
        detail="summary",
    )
    assert found.matches[0].address == "reviewer@content-squad"


class _FailAfter:
    name = "openai:fake"

    def __init__(self, fail_after: int) -> None:
        self.fail_after = fail_after
        self.calls = 0

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        if self.calls > self.fail_after:
            raise RuntimeError("api down")
        return [[1.0, 0.0] for _ in texts]


@pytest.mark.asyncio
async def test_find_fallback_does_not_mix_spaces(caplog):
    embedder = _FailAfter(fail_after=4)
    runtime = Team("content-squad", embeddings=embedder)
    await runtime.start()
    try:
        await join_member(runtime, "alpha", profile=_writer())
        await join_member(runtime, "zeta", profile=_legal())
        caller = await join_member(runtime, "researcher")
        found = await runtime.find(caller["session_token"], "legal contract")
        assert "ranking" not in found
        assert found["matches"][0]["address"] == "zeta@content-squad"
        assert runtime._directory is not None
        assert runtime._directory.using_fallback
        assert runtime._directory.backend_name == "hashed"
        assert "hashed fallback" in caplog.text
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_find_batches_vector_reads():
    store = MemoryStore()
    directory = Directory(store, CallableEmbedder(_legal_embed))
    members = [_member(f"member{index:02d}", _writer()) for index in range(8)]
    for member in members:
        await directory.upsert(member["name"], member["profile"])

    get_calls = {"n": 0}
    many_calls = {"n": 0}
    original_get = store.get
    original_many = store.get_many

    async def counting_get(key: str):
        get_calls["n"] += 1
        return await original_get(key)

    async def counting_many(keys: Sequence[str]):
        many_calls["n"] += 1
        return await original_many(keys)

    store.get = counting_get  # type: ignore[method-assign]
    store.get_many = counting_many  # type: ignore[method-assign]
    found = await directory.search(
        "draft notes",
        members,
        exclude_address="researcher@content-squad",
        limit=None,
        detail="summary",
    )
    assert len(found.matches) == 8
    assert many_calls["n"] == 1
    assert get_calls["n"] == 0


@pytest.mark.asyncio
async def test_sync_embed_does_not_block_event_loop():
    def slow_embed(texts: Sequence[str]) -> list[list[float]]:
        time.sleep(0.2)
        return [[1.0, 0.0] for _ in texts]

    store = MemoryStore()
    directory = Directory(store, CallableEmbedder(slow_embed))
    members = [_member("writer", _writer())]
    await directory.upsert("writer", _writer())
    task = asyncio.create_task(
        directory.search(
            "anything",
            members,
            exclude_address="researcher@content-squad",
            limit=None,
            detail="summary",
        )
    )
    await asyncio.sleep(0)
    delays: list[float] = []
    for _ in range(4):
        started = time.perf_counter()
        await asyncio.sleep(0.02)
        delays.append(time.perf_counter() - started)
    found = await task
    assert found.matches[0].address == "writer@content-squad"
    assert all(delay < 0.1 for delay in delays)


@pytest.mark.asyncio
async def test_find_ranking_does_not_change_send_recipient():
    runtime = Team("content-squad", embeddings="none")
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer", profile=_writer())
        await join_member(runtime, "reviewer", profile=_legal())
        caller = await join_member(runtime, "researcher")
        found = await runtime.find(
            caller["session_token"], "someone who can verify a contract"
        )
        assert found["matches"][0]["address"] == "reviewer@content-squad"
        sent = await runtime.send(
            caller["session_token"],
            {
                "id": str(uuid.uuid4()),
                "recipient": "writer",
                "kind": "event",
                "content": "notes",
            },
        )
        assert sent["message"]["recipient"] == "writer@content-squad"
        leased = await runtime.lease(writer["session_token"], max_items=1)
        assert leased["deliveries"][0]["message"]["recipient"] == "writer@content-squad"
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_light_card_uses_profile_tags_not_skill_tags(team: Team):
    await join_member(
        team,
        "reviewer",
        profile={
            "summary": "Reviews contracts for risk and missing terms.",
            "description": "Use for MSAs and similar commercial contracts.",
            "skills": [
                {
                    "name": "contract_review",
                    "description": "Read a contract and list risks.",
                    "tags": ["msa"],
                }
            ],
            "tags": ["legal", "contracts"],
        },
    )
    caller = await join_member(team, "researcher")
    light = await team.find(caller["session_token"], "verify a contract")
    match = light["matches"][0]
    assert match["tags"] == ["legal", "contracts"]
    full = await team.find(caller["session_token"], "verify a contract", detail="full")
    assert full["matches"][0]["profile"]["skills"][0]["tags"] == ["msa"]
    entry = await team.get_profile(caller["session_token"], "reviewer")
    assert entry["profile"]["description"].startswith("Use for MSAs")


@pytest.mark.asyncio
async def test_auto_embedder_does_not_swap_after_pin():
    inner = _FailAfter(fail_after=1)
    auto = AutoEmbedder()
    auto._inner = inner
    first = await auto.embed(["ok"])
    assert len(first[0]) == 2
    with pytest.raises(RuntimeError):
        await auto.embed(["fail"])
    assert auto.name == "openai:fake"


@pytest.mark.asyncio
async def test_auto_backend_selection_does_not_block_event_loop(monkeypatch):
    def slow_select():
        time.sleep(0.2)
        return HashedEmbedder()

    monkeypatch.setattr(
        "agentconnect.team.directory.embedder._select_auto_backend",
        slow_select,
    )
    auto = AutoEmbedder()
    task = asyncio.create_task(auto.embed(["probe"]))
    await asyncio.sleep(0)
    delays: list[float] = []
    for _ in range(4):
        started = time.perf_counter()
        await asyncio.sleep(0.02)
        delays.append(time.perf_counter() - started)
    rows = await task
    assert len(rows[0]) == 384
    assert all(delay < 0.1 for delay in delays)


@pytest.mark.asyncio
async def test_blocked_embedder_does_not_monopolize_other_directory():
    started = threading.Event()
    release = threading.Event()

    def blocked(texts: Sequence[str]) -> list[list[float]]:
        started.set()
        release.wait(timeout=5)
        return [[1.0, 0.0] for _ in texts]

    def fast(texts: Sequence[str]) -> list[list[float]]:
        return [[0.0, 1.0] for _ in texts]

    first = Directory(MemoryStore(), CallableEmbedder(blocked))
    second = Directory(MemoryStore(), CallableEmbedder(fast))
    task = asyncio.create_task(first.upsert("writer", _writer()))
    assert await asyncio.to_thread(started.wait, 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    began = time.perf_counter()
    await asyncio.wait_for(second.upsert("writer", _writer()), timeout=0.5)
    assert time.perf_counter() - began < 0.4
    found = await second.search(
        "anything",
        [_member("writer", _writer())],
        exclude_address="researcher@content-squad",
        limit=None,
        detail="summary",
    )
    assert found.matches[0].address == "writer@content-squad"
    assert not first.using_fallback
    release.set()


class _FlakyMemory(MemoryStore):
    def __init__(self) -> None:
        super().__init__()
        self.fail_get_many = False

    async def get_many(self, keys: Sequence[str]) -> list[object]:
        if self.fail_get_many:
            raise RuntimeError("store down")
        return await super().get_many(keys)


@pytest.mark.asyncio
async def test_store_failure_does_not_activate_hashed_fallback():
    store = _FlakyMemory()
    directory = Directory(store, CallableEmbedder(_legal_embed))
    members = [_member("writer", _writer()), _member("reviewer", _legal())]
    for member in members:
        await directory.upsert(member["name"], member["profile"])
    store.fail_get_many = True
    with pytest.raises(RuntimeError, match="store down"):
        await directory.search(
            "legal contract clause review",
            members,
            exclude_address="researcher@content-squad",
            limit=None,
            detail="summary",
        )
    assert not directory.using_fallback
    assert directory.backend_name == "custom"
    store.fail_get_many = False
    found = await directory.search(
        "legal contract clause review",
        members,
        exclude_address="researcher@content-squad",
        limit=None,
        detail="summary",
    )
    assert "ranking" not in found
    assert found.matches[0].address == "reviewer@content-squad"


@pytest.mark.asyncio
async def test_embed_fn_sync_async_and_awaitable_results():
    async def async_fn(texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def sync_fn(texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def sync_returns_awaitable(texts: Sequence[str]):
        async def inner() -> list[list[float]]:
            return [[1.0, 0.0] for _ in texts]

        return inner()

    members = [_member("writer", _writer())]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for fn in (async_fn, sync_fn, sync_returns_awaitable):
            directory = Directory(MemoryStore(), CallableEmbedder(fn))
            await directory.upsert("writer", _writer())
            found = await directory.search(
                "anything",
                members,
                exclude_address="researcher@content-squad",
                limit=None,
                detail="summary",
            )
            assert "ranking" not in found
            assert found.matches[0].address == "writer@content-squad"
    leaked = [
        item
        for item in caught
        if issubclass(item.category, RuntimeWarning)
        and "never awaited" in str(item.message).lower()
    ]
    assert leaked == []


def test_find_result_rejects_ranking_field():
    with pytest.raises(ValidationError):
        FindResult.model_validate({"matches": [], "ranking": "configured"})


def _heavy_profile(label: str) -> dict:
    block = ("clause review notes " * 40)[:800]
    examples = [("example clause " * 20)[:400] for _ in range(6)]
    return {
        "summary": f"Handles {label} paperwork.",
        "description": (block * 2)[:1000],
        "skills": [
            {
                "name": f"{label}_{index:02d}",
                "description": block,
                "examples": examples,
            }
            for index in range(8)
        ],
    }


_FILLER = "Routine office paperwork without a named specialty. "


def _about_3600(*, last_name: str, last_blurb: str) -> dict:
    block = (_FILLER * 20)[:600]
    examples = [(_FILLER * 8)[:250], (_FILLER * 8)[:250]]
    return {
        "summary": "Office helper for everyday paperwork.",
        "description": (_FILLER * 40)[:1200],
        "skills": [
            {"name": "admin_one", "description": block, "examples": examples},
            {"name": "admin_two", "description": block, "examples": examples},
            {
                "name": last_name,
                "description": last_blurb,
                "examples": [last_blurb],
            },
        ],
    }


async def _timer_delays(samples: int = 8, sleep_for: float = 0.01) -> list[float]:
    delays: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        await asyncio.sleep(sleep_for)
        delays.append(time.perf_counter() - started)
    return delays


class _TruncatingKeyword:
    name = "openai:trunc"
    input_char_limit = 512
    max_batch = 8

    def __init__(self) -> None:
        self.oversize = 0

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        rows: list[list[float]] = []
        for text in texts:
            if len(text) > 512:
                self.oversize += 1
                raise RuntimeError("payload too large")
            lowered = text.lower()
            salvage = 1.0 if "maritime salvage" in lowered else 0.0
            pedigree = 1.0 if "icelandic horse" in lowered else 0.0
            rows.append([salvage, pedigree, 0.1])
        return rows


class _HostedSpy:
    def __init__(self) -> None:
        self.payloads: list[list[str]] = []

    async def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        self.payloads.append(list(texts))
        raise AssertionError("hosted embedder must not receive content")


@pytest.mark.asyncio
async def test_auto_ignores_ambient_hosted_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-for-network")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-test")
    monkeypatch.setattr(
        "agentconnect.team.directory.embedder._pytest_pins_hashed_auto",
        lambda: False,
    )
    monkeypatch.setattr(
        "agentconnect.team.directory.embedder._module_available",
        lambda name: False,
    )
    spy = _HostedSpy()
    monkeypatch.setattr(OpenAIEmbedder, "embed", spy)
    monkeypatch.setattr(LiteLLMEmbedder, "embed", spy)
    selected = _select_auto_backend()
    assert isinstance(selected, HashedEmbedder)
    auto = AutoEmbedder()
    rows = await auto.embed(["contract review"])
    assert len(rows[0]) == 384
    assert auto.name == "hashed"
    assert spy.payloads == []


@pytest.mark.asyncio
async def test_auto_with_fastembed_available_stays_local(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-for-network")
    monkeypatch.setattr(
        "agentconnect.team.directory.embedder._pytest_pins_hashed_auto",
        lambda: False,
    )
    monkeypatch.setattr(
        "agentconnect.team.directory.embedder._module_available",
        lambda name: name == "fastembed",
    )
    spy = _HostedSpy()
    monkeypatch.setattr(OpenAIEmbedder, "embed", spy)
    monkeypatch.setattr(LiteLLMEmbedder, "embed", spy)
    selected = _select_auto_backend()
    assert isinstance(selected, FastEmbedEmbedder)
    assert spy.payloads == []


@pytest.mark.asyncio
async def test_fallback_with_ambient_key_does_not_host_content(monkeypatch, caplog):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-for-network")
    spy = _HostedSpy()
    monkeypatch.setattr(OpenAIEmbedder, "embed", spy)
    monkeypatch.setattr(LiteLLMEmbedder, "embed", spy)
    embedder = _FailAfter(fail_after=4)
    runtime = Team("content-squad", embeddings=embedder)
    await runtime.start()
    try:
        await join_member(runtime, "alpha", profile=_writer())
        await join_member(runtime, "zeta", profile=_legal())
        caller = await join_member(runtime, "researcher")
        found = await runtime.find(caller["session_token"], "legal contract")
        assert found["matches"][0]["address"] == "zeta@content-squad"
        assert runtime._directory is not None
        assert runtime._directory.using_fallback
        assert "ranking" not in found
        assert spy.payloads == []
        assert "hashed fallback" in caplog.text
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_hashed_rebuild_keeps_event_loop_responsive():
    store = MemoryStore()
    directory = Directory(store, HashedEmbedder())
    members = [
        _member(f"agent{index:02d}", _heavy_profile(f"task{index:02d}"))
        for index in range(12)
    ]
    task = asyncio.create_task(
        directory.search(
            "clause review notes",
            members,
            exclude_address="researcher@content-squad",
            limit=None,
            detail="summary",
        )
    )
    await asyncio.sleep(0)
    delays = await _timer_delays()
    found = await task
    assert len(found.matches) == 12
    assert max(delays) < 0.08


@pytest.mark.asyncio
async def test_warm_ranking_keeps_event_loop_responsive():
    store = MemoryStore()
    directory = Directory(store, HashedEmbedder())
    members = [
        _member(
            f"agent{index:03d}",
            profile(summary=f"Handles similar paperwork {index}."),
        )
        for index in range(400)
    ]
    for member in members:
        await directory.upsert(member["name"], member["profile"])
    await directory.search(
        "similar paperwork",
        members[:8],
        exclude_address="researcher@content-squad",
        limit=None,
        detail="summary",
    )
    task = asyncio.create_task(
        directory.search(
            "similar paperwork",
            members,
            exclude_address="researcher@content-squad",
            limit=None,
            detail="summary",
        )
    )
    await asyncio.sleep(0)
    delays = await _timer_delays()
    found = await task
    assert len(found.matches) == 100
    assert max(delays) < 0.08


@pytest.mark.asyncio
async def test_find_does_not_block_send_occupancy():
    runtime = Team("content-squad", embeddings="none")
    await runtime.start()
    try:
        writer = await join_member(runtime, "writer", profile=_writer())
        for index in range(10):
            name = f"clerk{index:02d}"
            await join_member(
                runtime,
                name,
                agent_did=make_did(name),
                profile=_heavy_profile(name),
            )
        caller = await join_member(
            runtime, "researcher", agent_did=make_did("researcher")
        )
        search = asyncio.create_task(
            runtime.find(caller["session_token"], "clause review notes")
        )
        await asyncio.sleep(0)
        started = time.perf_counter()
        sent = await runtime.send(
            caller["session_token"],
            {
                "id": str(uuid.uuid4()),
                "recipient": "writer",
                "kind": "event",
                "content": "notes",
            },
        )
        elapsed = time.perf_counter() - started
        found = await search
        assert elapsed < 0.25
        assert sent["message"]["recipient"] == "writer@content-squad"
        leased = await runtime.lease(writer["session_token"], max_items=1)
        assert leased["deliveries"][0]["message"]["recipient"] == "writer@content-squad"
        assert found["matches"]
    finally:
        await runtime.stop()


def test_profile_windows_keep_later_skill_out_of_first_budget():
    salvage = _about_3600(
        last_name="salvage_arbitration",
        last_blurb="Handles maritime salvage arbitration disputes.",
    )
    text = profile_text(salvage)
    assert 3000 < len(text) < 5000
    assert "maritime salvage" not in text[:2000]
    assert "maritime salvage" in text
    windows = profile_windows(salvage, 512)
    assert "maritime salvage" not in windows[0]
    assert any("maritime salvage" in window for window in windows)


@pytest.mark.asyncio
async def test_bounded_inputs_keep_later_skills_and_avoid_provider_errors():
    salvage = _about_3600(
        last_name="salvage_arbitration",
        last_blurb="Handles maritime salvage arbitration disputes.",
    )
    pedigree = _about_3600(
        last_name="horse_pedigree",
        last_blurb="Tracks icelandic horse pedigree records.",
    )
    assert profile_text(salvage)[:2000] == profile_text(pedigree)[:2000]
    embedder = _TruncatingKeyword()
    directory = Directory(MemoryStore(), embedder)
    members = [_member("salvage", salvage), _member("pedigree", pedigree)]
    for member in members:
        await directory.upsert(member["name"], member["profile"])
    found = await directory.search(
        "maritime salvage arbitration",
        members,
        exclude_address="researcher@content-squad",
        limit=None,
        detail="summary",
    )
    assert embedder.oversize == 0
    assert found.matches[0].address == "salvage@content-squad"
    assert found.matches[1].address == "pedigree@content-squad"


@pytest.mark.asyncio
async def test_old_space_without_representation_is_rebuilt():
    store = MemoryStore()
    calls = {"n": 0}

    async def embed(texts: Sequence[str]) -> list[list[float]]:
        calls["n"] += 1
        return [[1.0, 0.0] for _ in texts]

    directory = Directory(store, CallableEmbedder(embed))
    await directory.upsert("writer", _writer())
    record = await store.get("dirvec:writer")
    assert isinstance(record, dict)
    record["space"] = "custom:old"
    await store.put("dirvec:writer", record)
    before = calls["n"]
    found = await directory.search(
        "anything",
        [_member("writer", _writer())],
        exclude_address="researcher@content-squad",
        limit=None,
        detail="summary",
    )
    assert found.matches[0].address == "writer@content-squad"
    assert calls["n"] > before
    fresh = await store.get("dirvec:writer")
    assert isinstance(fresh, dict)
    assert fresh["space"] != "custom:old"


@pytest.mark.asyncio
async def test_bge_later_skill_survives_long_profile():
    pytest.importorskip("fastembed")
    from fastembed import TextEmbedding

    from agentconnect.team.directory.embedder import (
        DEFAULT_FASTEMBED_MODEL,
        l2_normalize,
    )

    salvage = _about_3600(
        last_name="salvage_arbitration",
        last_blurb="Handles maritime salvage arbitration disputes.",
    )
    pedigree = _about_3600(
        last_name="horse_pedigree",
        last_blurb="Tracks icelandic horse pedigree records.",
    )
    salvage_text = profile_text(salvage)
    pedigree_text = profile_text(pedigree)
    assert salvage_text[:2000] == pedigree_text[:2000]
    assert "maritime salvage" not in salvage_text[:2000]
    model = TextEmbedding(model_name=DEFAULT_FASTEMBED_MODEL)
    naive = [
        l2_normalize(list(map(float, vector)))
        for vector in model.embed([salvage_text, pedigree_text])
    ]
    assert naive[0] == naive[1]
    store = MemoryStore()
    directory = Directory(store, FastEmbedEmbedder())
    members = [_member("salvage", salvage), _member("pedigree", pedigree)]
    for member in members:
        await directory.upsert(member["name"], member["profile"])
    found = await directory.search(
        "maritime salvage arbitration",
        members,
        exclude_address="researcher@content-squad",
        limit=None,
        detail="summary",
    )
    left = await store.get("dirvec:salvage")
    right = await store.get("dirvec:pedigree")
    assert isinstance(left, dict) and isinstance(right, dict)
    assert left["vector"] != right["vector"]
    assert found.matches[0].address == "salvage@content-squad"


_CJK_FILL = "日常文书处理与常规办公记录整理。"


def _token_dense(*, last_name: str, last_blurb: str) -> dict:
    block = _CJK_FILL * 40
    return {
        "summary": "办公室日常文书助手。",
        "description": block,
        "skills": [
            {
                "name": last_name,
                "description": last_blurb,
                "examples": [last_blurb],
            }
        ],
    }


def _chinese_long(marker: str) -> dict:
    block = "中文档案检索与整理工作记录。" * 730
    return {
        "summary": "中文档案助手。",
        "description": block,
        "skills": [
            {"name": "archive", "description": marker, "examples": [marker]},
        ],
    }


def _provider_tokens(text: str) -> int:
    """Simulated hosted limiter: one token per character."""
    return len(text.strip())


def test_fastembed_token_windows_keep_content_beyond_first_window():
    pytest.importorskip("fastembed")
    from fastembed import TextEmbedding

    from agentconnect.team.directory.embedder import DEFAULT_FASTEMBED_MODEL

    prefix = _CJK_FILL * 40
    suffix = "Handles maritime salvage arbitration disputes."
    text = f"{prefix}\n{suffix}"
    assert 600 < len(text) < 900
    model = TextEmbedding(model_name=DEFAULT_FASTEMBED_MODEL)
    tokenizer = _fastembed_tokenizer(model)
    assert tokenizer is not None
    truncated = tokenizer.encode(text, add_special_tokens=False)
    cut = truncated.offsets[-1][1]
    assert cut < len(text)
    assert "maritime salvage" not in text[:cut]
    complete = encode_complete(tokenizer, text)
    assert complete.offsets[-1][1] >= text.rfind("maritime salvage")
    windows = token_windows(tokenizer, text, local_content_tokens(tokenizer))
    assert len(windows) > 1
    assert "maritime salvage" not in windows[0]
    assert any("maritime salvage" in window for window in windows)
    assert tokenizer.truncation["max_length"] == 512


@pytest.mark.asyncio
async def test_bge_token_dense_profile_keeps_later_skill():
    pytest.importorskip("fastembed")
    from fastembed import TextEmbedding

    from agentconnect.team.directory.embedder import (
        DEFAULT_FASTEMBED_MODEL,
        l2_normalize,
    )

    salvage = _token_dense(
        last_name="salvage_arbitration",
        last_blurb="Handles maritime salvage arbitration disputes.",
    )
    pedigree = _token_dense(
        last_name="horse_pedigree",
        last_blurb="Tracks icelandic horse pedigree records.",
    )
    salvage_text = profile_text(salvage)
    pedigree_text = profile_text(pedigree)
    assert 600 < len(salvage_text) < 900
    assert salvage_text[:500] == pedigree_text[:500]
    assert "maritime salvage" not in salvage_text[:500]
    model = TextEmbedding(model_name=DEFAULT_FASTEMBED_MODEL)
    naive = [
        l2_normalize(list(map(float, vector)))
        for vector in model.embed([salvage_text, pedigree_text])
    ]
    assert naive[0] == naive[1]
    store = MemoryStore()
    directory = Directory(store, FastEmbedEmbedder())
    members = [_member("salvage", salvage), _member("pedigree", pedigree)]
    for member in members:
        await directory.upsert(member["name"], member["profile"])
    found = await directory.search(
        "maritime salvage arbitration",
        members,
        exclude_address="researcher@content-squad",
        limit=None,
        detail="summary",
    )
    left = await store.get("dirvec:salvage")
    right = await store.get("dirvec:pedigree")
    assert isinstance(left, dict) and isinstance(right, dict)
    assert left["vector"] != right["vector"]
    assert str(left["space"]).endswith(":t1")
    assert found.matches[0].address == "salvage@content-squad"
    assert not directory.using_fallback


@pytest.mark.asyncio
async def test_hosted_token_windows_avoid_limit_rejection(monkeypatch):
    salvage = _chinese_long("处理海难救助仲裁争议。")
    pedigree = _chinese_long("登记冰岛马血统档案。")
    salvage_text = profile_text(salvage)
    pedigree_text = profile_text(pedigree)
    assert salvage_text[:8000] == pedigree_text[:8000]
    assert _provider_tokens(salvage_text) > 8192
    assert hosted_token_count(salvage_text) > 8192
    assert "海难救助" not in salvage_text[:8000]
    seen: list[list[str]] = []
    rejected = {"n": 0}

    async def fake_request(self, texts: list[str]) -> list[list[float]]:
        total = 0
        rows: list[list[float]] = []
        for text in texts:
            cost = _provider_tokens(text)
            if cost > 8192:
                rejected["n"] += 1
                raise RuntimeError("max input tokens")
            total += cost
            rows.append(
                [
                    1.0 if "海难救助" in text else 0.0,
                    1.0 if "冰岛马" in text else 0.0,
                    0.1,
                ]
            )
        if total > 300_000:
            rejected["n"] += 1
            raise RuntimeError("max tokens per request")
        seen.append(list(texts))
        return rows

    monkeypatch.setattr(OpenAIEmbedder, "_embed_request", fake_request)
    embedder = OpenAIEmbedder()
    with pytest.raises(RuntimeError, match="max input tokens"):
        await fake_request(embedder, [salvage_text])
    rejected["n"] = 0
    directory = Directory(MemoryStore(), embedder)
    members = [_member("salvage", salvage), _member("pedigree", pedigree)]
    for member in members:
        await directory.upsert(member["name"], member["profile"])
    found = await directory.search(
        "海难救助仲裁",
        members,
        exclude_address="researcher@content-squad",
        limit=None,
        detail="summary",
    )
    assert rejected["n"] == 0
    assert not directory.using_fallback
    assert any("海难救助" in text for payload in seen for text in payload)
    assert found.matches[0].address == "salvage@content-squad"


@pytest.mark.asyncio
async def test_previous_representation_cached_vector_is_rebuilt():
    store = MemoryStore()
    directory = Directory(store, HashedEmbedder())
    await directory.upsert("writer", _writer())
    record = await store.get("dirvec:writer")
    assert isinstance(record, dict)
    assert str(record["space"]).endswith(":t1")
    record["space"] = "hashed:384:w1"
    await store.put("dirvec:writer", record)
    found = await directory.search(
        "anything",
        [_member("writer", _writer())],
        exclude_address="researcher@content-squad",
        limit=None,
        detail="summary",
    )
    assert found.matches[0].address == "writer@content-squad"
    fresh = await store.get("dirvec:writer")
    assert isinstance(fresh, dict)
    assert fresh["space"] != "hashed:384:w1"
    assert str(fresh["space"]).endswith(":t1")
