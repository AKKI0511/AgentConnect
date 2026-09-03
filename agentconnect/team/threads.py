"""Thread transcript storage.

A Thread is an opaque UUID shared by related Messages among a fixed
participant set of one or more Memberships. The first accepted Message
using a ``thread_id`` seeds that set from its sender and recipient.
Later Messages may travel only among those Memberships. The Runtime
assigns a per-Thread ``seq`` on acceptance. History, the delivered
window, and ``before`` cursors order by that value.
"""

from __future__ import annotations

from typing import Any, Optional

from agentconnect.team.codec import json_size
from agentconnect.team.store.base import Store

THREAD_KEY_PREFIX = "thread:"
THREADS_SET = "threads"


def thread_key(thread_id: str) -> str:
    """Return the store key for a Thread record."""
    return f"{THREAD_KEY_PREFIX}{thread_id}"


def _sort_key(message: dict[str, Any]) -> tuple:
    return (int(message["seq"]),)


def _participants_for(sender: str, recipient: str) -> list[str]:
    if sender == recipient:
        return [sender]
    return sorted({sender, recipient})


async def load_thread(store: Store, thread_id: str) -> Optional[dict[str, Any]]:
    """Load a Thread record, or None if it is missing."""
    record = await store.get(thread_key(thread_id))
    if record is None:
        return None
    return record


async def save_thread(store: Store, thread: dict[str, Any]) -> None:
    """Persist a Thread and add it to the Thread set."""
    await store.put(thread_key(thread["id"]), thread)
    await store.set_add(THREADS_SET, thread["id"])


def ensure_thread(
    existing: Optional[dict[str, Any]],
    *,
    thread_id: str,
    sender: str,
    recipient: str,
) -> dict[str, Any]:
    """Return ``existing``, or create a Thread with a fixed participant set."""
    if existing is not None:
        return existing
    return {
        "id": thread_id,
        "participants": _participants_for(sender, recipient),
        "message_ids": [],
        "next_seq": 1,
    }


def participant_set(thread: dict[str, Any]) -> set[str]:
    """Return the Addresses allowed to send in this Thread."""
    return set(thread.get("participants") or [])


def allocate_seq(thread: dict[str, Any], message: dict[str, Any]) -> int:
    """Assign the next Thread sequence onto ``message`` when it is new.

    Replaying an already listed Message leaves its ``seq`` unchanged.
    """
    if message["id"] in thread["message_ids"]:
        seq = message.get("seq")
        if seq is not None:
            return int(seq)
        listed = thread["message_ids"]
        return listed.index(message["id"]) + 1
    seq = int(thread.get("next_seq") or (len(thread["message_ids"]) + 1))
    message["seq"] = seq
    thread["next_seq"] = seq + 1
    return seq


async def append_message(
    store: Store,
    *,
    thread_id: str,
    message: dict[str, Any],
    sender: str,
    recipient: str,
) -> dict[str, Any]:
    """Append ``message`` to the Thread transcript if it is not already listed."""
    thread = ensure_thread(
        await load_thread(store, thread_id),
        thread_id=thread_id,
        sender=sender,
        recipient=recipient,
    )
    allocate_seq(thread, message)
    if message["id"] not in thread["message_ids"]:
        thread["message_ids"].append(message["id"])
    await save_thread(store, thread)
    return thread


def history_window(
    messages: list[dict[str, Any]],
    *,
    delivered_id: str,
    limit: int,
    max_bytes: int,
) -> tuple[list[dict[str, Any]], bool]:
    """Return the bounded recent window of Messages before ``delivered_id``.

    Ordered by ``seq``. ``limit`` is the count cap. ``max_bytes`` is an
    additional UTF-8 JSON budget so a Delivery cannot grow with Message
    size even when the count cap has not been reached.
    """
    ordered = sorted(messages, key=_sort_key)
    earlier: list[dict[str, Any]] = []
    for message in ordered:
        if message["id"] == delivered_id:
            break
        earlier.append(message)
    complete_count = len(earlier)
    if limit <= 0:
        return [], complete_count == 0
    window = earlier[-limit:]
    while window and json_size(window) > max_bytes:
        window = window[1:]
    complete = len(window) == complete_count
    return window, complete


def page_history(
    messages: list[dict[str, Any]],
    *,
    before: Optional[str],
    limit: int,
) -> tuple[list[dict[str, Any]], bool]:
    """Return one page of retained history, oldest of the page first.

    Ordered by ``seq``. Omit ``before`` to read the newest page. A
    ``before`` id that is not in the retained transcript, including one
    retention has removed, returns that newest page. ``has_more`` is
    True when older retained Messages remain before this page.
    """
    ordered = sorted(messages, key=_sort_key)
    if before is not None:
        index = next((i for i, msg in enumerate(ordered) if msg["id"] == before), None)
        if index is None:
            slice_end = len(ordered)
        else:
            slice_end = index
        older = ordered[:slice_end]
    else:
        older = ordered
    page = older[-limit:] if limit else []
    start = len(older) - len(page)
    has_more = start > 0
    return page, has_more


def trim_thread_ids(
    message_ids: list[str],
    messages_by_id: dict[str, dict[str, Any]],
    *,
    keep_ids: set[str],
    max_messages: int,
) -> list[str]:
    """Drop oldest Messages past ``max_messages``, keeping ``keep_ids``."""
    if len(message_ids) <= max_messages:
        return list(message_ids)
    ordered = sorted(
        (messages_by_id[mid] for mid in message_ids if mid in messages_by_id),
        key=_sort_key,
    )
    kept: list[str] = []
    drop_budget = max(0, len(ordered) - max_messages)
    for message in ordered:
        if drop_budget > 0 and message["id"] not in keep_ids:
            drop_budget -= 1
            continue
        kept.append(message["id"])
    return kept
