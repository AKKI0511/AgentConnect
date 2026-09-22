"""Failure handling for the discovery retrieval runner."""

from __future__ import annotations

from benchmarks.discovery.score import attribution_error, command_status, publish
from benchmarks.discovery import score


def _hold(*, recall: bool = True, mrr: bool = True) -> dict:
    return {
        "denominator": 1,
        "coverage_at_1": 1.0,
        "coverage_at_5": 1.0,
        "coverage_at_10": 1.0,
        "mrr": 1.0,
        "recall_at_10_pass": recall,
        "mrr_pass": mrr,
        "slices": {},
    }


def _payload() -> dict:
    backend = {
        "roster_sizes": {},
        "backend_name": "fastembed:example",
        "using_fallback": False,
        "held_out_shuffled": _hold(),
    }
    hashed = {
        "roster_sizes": {},
        "backend_name": "hashed",
        "using_fallback": False,
        "held_out_shuffled": _hold(),
    }
    return {
        "generated_at_utc": "2026-09-22T00:00:00Z",
        "corpus_revision": "discovery-v1",
        "preprocessing_revision": "profile-units-v1",
        "bm25_revision": "okapi-k1-1.5-b-0.75-alnum",
        "shuffle_seed": 20260922,
        "failures": [],
        "neural": {"model_id": "example", "load_failure": None},
        "backends": {
            "hashed": hashed,
            "bm25": {"roster_sizes": {}, "held_out_shuffled": _hold()},
            "neural": backend,
        },
        "field_diagnostic": [],
    }


def test_hashed_fallback_is_not_labeled_neural():
    assert (
        attribution_error("neural", using_fallback=True, backend_name="hashed")
        == "neural fell back to hashed"
    )
    assert attribution_error("neural", using_fallback=False, backend_name="hashed")
    assert (
        attribution_error(
            "neural",
            using_fallback=False,
            backend_name="fastembed:BAAI/bge-small-en-v1.5",
        )
        is None
    )
    assert (
        attribution_error("hashed", using_fallback=False, backend_name="hashed") is None
    )


def test_required_backend_or_gate_failure_fails_the_command():
    assert command_status(_payload()) == 0
    fallen = _payload()
    fallen["backends"]["neural"] = {"error": "neural fell back to hashed"}
    assert command_status(fallen) == 1
    missed = _payload()
    missed["backends"]["hashed"]["held_out_shuffled"]["recall_at_10_pass"] = False
    assert command_status(missed) == 1
    diagnostic = _payload()
    diagnostic["field_diagnostic"] = [
        {
            "backend": "neural",
            "representation": "full_profile_text",
            "error": "fell back",
        }
    ]
    assert command_status(diagnostic) == 1


def test_failed_run_is_kept_when_a_later_run_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(score, "ARTIFACT_DIR", tmp_path)
    failed = _payload()
    failed["generated_at_utc"] = "2026-09-22T00:00:00Z"
    failed["backends"]["neural"] = {"error": "neural fell back to hashed"}
    assert publish(failed) == 1
    kept = next((tmp_path / "failed").iterdir())
    original = kept.read_text(encoding="utf-8")
    assert "fell back" in original
    success = _payload()
    success["generated_at_utc"] = "2026-09-22T01:00:00Z"
    assert publish(success) == 0
    assert kept.read_text(encoding="utf-8") == original
    assert (tmp_path / "results.json").is_file()
    again = _payload()
    again["generated_at_utc"] = "2026-09-22T00:00:00Z"
    again["backends"]["bm25"] = {"error": "bm25 failed"}
    assert publish(again) == 1
    assert len(list((tmp_path / "failed").iterdir())) == 2
    assert kept.read_text(encoding="utf-8") == original
