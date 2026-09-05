"""Canonical JSON used for Message idempotency."""

from agentconnect.team.codec import canonical_json, semantic_hash


def test_numbers_normalize_across_int_float_and_scientific():
    assert canonical_json({"n": 1}) == canonical_json({"n": 1.0})
    assert canonical_json({"n": 1}) == canonical_json({"n": 1e0})
    assert semantic_hash({"n": 1}) == semantic_hash({"n": 1.0})
    assert semantic_hash({"n": 1}) == semantic_hash({"n": 1e0})


def test_object_key_order_does_not_change_hash():
    assert semantic_hash({"a": 1, "b": 2}) == semantic_hash({"b": 2, "a": 1})


def test_array_order_is_significant():
    assert semantic_hash([1, 2]) != semantic_hash([2, 1])


def test_timestamp_score_orders_past_before_future():
    from datetime import timedelta

    from agentconnect.team.codec import format_timestamp, timestamp_score, utc_now

    now = utc_now()
    past = format_timestamp(now - timedelta(seconds=5))
    future = format_timestamp(now + timedelta(seconds=5))
    assert timestamp_score(past) < timestamp_score(now) < timestamp_score(future)
