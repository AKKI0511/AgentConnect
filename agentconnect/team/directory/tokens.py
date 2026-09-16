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
_TIKTOKEN_PROVIDERS = frozenset({"openai", "azure"})
_OPENAI_INSTALL = "pip install 'agentconnect[openai]'"
_LITELLM_INSTALL = "pip install 'agentconnect[aiagent,openai]'"


class EmbeddingSetupError(RuntimeError):
    """Hosted embedding extras or model metadata are missing or unsafe."""


def require_tiktoken() -> Any:
    """Import tiktoken or raise an install error."""
    try:
        import tiktoken
    except ImportError as exc:
        raise EmbeddingSetupError(
            "OpenAI Directory embeddings require tiktoken. "
            f"Install it with {_OPENAI_INSTALL}."
        ) from exc
    return tiktoken


def encoding_for_hosted_model(model: str) -> Any:
    """Return the tiktoken encoding for an OpenAI-compatible embedding model."""
    tiktoken = require_tiktoken()
    names = [model]
    if "/" in model:
        names.append(model.rsplit("/", 1)[-1])
    for name in names:
        try:
            return tiktoken.encoding_for_model(name)
        except KeyError:
            continue
    return tiktoken.get_encoding("cl100k_base")


def encode_hosted(encoding: Any, text: str) -> list[int]:
    """Encode ``text``, keeping literal special-token strings as ordinary text."""
    return encoding.encode(text, disallowed_special=())


def split_token_windows(encoding: Any, text: str, max_tokens: int) -> list[list[int]]:
    """Split ``text`` into token-id windows of at most ``max_tokens``."""
    if max_tokens < 1:
        raise ValueError("token limit must be positive")
    stripped = text.strip()
    if not stripped:
        return [[]]
    token_ids = encode_hosted(encoding, stripped)
    return [
        token_ids[index : index + max_tokens]
        for index in range(0, len(token_ids), max_tokens)
    ]


def pack_token_batches(
    windows: Sequence[Sequence[int]],
    *,
    batch: int,
    request_tokens: int,
) -> list[list[list[int]]]:
    """Group token windows so no request exceeds ``batch`` or ``request_tokens``."""
    if batch < 1 or request_tokens < 1:
        raise ValueError("batch and request token limits must be positive")
    chunks: list[list[list[int]]] = []
    current: list[list[int]] = []
    used = 0
    for window in windows:
        ids = list(window)
        cost = len(ids)
        if current and (len(current) >= batch or used + cost > request_tokens):
            chunks.append(current)
            current = []
            used = 0
        current.append(ids)
        used += cost
    if current:
        chunks.append(current)
    return chunks


def litellm_embedding_info(model: str) -> dict[str, Any]:
    """Return LiteLLM metadata for ``model``, or raise a setup error."""
    try:
        from litellm.utils import get_model_info
    except ImportError as exc:
        raise EmbeddingSetupError(
            "LiteLLM Directory embeddings require litellm and tiktoken. "
            f"Install them with {_LITELLM_INSTALL}."
        ) from exc
    try:
        info = get_model_info(model)
    except Exception as exc:
        raise EmbeddingSetupError(
            f"LiteLLM has no embedding metadata for {model!r}. "
            "Use an OpenAI or Azure embedding model, or embeddings='openai'."
        ) from exc
    return dict(info)


def hosted_litellm_limits(model: str) -> tuple[int, int]:
    """Return per-input and per-request token limits for a supported model.

    LiteLLM's generic tokenizer is cl100k for most embedding providers,
    including Cohere. Only OpenAI and Azure embedding models have a
    tiktoken encoding that matches the hosted model.
    """
    require_tiktoken()
    info = litellm_embedding_info(model)
    mode = info.get("mode")
    provider = str(info.get("litellm_provider") or "")
    if mode != "embedding":
        raise EmbeddingSetupError(
            f"LiteLLM model {model!r} is mode {mode!r}, not embedding."
        )
    if provider not in _TIKTOKEN_PROVIDERS:
        raise EmbeddingSetupError(
            "LiteLLM Directory embeddings are supported only for OpenAI and "
            "Azure models whose tokenizer is tiktoken. "
            f"{model!r} uses provider {provider!r}, which LiteLLM tokenizes "
            "with a generic fallback that is not model-exact. Use "
            "embeddings='openai' or litellm:<openai-or-azure-embedding-model>. "
            f"Install with {_LITELLM_INSTALL}."
        )
    raw = info.get("max_input_tokens")
    if raw is None:
        raw = info.get("max_tokens")
    try:
        input_tokens = int(raw)
    except (TypeError, ValueError):
        input_tokens = 0
    if input_tokens < 1:
        raise EmbeddingSetupError(
            f"LiteLLM metadata for {model!r} does not include a positive "
            "max_input_tokens value."
        )
    return input_tokens, OPENAI_REQUEST_TOKENS


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
        except TypeError as exc:
            raise RuntimeError("tokenizer did not return token ids") from exc
    if len(ids) <= max_tokens:
        return [stripped]
    offsets = getattr(encoded, "offsets", None)
    windows: list[str] = []
    for start in range(0, len(ids), max_tokens):
        end = min(start + max_tokens, len(ids))
        piece = _window_text(tokenizer, stripped, ids, offsets, start, end)
        windows.append(piece)
    return windows


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
        piece = decode(list(ids[start:end]))
        if piece:
            return str(piece)
    raise RuntimeError("tokenizer window decode produced no text")


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
