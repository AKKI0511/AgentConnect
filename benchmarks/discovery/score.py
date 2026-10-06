"""Retrieval benchmark for the discovery corpus.

Ranks held-out and development needs with the production Directory
(hashed and FastEmbed) and a small BM25 baseline. Writes
``artifacts/discovery-v1/``. Does not call a chat model.
"""

from __future__ import annotations

import asyncio
import json
import math
import random
import re
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from agentconnect.team.directory.directory import Directory, profile_text
from agentconnect.team.directory.embedder import (
    DEFAULT_FASTEMBED_MODEL,
    FastEmbedEmbedder,
    HashedEmbedder,
)
from agentconnect.team.store.memory import MemoryStore

from benchmarks.discovery import criteria
from benchmarks.discovery.corpus import CORPUS_REVISION, load_corpus
from benchmarks.discovery.types import Need, Roster

PREPROCESSING_REVISION = "profile-units-v1"
BM25_REVISION = "okapi-k1-1.5-b-0.75-alnum"
SHUFFLE_SEED = 20260922
ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts" / "discovery-v1"

_ALNUM = re.compile(r"[a-z0-9]+")


def alnum_tokens(text: str) -> list[str]:
    return _ALNUM.findall(text.lower())


def bm25_rank(query: str, docs: Mapping[str, str]) -> list[str]:
    """Okapi BM25 over ``profile_text`` documents. Not a production backend."""
    k1 = 1.5
    b = 0.75
    tokenized = {addr: alnum_tokens(text) for addr, text in docs.items()}
    n_docs = len(tokenized)
    if n_docs == 0:
        return []
    avgdl = sum(len(toks) for toks in tokenized.values()) / n_docs
    df: Counter[str] = Counter()
    for toks in tokenized.values():
        df.update(set(toks))
    scores: dict[str, float] = {}
    for addr, toks in tokenized.items():
        tf = Counter(toks)
        dl = len(toks) or 1
        score = 0.0
        for term in alnum_tokens(query):
            freq = tf.get(term, 0)
            if freq == 0:
                continue
            n_qi = df[term]
            idf = math.log(1.0 + (n_docs - n_qi + 0.5) / (n_qi + 0.5))
            denom = freq + k1 * (1.0 - b + b * dl / avgdl)
            score += idf * (freq * (k1 + 1.0)) / denom
        scores[addr] = score
    return sorted(scores, key=lambda addr: (-scores[addr], addr))


def shuffle_roster(roster: Roster, rng: random.Random) -> tuple[Roster, dict[str, str]]:
    old = sorted(roster.members)
    new = old[:]
    rng.shuffle(new)
    mapping = dict(zip(old, new, strict=True))
    members = {
        mapping[addr]: deepcopy(dict(profile))
        for addr, profile in roster.members.items()
    }
    return Roster(id=roster.id, members=members), mapping


def remap_need(need: Need, mapping: Mapping[str, str] | None) -> Need:
    if mapping is None:
        return need
    return Need(
        id=need.id,
        split=need.split,
        roster_id=need.roster_id,
        query=need.query,
        acceptable=frozenset(mapping[addr] for addr in need.acceptable),
        task=need.task,
        slices=need.slices,
    )


def _summary_names(profile: Mapping[str, Any]) -> dict[str, Any]:
    skills = [
        {
            "name": str(skill.get("name") or ""),
            "description": str(skill.get("name") or "skill"),
        }
        for skill in profile.get("skills") or []
        if isinstance(skill, Mapping)
    ]
    return {"summary": str(profile.get("summary") or ""), "skills": skills}


def _did(label: str) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    mapped = "".join(alphabet[ord(ch) % len(alphabet)] for ch in label)
    return "did:key:z" + (mapped + "1" * 48)[:48]


def _members(roster: Roster) -> list[dict[str, Any]]:
    return [
        {
            "name": address,
            "address": f"{address}@discovery",
            "agent_did": _did(address),
            "profile": dict(profile),
        }
        for address, profile in sorted(roster.members.items())
    ]


def _queries(needs: Sequence[Need], roster_id: str) -> list[tuple[str, str]]:
    return [(need.id, need.query) for need in needs if need.roster_id == roster_id]


def attribution_error(
    requested: str, *, using_fallback: bool, backend_name: str
) -> str | None:
    """Return why ``requested`` must not keep these ranks, if it must not.

    Hashed fallback ranks are never reported as neural.
    """
    if using_fallback:
        return f"{requested} fell back to {backend_name}"
    if requested == "neural" and not backend_name.startswith("fastembed:"):
        return f"{requested} ranked with {backend_name}, not a neural backend"
    if requested == "hashed" and backend_name != "hashed":
        return f"{requested} ranked with {backend_name}"
    return None


async def _rank_directory(
    roster: Roster, needs: Sequence[Need], embedder: Any
) -> tuple[dict[str, list[str]], Directory]:
    directory = Directory(MemoryStore(), embedder)
    members = _members(roster)
    ranked: dict[str, list[str]] = {}
    for need_id, query in _queries(needs, roster.id):
        found = await directory.search(
            query,
            members,
            exclude_address="absent@discovery",
            limit=None,
        )
        ranked[need_id] = [match.address.split("@", 1)[0] for match in found.matches]
    return ranked, directory


def _best_rank(ranked: Sequence[str], acceptable: set[str]) -> int | None:
    if not acceptable:
        return None
    for index, address in enumerate(ranked, start=1):
        if address in acceptable:
            return index
    return None


def _coverage(ranks: Sequence[int | None], k: int) -> float | None:
    if not ranks:
        return None
    return sum(1 for rank in ranks if rank is not None and rank <= k) / len(ranks)


def _mrr(ranks: Sequence[int | None]) -> float | None:
    if not ranks:
        return None
    return sum(0.0 if rank is None else 1.0 / rank for rank in ranks) / len(ranks)


def _metrics(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    ranks = [row["best_rank"] for row in rows]
    out: dict[str, Any] = {"denominator": len(rows)}
    for k in criteria.COVERAGE_KS:
        out[f"coverage_at_{k}"] = _coverage(ranks, k)
    out["mrr"] = _mrr(ranks)
    out["recall_at_10_pass"] = (
        out["coverage_at_10"] is not None
        and out["coverage_at_10"] >= criteria.RECALL_AT_10_MIN
    )
    out["mrr_pass"] = out["mrr"] is not None and out["mrr"] >= criteria.MRR_MIN
    return out


def _slices(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    labels: set[str] = set()
    for row in rows:
        labels.update(row["slices"])
    return {
        label: _metrics([row for row in rows if label in row["slices"]])
        for label in sorted(labels)
    }


async def _embedder_ranks(
    rosters: Mapping[str, Roster],
    needs: Sequence[Need],
    embedder: Any,
    *,
    requested: str,
) -> dict[str, list[str]]:
    ranked: dict[str, list[str]] = {}
    for roster in rosters.values():
        part, directory = await _rank_directory(roster, needs, embedder)
        error = attribution_error(
            requested,
            using_fallback=directory.using_fallback,
            backend_name=directory.backend_name,
        )
        if error:
            raise RuntimeError(error)
        ranked.update(part)
    return ranked


def _bm25_ranks(
    rosters: Mapping[str, Roster], needs: Sequence[Need]
) -> dict[str, list[str]]:
    ranked: dict[str, list[str]] = {}
    for roster in rosters.values():
        docs = {addr: profile_text(profile) for addr, profile in roster.members.items()}
        for need_id, query in _queries(needs, roster.id):
            ranked[need_id] = bm25_rank(query, docs)
    return ranked


def _rows_for(
    needs: Sequence[Need],
    ranked: Mapping[str, list[str]],
    rosters: Mapping[str, Roster],
    *,
    backend: str,
    shuffled: bool,
) -> list[dict[str, Any]]:
    rows = []
    for need in needs:
        if not need.acceptable:
            continue
        order = ranked.get(need.id, [])
        best = _best_rank(order, set(need.acceptable))
        rows.append(
            {
                "need_id": need.id,
                "backend": backend,
                "split": need.split,
                "shuffled": shuffled,
                "roster_id": need.roster_id,
                "roster_size": rosters[need.roster_id].size,
                "slices": sorted(need.slices),
                "acceptable": sorted(need.acceptable),
                "best_rank": best,
                "top10": order[:10],
            }
        )
    return rows


def _failure(row: dict[str, Any]) -> bool:
    rank = row["best_rank"]
    return rank is None or rank > 10


async def _load_neural() -> tuple[FastEmbedEmbedder | None, str | None]:
    try:
        embedder = FastEmbedEmbedder()
        await embedder.embed(["discovery probe"])
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    return embedder, None


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Discovery retrieval",
        "",
        f"- Corpus revision: `{payload['corpus_revision']}`",
        f"- Preprocessing revision: `{payload['preprocessing_revision']}`",
        f"- BM25 revision: `{payload['bm25_revision']}`",
        f"- Shuffle seed: `{payload['shuffle_seed']}`",
        f"- Neural model: `{payload['neural']['model_id']}`",
        "",
        "Gates apply to held-out shuffled needs whose acceptable set is non-empty: "
        f"coverage@10 ≥ {criteria.RECALL_AT_10_MIN} and MRR ≥ {criteria.MRR_MIN}. "
        "Coverage@1 and coverage@5 are reported, not gated. "
        "A roster no larger than k cannot show a coverage@k miss.",
        "",
    ]
    if payload["neural"]["load_failure"]:
        lines.append(
            "Neural backend failed to load. Hashed results were not copied in its place."
        )
        lines.append("")
        lines.append("```")
        lines.append(payload["neural"]["load_failure"])
        lines.append("```")
        lines.append("")
    for backend, block in payload["backends"].items():
        if block.get("error"):
            lines.append(f"## {backend}")
            lines.append("")
            lines.append(f"Failed: {block['error']}")
            lines.append("")
            continue
        hold = block["held_out_shuffled"]
        lines.append(f"## {backend} — held-out shuffled")
        lines.append("")
        if block.get("backend_name"):
            lines.append(
                f"Directory backend: `{block['backend_name']}`. "
                f"Fallback: {block.get('using_fallback')}."
            )
            lines.append("")
        lines.append(
            f"Denominator: {hold['denominator']} needs with an acceptable recipient."
        )
        lines.append("")
        lines.append("| Metric | Value | Gate |")
        lines.append("| --- | --- | --- |")
        lines.append(f"| coverage@1 | {_fmt(hold['coverage_at_1'])} |  |")
        lines.append(f"| coverage@5 | {_fmt(hold['coverage_at_5'])} |  |")
        mark = "pass" if hold["recall_at_10_pass"] else "fail"
        lines.append(
            f"| coverage@10 | {_fmt(hold['coverage_at_10'])} | "
            f"{criteria.RECALL_AT_10_MIN} ({mark}) |"
        )
        mark = "pass" if hold["mrr_pass"] else "fail"
        lines.append(f"| MRR | {_fmt(hold['mrr'])} | {criteria.MRR_MIN} ({mark}) |")
        lines.append("")
        lines.append("| Slice | Denominator | coverage@10 | MRR |")
        lines.append("| --- | --- | --- | --- |")
        for label, metrics in hold["slices"].items():
            lines.append(
                f"| {label} | {metrics['denominator']} | "
                f"{_fmt(metrics['coverage_at_10'])} | {_fmt(metrics['mrr'])} |"
            )
        lines.append("")
        lines.append(
            "Roster sizes: "
            + ", ".join(
                f"{name}={size}" for name, size in sorted(block["roster_sizes"].items())
            )
        )
        lines.append("")
    misses = payload["failures"]
    gate_misses = [
        row for row in misses if row["best_rank"] is None or row["best_rank"] > 10
    ]
    lines.append(
        f"Coverage@10 misses: {len(gate_misses)}. "
        f"Coverage@1 misses: {len(misses)}. Both are listed in `results.json`. "
        "Only coverage@10 misses fail the gate."
    )
    lines.append("")
    diag = payload.get("field_diagnostic")
    if diag:
        lines.append("## Field diagnostic")
        lines.append("")
        lines.append(
            "Held-out shuffled coverage@10 and MRR for the full Profile text "
            "versus summary plus skill names. Not a gate and not a field change."
        )
        lines.append("")
        lines.append("| Backend | Representation | Denominator | coverage@10 | MRR |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in diag:
            if row.get("error"):
                lines.append(
                    f"| {row['backend']} | {row['representation']} |  | "
                    f"{row['error']} |  |"
                )
                continue
            lines.append(
                f"| {row['backend']} | {row['representation']} | {row['denominator']} | "
                f"{_fmt(row['coverage_at_10'])} | {_fmt(row['mrr'])} |"
            )
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run() -> dict[str, Any]:
    corpus = load_corpus()
    rng = random.Random(SHUFFLE_SEED)
    shuffled_rosters: dict[str, Roster] = {}
    mappings: dict[str, dict[str, str]] = {}
    for roster_id in sorted(corpus.rosters):
        shuffled, mapping = shuffle_roster(corpus.rosters[roster_id], rng)
        shuffled_rosters[roster_id] = shuffled
        mappings[roster_id] = mapping
    plain_needs = list(corpus.needs)
    shuffled_needs = [
        remap_need(need, mappings[need.roster_id]) for need in plain_needs
    ]
    views = {
        False: (corpus.rosters, plain_needs),
        True: (shuffled_rosters, shuffled_needs),
    }
    neural, neural_error = await _load_neural()
    hashed = HashedEmbedder()
    backends: dict[str, Any] = {}
    failures: list[dict[str, Any]] = []
    rankers: dict[str, Any] = {"hashed": hashed, "bm25": None}
    if neural is not None:
        rankers["neural"] = neural
    for name, embedder in rankers.items():
        block: dict[str, Any] = {
            "roster_sizes": {rid: roster.size for rid, roster in corpus.rosters.items()}
        }
        try:
            for shuffled, (rosters, needs) in views.items():
                if name == "bm25":
                    ranked = _bm25_ranks(rosters, needs)
                else:
                    ranked = await _embedder_ranks(
                        rosters, needs, embedder, requested=name
                    )
                    block["backend_name"] = getattr(embedder, "name", name)
                    block["using_fallback"] = False
                for split in ("development", "held_out"):
                    subset = [need for need in needs if need.split == split]
                    rows = _rows_for(
                        subset, ranked, rosters, backend=name, shuffled=shuffled
                    )
                    key = f"{split}_{'shuffled' if shuffled else 'unshuffled'}"
                    block[key] = _metrics(rows)
                    if split == "held_out" and shuffled:
                        block[key]["slices"] = _slices(rows)
                    if shuffled and split == "held_out":
                        failures.extend(
                            row
                            for row in rows
                            if row["best_rank"] is None or row["best_rank"] > 1
                        )
        except Exception as exc:
            block = {"error": f"{type(exc).__name__}: {exc}"}
        backends[name] = block
    if neural is None:
        backends["neural"] = {"error": neural_error}
    diagnostic = await _field_diagnostic(views[True][0], views[True][1], hashed, neural)
    payload = {
        "corpus_revision": CORPUS_REVISION,
        "preprocessing_revision": PREPROCESSING_REVISION,
        "bm25_revision": BM25_REVISION,
        "shuffle_seed": SHUFFLE_SEED,
        "neural": {
            "model_id": DEFAULT_FASTEMBED_MODEL,
            "load_failure": neural_error,
        },
        "gates": {
            "recall_at_10_min": criteria.RECALL_AT_10_MIN,
            "mrr_min": criteria.MRR_MIN,
        },
        "empty_acceptable": {
            "development": sum(
                1
                for need in plain_needs
                if need.split == "development" and not need.acceptable
            ),
            "held_out": sum(
                1
                for need in plain_needs
                if need.split == "held_out" and not need.acceptable
            ),
        },
        "backends": backends,
        "failures": failures,
        "field_diagnostic": diagnostic,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return payload


def command_status(payload: Mapping[str, Any]) -> int:
    """Fail when a required backend or a held-out ranking gate fails."""
    for name in ("hashed", "bm25", "neural"):
        block = payload.get("backends", {}).get(name)
        if not isinstance(block, Mapping) or block.get("error"):
            return 1
        hold = block.get("held_out_shuffled")
        if not isinstance(hold, Mapping):
            return 1
        if not hold.get("recall_at_10_pass") or not hold.get("mrr_pass"):
            return 1
    for row in payload.get("field_diagnostic") or []:
        if isinstance(row, Mapping) and row.get("error"):
            return 1
    if payload.get("neural", {}).get("load_failure"):
        return 1
    return 0


def publish(payload: Mapping[str, Any]) -> int:
    """Write the current report, and keep a failed run where later runs cannot replace it."""
    status = command_status(payload)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=2) + "\n"
    if status != 0:
        failed = ARTIFACT_DIR / "failed"
        failed.mkdir(exist_ok=True)
        stamp = str(payload.get("generated_at_utc", "run")).replace(":", "")
        path = failed / f"{stamp}.json"
        suffix = 1
        while path.exists():
            path = failed / f"{stamp}-{suffix}.json"
            suffix += 1
        path.write_text(body, encoding="utf-8")
        return status
    (ARTIFACT_DIR / "results.json").write_text(body, encoding="utf-8")
    _write_markdown(dict(payload), ARTIFACT_DIR / "RESULTS.md")
    return status


async def _field_diagnostic(rosters, needs, hashed, neural) -> list[dict[str, Any]]:
    held = [need for need in needs if need.split == "held_out"]
    full = rosters
    thin_rosters = {}
    for roster_id, roster in rosters.items():
        thin_rosters[roster_id] = Roster(
            id=roster.id,
            members={
                addr: _summary_names(profile)
                for addr, profile in roster.members.items()
            },
        )
    rows = []
    embedders: list[tuple[str, Any]] = [("hashed", hashed)]
    if neural is not None:
        embedders.append(("neural", neural))
    for backend, embedder in embedders:
        for label, group in (
            ("full_profile_text", full),
            ("summary_and_skill_names", thin_rosters),
        ):
            try:
                ranked = await _embedder_ranks(group, held, embedder, requested=backend)
            except RuntimeError as exc:
                rows.append(
                    {
                        "backend": backend,
                        "representation": label,
                        "error": str(exc),
                    }
                )
                continue
            metrics = _metrics(
                _rows_for(held, ranked, group, backend=backend, shuffled=True)
            )
            rows.append(
                {
                    "backend": backend,
                    "representation": label,
                    "denominator": metrics["denominator"],
                    "coverage_at_10": metrics["coverage_at_10"],
                    "mrr": metrics["mrr"],
                    "using_fallback": False,
                }
            )
    return rows


def main() -> None:
    import sys

    payload = asyncio.run(run())
    status = publish(payload)
    print(ARTIFACT_DIR)
    for name, block in payload["backends"].items():
        if block.get("error"):
            print(name, "FAILED", block["error"])
            continue
        hold = block["held_out_shuffled"]
        print(
            name,
            block.get("backend_name", name),
            "fallback",
            block.get("using_fallback"),
            "coverage@10",
            hold["coverage_at_10"],
            "mrr",
            hold["mrr"],
            "n",
            hold["denominator"],
        )
    sys.exit(status)


if __name__ == "__main__":
    main()
