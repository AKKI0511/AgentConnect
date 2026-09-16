"""Tokenizer-backed hosted windows and request packing."""

from __future__ import annotations

import builtins
import sys

import pytest

from agentconnect.team import Team
from agentconnect.team.directory.embedder import (
    FastEmbedEmbedder,
    LiteLLMEmbedder,
    OpenAIEmbedder,
)
from agentconnect.team.directory.tokens import (
    OPENAI_INPUT_TOKENS,
    OPENAI_REQUEST_TOKENS,
    EmbeddingSetupError,
    encode_hosted,
    encoding_for_hosted_model,
    pack_token_batches,
    split_token_windows,
)


def test_neural_backends_own_token_limits():
    assert OpenAIEmbedder.input_char_limit is None
    assert LiteLLMEmbedder.input_char_limit is None
    assert FastEmbedEmbedder.input_char_limit is None
    assert OpenAIEmbedder.input_token_limit == OPENAI_INPUT_TOKENS
    assert OpenAIEmbedder.request_token_limit == OPENAI_REQUEST_TOKENS


def test_hosted_windows_keep_dense_cjk_inside_input_budget():
    tiktoken = pytest.importorskip("tiktoken")
    encoding = tiktoken.encoding_for_model("text-embedding-3-small")
    text = "海难救助仲裁争议处理专家。" * 800
    assert len(text) > 10000
    full = encode_hosted(encoding, text)
    assert len(full) > OPENAI_INPUT_TOKENS
    windows = split_token_windows(encoding, text, OPENAI_INPUT_TOKENS)
    assert len(windows) > 1
    assert [token for window in windows for token in window] == full
    joined = "".join(encoding.decode_with_offsets(window)[0] for window in windows)
    assert joined == text
    for window in windows:
        assert len(window) <= OPENAI_INPUT_TOKENS
        decoded, _offsets = encoding.decode_with_offsets(window)
        assert "\ufffd" not in decoded


def test_literal_endoftext_stays_ordinary_text():
    pytest.importorskip("tiktoken")
    encoding = encoding_for_hosted_model("text-embedding-3-small")
    text = "Keep <|endoftext|> as literal text."
    with pytest.raises(ValueError, match="endoftext"):
        encoding.encode(text)
    ids = encode_hosted(encoding, text)
    decoded, _offsets = encoding.decode_with_offsets(ids)
    assert decoded == text
    assert "<|endoftext|>" in decoded


def test_emoji_windows_do_not_insert_replacement_characters():
    pytest.importorskip("tiktoken")
    encoding = encoding_for_hosted_model("text-embedding-3-small")
    text = "😀" * 5000
    windows = split_token_windows(encoding, text, 64)
    assert len(windows) > 1
    concat = [token for window in windows for token in window]
    assert concat == encode_hosted(encoding, text)
    joined = "".join(encoding.decode_with_offsets(window)[0] for window in windows)
    assert joined == text
    assert "\ufffd" not in joined
    naive = "".join(encoding.decode(window) for window in windows)
    if naive != text:
        assert "\ufffd" in naive


def test_pack_token_batches_splits_before_request_budget():
    windows = [[1] * 8000 for _ in range(50)]
    chunks = pack_token_batches(
        windows, batch=128, request_tokens=OPENAI_REQUEST_TOKENS
    )
    assert len(chunks) > 1
    for chunk in chunks:
        assert 1 <= len(chunk) <= 128
        assert sum(len(window) for window in chunk) <= OPENAI_REQUEST_TOKENS


def test_missing_tiktoken_is_setup_error(monkeypatch):
    monkeypatch.delitem(sys.modules, "tiktoken", raising=False)
    real_import = builtins.__import__

    def blocked(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "tiktoken" or name.startswith("tiktoken."):
            raise ImportError("No module named 'tiktoken'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked)
    with pytest.raises(EmbeddingSetupError, match=r"agentconnect\[openai\]"):
        OpenAIEmbedder()
    with pytest.raises(EmbeddingSetupError, match=r"agentconnect\[openai\]"):
        Team("content-squad", embeddings="openai")


def test_missing_litellm_is_setup_error(monkeypatch):
    pytest.importorskip("tiktoken")
    for key in list(sys.modules):
        if key == "litellm" or key.startswith("litellm."):
            monkeypatch.delitem(sys.modules, key, raising=False)
    real_import = builtins.__import__

    def blocked(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "litellm" or name.startswith("litellm."):
            raise ImportError("No module named 'litellm'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked)
    with pytest.raises(EmbeddingSetupError, match=r"agentconnect\[aiagent,openai\]"):
        LiteLLMEmbedder("azure/text-embedding-3-small")
    with pytest.raises(EmbeddingSetupError, match=r"agentconnect\[aiagent,openai\]"):
        Team("content-squad", embeddings="litellm:azure/text-embedding-3-small")


def test_litellm_cohere_is_setup_error(monkeypatch):
    pytest.importorskip("tiktoken")
    monkeypatch.setattr(
        "agentconnect.team.directory.tokens.litellm_embedding_info",
        lambda model: {
            "mode": "embedding",
            "litellm_provider": "cohere",
            "max_input_tokens": 512,
        },
    )
    with pytest.raises(EmbeddingSetupError, match="cohere"):
        LiteLLMEmbedder("embed-english-v3.0")
    with pytest.raises(EmbeddingSetupError, match="cohere"):
        Team("content-squad", embeddings="litellm:embed-english-v3.0")


def test_litellm_azure_uses_model_metadata(monkeypatch):
    pytest.importorskip("tiktoken")
    monkeypatch.setattr(
        "agentconnect.team.directory.tokens.litellm_embedding_info",
        lambda model: {
            "mode": "embedding",
            "litellm_provider": "azure",
            "max_input_tokens": 8191,
            "max_tokens": 8191,
        },
    )
    embedder = LiteLLMEmbedder("azure/text-embedding-3-small")
    assert embedder.input_token_limit == 8191
    assert embedder.request_token_limit == OPENAI_REQUEST_TOKENS
    assert embedder.name == "litellm:azure/text-embedding-3-small"


def test_litellm_live_metadata_matches_support_decision():
    pytest.importorskip("litellm")
    from litellm.utils import _select_tokenizer, get_model_info

    azure = dict(get_model_info("azure/text-embedding-3-small"))
    assert azure["mode"] == "embedding"
    assert azure["litellm_provider"] == "azure"
    assert int(azure["max_input_tokens"]) == 8191
    cohere = dict(get_model_info("embed-english-v3.0"))
    assert cohere["litellm_provider"] == "cohere"
    tokenizer = _select_tokenizer("embed-english-v3.0")
    assert tokenizer["type"] == "openai_tokenizer"
