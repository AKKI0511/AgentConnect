"""Token budgets for Directory embedding backends.

Neural backends split here so a valid Profile is neither truncated nor
rejected as a provider outage. Directory character packing stays on
backends that publish a character limit.
"""

from __future__ import annotations

from typing import Any, Sequence

# OpenAI embedding models: 8192 tokens per input, 300_000 per request.
# Windows use 8191 so a request stays strictly inside the published cap.
OPENAI_INPUT_TOKENS = 8191
OPENAI_REQUEST_TOKENS = 300_000
DEFAULT_LOCAL_INPUT_TOKENS = 512

_TIKTOKEN: Any = None
_TIKTOKEN_MISSING = False


def hosted_token_count(text: str) -> int:
    """Return a cl100k_base count, or a dense estimate that does not under-count."""
    stripped = text.strip()
    if not stripped:
        return 0
    encoder = _cl100k()
    if encoder is not None:
        return len(encoder.encode(stripped))
    return _estimate_token_count(stripped)


def hosted_token_windows(text: str, max_tokens: int = OPENAI_INPUT_TOKENS) -> list[str]:
    """Split ``text`` into windows of at most ``max_tokens`` hosted tokens."""
    if max_tokens < 1:
        raise ValueError("token limit must be positive")
    stripped = text.strip()
    if not stripped:
        return [""]
    encoder = _cl100k()
    if encoder is not None:
        tokens = encoder.encode(stripped)
        if len(tokens) <= max_tokens:
            return [stripped]
        windows: list[str] = []
        for start in range(0, len(tokens), max_tokens):
            piece = encoder.decode(tokens[start : start + max_tokens])
            if piece:
                windows.append(piece)
        return windows or [stripped]
    return estimate_token_windows(stripped, max_tokens)


def pack_token_batches(
    texts: Sequence[str],
    counts: Sequence[int],
    *,
    batch: int,
    request_tokens: int,
) -> list[list[str]]:
    """Group windows so no request exceeds ``batch`` items or ``request_tokens``."""
    if len(texts) != len(counts):
        raise ValueError("token counts must match texts")
    if batch < 1 or request_tokens < 1:
        raise ValueError("batch and request token limits must be positive")
    chunks: list[list[str]] = []
    current: list[str] = []
    used = 0
    for text, count in zip(texts, counts, strict=True):
        cost = max(0, int(count))
        if current and (len(current) >= batch or used + cost > request_tokens):
            chunks.append(current)
            current = []
            used = 0
        current.append(text)
        used += cost
    if current:
        chunks.append(current)
    return chunks


def estimate_token_windows(text: str, max_tokens: int) -> list[str]:
    """Split ``text`` using a dense per-character estimate that does not under-count."""
    if max_tokens < 1:
        raise ValueError("token limit must be positive")
    stripped = text.strip()
    if not stripped:
        return [""]
    windows: list[str] = []
    buf: list[str] = []
    used = 0
    for char in stripped:
        cost = _char_token_cost(char)
        if buf and used + cost > max_tokens:
            windows.append("".join(buf))
            buf = [char]
            used = cost
            continue
        buf.append(char)
        used += cost
    if buf:
        windows.append("".join(buf))
    return windows or [stripped]


def encode_complete(tokenizer: Any, text: str) -> Any:
    """Encode ``text`` without the tokenizer's truncation cap."""
    saved = getattr(tokenizer, "truncation", None)
    disable = getattr(tokenizer, "no_truncation", None)
    if callable(disable):
        disable()
    try:
        try:
            return tokenizer.encode(text, add_special_tokens=False)
        except TypeError:
            return tokenizer.encode(text)
    finally:
        _restore_truncation(tokenizer, saved)


def local_content_tokens(tokenizer: Any) -> int:
    """Content-token budget for one local model input, excluding special tokens."""
    trunc = getattr(tokenizer, "truncation", None) or {}
    try:
        max_length = int(trunc.get("max_length") or DEFAULT_LOCAL_INPUT_TOKENS)
    except (TypeError, ValueError, AttributeError):
        max_length = DEFAULT_LOCAL_INPUT_TOKENS
    special = 2
    adder = getattr(tokenizer, "num_special_tokens_to_add", None)
    if callable(adder):
        try:
            special = int(adder(False))
        except TypeError:
            try:
                special = int(adder())
            except (TypeError, ValueError):
                special = 2
        except (TypeError, ValueError):
            special = 2
    return max(1, max_length - max(0, special))


def token_windows(tokenizer: Any, text: str, max_tokens: int) -> list[str]:
    """Split ``text`` on complete token ids, using original character offsets."""
    if max_tokens < 1:
        raise ValueError("token limit must be positive")
    stripped = text.strip()
    if not stripped:
        return [""]
    encoded = encode_complete(tokenizer, stripped)
    ids = getattr(encoded, "ids", encoded)
    if not isinstance(ids, (list, tuple)):
        try:
            ids = list(ids)
        except TypeError:
            return estimate_token_windows(stripped, max_tokens)
    if len(ids) <= max_tokens:
        return [stripped]
    offsets = getattr(encoded, "offsets", None)
    windows: list[str] = []
    for start in range(0, len(ids), max_tokens):
        end = min(start + max_tokens, len(ids))
        piece = _window_text(tokenizer, stripped, ids, offsets, start, end)
        if piece:
            windows.append(piece)
    return windows or estimate_token_windows(stripped, max_tokens)


def _window_text(
    tokenizer: Any,
    stripped: str,
    ids: Sequence[Any],
    offsets: Any,
    start: int,
    end: int,
) -> str:
    if isinstance(offsets, (list, tuple)) and end - 1 < len(offsets):
        first = offsets[start]
        last = offsets[end - 1]
        try:
            char_start = int(first[0])
            char_end = int(last[1])
        except (TypeError, ValueError, IndexError):
            char_start = -1
            char_end = -1
        if 0 <= char_start < char_end <= len(stripped):
            return stripped[char_start:char_end]
    decode = getattr(tokenizer, "decode", None)
    if callable(decode):
        try:
            piece = decode(list(ids[start:end]))
        except Exception:
            piece = ""
        if piece:
            return str(piece)
    return ""


def _restore_truncation(tokenizer: Any, saved: Any) -> None:
    if not saved:
        return
    enable = getattr(tokenizer, "enable_truncation", None)
    if not callable(enable):
        return
    try:
        enable(
            max_length=int(saved["max_length"]),
            stride=int(saved.get("stride") or 0),
            strategy=saved.get("strategy") or "longest_first",
            direction=saved.get("direction") or "right",
        )
    except (TypeError, ValueError, KeyError):
        try:
            enable(**dict(saved))
        except Exception:
            return


def _cl100k() -> Any:
    global _TIKTOKEN, _TIKTOKEN_MISSING
    if _TIKTOKEN_MISSING:
        return None
    if _TIKTOKEN is not None:
        return _TIKTOKEN
    try:
        import tiktoken
    except ImportError:
        _TIKTOKEN_MISSING = True
        return None
    _TIKTOKEN = tiktoken.get_encoding("cl100k_base")
    return _TIKTOKEN


def _estimate_token_count(text: str) -> int:
    return sum(_char_token_cost(char) for char in text)


def _char_token_cost(char: str) -> int:
    code = ord(char)
    if code < 128:
        return 1
    if code < 0x10000:
        return 2
    return 3
