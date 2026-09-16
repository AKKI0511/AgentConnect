"""Token windowing and hosted request packing."""

from __future__ import annotations

from agentconnect.team.directory.embedder import (
    FastEmbedEmbedder,
    LiteLLMEmbedder,
    OpenAIEmbedder,
)
from agentconnect.team.directory.tokens import (
    OPENAI_INPUT_TOKENS,
    OPENAI_REQUEST_TOKENS,
    hosted_token_count,
    hosted_token_windows,
    pack_token_batches,
)


def test_neural_backends_own_token_limits():
    assert OpenAIEmbedder.input_char_limit is None
    assert LiteLLMEmbedder.input_char_limit is None
    assert FastEmbedEmbedder.input_char_limit is None
    assert OpenAIEmbedder.input_token_limit == OPENAI_INPUT_TOKENS
    assert OpenAIEmbedder.request_token_limit == OPENAI_REQUEST_TOKENS


def test_hosted_windows_keep_dense_cjk_inside_input_budget():
    text = "海难救助仲裁争议处理专家。" * 800
    assert len(text) > 10000
    assert hosted_token_count(text) > OPENAI_INPUT_TOKENS
    windows = hosted_token_windows(text, OPENAI_INPUT_TOKENS)
    assert len(windows) > 1
    assert "".join(windows) == text
    for window in windows:
        assert hosted_token_count(window) <= OPENAI_INPUT_TOKENS


def test_pack_token_batches_splits_before_request_budget():
    texts = ["x"] * 50
    counts = [8000] * 50
    chunks = pack_token_batches(
        texts, counts, batch=128, request_tokens=OPENAI_REQUEST_TOKENS
    )
    assert len(chunks) > 1
    for chunk in chunks:
        assert 1 <= len(chunk) <= 128
        assert len(chunk) * 8000 <= OPENAI_REQUEST_TOKENS
