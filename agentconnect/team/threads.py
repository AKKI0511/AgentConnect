"""Thread transcript storage.

A Thread is an opaque UUID shared by related Messages among a fixed
participant set of Membership identities. The first accepted Message
using a ``thread_id`` seeds that set from the sending and receiving
Memberships. Later Messages may travel only among those identities.
Address reuse after removal is a different Membership. The Runtime
assigns a per-Thread ``seq`` on acceptance. History, the delivered
window, and ``before`` cursors order by that value.
"""

from __future__ import annotations

from typing import Any, Optional

from agentconnect.team.codec import json_size
from agentconnect.team.store.base import Store, StoreRecord
from agentconnect.team.store.ops import Cas, Insert, SetAdd, StoreOp
from agentconnect.team.retention import LIVE_MESSAGES_SET, RETAIN_MESSAGES_SET

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
    """Return the Membership identities allowed to send in this Thread."""
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


def copy_thread(thread: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of Thread fields the Runtime mutates."""
    return {
        "id": thread["id"],
        "participants": list(thread.get("participants") or []),
        "message_ids": list(thread.get("message_ids") or []),
        "next_seq": thread.get("next_seq"),
    }


def prepare_append(
    record: Optional[StoreRecord],
    *,
    thread_id: str,
    message: dict[str, Any],
    sender: str,
    recipient: str,
    max_messages: Optional[int] = None,
    keep_ids: Optional[set[str]] = None,
    parent_thread_id: Optional[str] = None,
) -> tuple[dict[str, Any], list[StoreOp], Optional[str]]:
    """Build the Thread write for one Message.

    Returns ``(thread, ops, error)``. ``error`` is ``forbidden`` when
    ``sender`` or ``recipient`` is outside a Thread that already exists,
    or ``invalid_request`` when ``parent_id`` names a Message from
    another Thread and this Thread already exists.
    Mutates ``message['seq']`` when the Message is new.
    ``max_messages`` and ``keep_ids`` are accepted for callers that trim
    after this returns. This function does not load retained Message
    bodies or enumerate Team-wide keep sets.
    """
    existing = None if record is None else dict(record.value)
    if existing is not None:
        participants = participant_set(existing)
        if sender not in participants or recipient not in participants:
            return existing, [], "forbidden"
        if parent_thread_id is not None and parent_thread_id != thread_id:
            return existing, [], "invalid_request"
        thread = copy_thread(existing)
    else:
        thread = ensure_thread(
            None,
            thread_id=thread_id,
            sender=sender,
            recipient=recipient,
        )
    allocate_seq(thread, message)
    if message["id"] not in thread["message_ids"]:
        thread["message_ids"].append(message["id"])
    del max_messages, keep_ids
    key = thread_key(thread_id)
    if record is None:
        ops: list[StoreOp] = [Insert(key, thread), SetAdd(THREADS_SET, thread_id)]
    else:
        ops = [Cas(key, record.version, thread)]
    return thread, ops, None


async def append_message(
    store: Store,
    *,
    thread_id: str,
    message: dict[str, Any],
    sender: str,
    recipient: str,
    max_messages: Optional[int] = None,
    keep_ids: Optional[set[str]] = None,
) -> dict[str, Any]:
    """Append ``message`` to the Thread transcript if it is not already listed.

    Compare-and-set on the Thread document assigns ``seq``. Two concurrent
    appends receive distinct values in the order the store accepts them.
    When ``max_messages`` is set, oldest Messages not in ``keep_ids`` are
    dropped from the id list on the same write. Bodies are deleted by the
    caller.
    """
    key = thread_key(thread_id)
    while True:
        record = await store.get_record(key)
        thread, ops, error = prepare_append(
            record,
            thread_id=thread_id,
            message=message,
            sender=sender,
            recipient=recipient,
            max_messages=max_messages,
            keep_ids=keep_ids,
        )
        if error == "forbidden":
            return thread
        result = await store.apply(ops)
        if result.ok:
            return thread
        if result.reason in {"exists", "cas"}:
            continue
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


def history_ids_before(
    message_ids: list[str],
    *,
    delivered_id: str,
    limit: int,
) -> tuple[list[str], bool]:
    """Return earlier Message ids before ``delivered_id``, capped by ``limit``.

    ``message_ids`` is seq order. No bodies are read.
    """
    try:
        index = message_ids.index(delivered_id)
        earlier = message_ids[:index]
    except ValueError:
        earlier = list(message_ids)
    complete_count = len(earlier)
    if limit <= 0:
        return [], complete_count == 0
    window = earlier[-limit:]
    return window, len(window) == complete_count


def history_id_window(
    messages: list[dict[str, Any]],
    *,
    delivered_id: str,
    limit: int,
) -> tuple[list[str], bool]:
    """Return earlier Message ids before ``delivered_id``, capped by ``limit``.

    Ordered by ``seq``. No byte budget; ids are small.
    """
    ordered = sorted(messages, key=_sort_key)
    return history_ids_before(
        [message["id"] for message in ordered],
        delivered_id=delivered_id,
        limit=limit,
    )


def page_history_ids(
    message_ids: list[str],
    *,
    before: Optional[str],
    limit: int,
) -> tuple[list[str], bool]:
    """Return one page of retained ids, oldest of the page first.

    ``message_ids`` is seq order. Omit ``before`` to read the newest page.
    A ``before`` id that is not in the list returns that newest page.
    """
    if before is not None:
        try:
            index = message_ids.index(before)
        except ValueError:
            index = len(message_ids)
        older = message_ids[:index]
    else:
        older = message_ids
    page = older[-limit:] if limit else []
    has_more = (len(older) - len(page)) > 0
    return page, has_more


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
    ids = [message["id"] for message in ordered]
    page_ids, has_more = page_history_ids(ids, before=before, limit=limit)
    by_id = {message["id"]: message for message in ordered}
    page = [by_id[item] for item in page_ids if item in by_id]
    return page, has_more


def trim_thread_ids(
    message_ids: list[str],
    *,
    keep_ids: set[str],
    max_messages: int,
) -> list[str]:
    """Drop oldest Messages past ``max_messages``, keeping ``keep_ids``.

    ``message_ids`` is seq order, oldest first. Ids in ``keep_ids`` stay
    even when that leaves the Thread longer than ``max_messages``.
    """
    if len(message_ids) <= max_messages:
        return list(message_ids)
    kept: list[str] = []
    drop_budget = max(0, len(message_ids) - max_messages)
    for message_id in message_ids:
        if drop_budget > 0 and message_id not in keep_ids:
            drop_budget -= 1
            continue
        kept.append(message_id)
    return kept


async def drop_unprotected_ids(
    store: Store,
    message_ids: list[str],
    *,
    max_messages: int,
    protect: Optional[set[str]] = None,
) -> tuple[list[str], list[str]]:
    """Return ``(kept, dropped)`` without loading the whole retain set.

    Each candidate uses a membership check on live Mailbox work and on
    ``retain:messages``. Queued or leased ids stay in the Thread.
    """
    if max_messages < 0 or len(message_ids) <= max_messages:
        return list(message_ids), []
    held = protect or set()
    kept: list[str] = []
    dropped: list[str] = []
    budget = len(message_ids) - max_messages
    for message_id in message_ids:
        if budget > 0 and message_id not in held:
            live = await store.set_is_member(LIVE_MESSAGES_SET, message_id)
            needed = await store.set_is_member(RETAIN_MESSAGES_SET, message_id)
            if not live and not needed:
                dropped.append(message_id)
                budget -= 1
                continue
        kept.append(message_id)
    return kept, dropped
