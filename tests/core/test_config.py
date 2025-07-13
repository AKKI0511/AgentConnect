"""
Tests for configuration environment variable handling.

This module tests that all environment variables in config.py work as expected.
"""

import os
import pytest
from agentconnect.core.config import (
    VectorSearchSettings,
    RegistryAPISettings,
    LoggingSettings,
    RegistrySettings,
)


class TestVectorSearchSettings:
    """Test VectorSearchSettings environment variables."""

    def test_defaults(self):
        """Test default values without environment variables."""
        settings = VectorSearchSettings()
        assert settings.model_name == "sentence-transformers/all-mpnet-base-v2"
        assert settings.cache_folder == "./.cache/huggingface/embeddings"
        assert settings.vector_store_path == "./.cache/vector_stores"
        assert settings.in_memory is True

    def test_env_overrides(self, monkeypatch):
        """Test environment variable overrides."""
        monkeypatch.setenv("AGENTCONNECT_REGISTRY_model_name", "custom-model")
        monkeypatch.setenv("AGENTCONNECT_REGISTRY_cache_folder", "/custom/cache")
        monkeypatch.setenv("AGENTCONNECT_REGISTRY_vector_store_path", "/custom/store")
        monkeypatch.setenv("AGENTCONNECT_REGISTRY_in_memory", "false")

        settings = VectorSearchSettings()
        assert settings.model_name == "custom-model"
        assert settings.cache_folder == "/custom/cache"
        assert settings.vector_store_path == "/custom/store"
        assert settings.in_memory is False


class TestRegistryAPISettings:
    """Test RegistryAPISettings environment variables."""

    def test_defaults(self):
        """Test default values without environment variables."""
        settings = RegistryAPISettings()
        assert settings.host == "localhost"
        assert settings.port == 8000
        assert settings.debug is False
        assert settings.allowed_origins == [
            "http://localhost:5173",
            "http://localhost:3000",
        ]

    def test_env_overrides(self, monkeypatch):
        """Test environment variable overrides."""
        monkeypatch.setenv("AGENTCONNECT_REGISTRY_API_host", "0.0.0.0")
        monkeypatch.setenv("AGENTCONNECT_REGISTRY_API_port", "8080")
        monkeypatch.setenv("AGENTCONNECT_REGISTRY_API_debug", "true")
        monkeypatch.setenv(
            "AGENTCONNECT_REGISTRY_API_allowed_origins",
            '["http://example.com","http://test.com"]',
        )

        settings = RegistryAPISettings()
        assert settings.host == "0.0.0.0"
        assert settings.port == 8080
        assert settings.debug is True
        assert settings.allowed_origins == ["http://example.com", "http://test.com"]

    def test_allowed_origins_parsing(self, monkeypatch):
        """Test allowed_origins JSON array parsing."""
        monkeypatch.setenv(
            "AGENTCONNECT_REGISTRY_API_allowed_origins",
            '["http://a.com", "http://b.com", "http://c.com"]',
        )

        settings = RegistryAPISettings()
        assert settings.allowed_origins == [
            "http://a.com",
            "http://b.com",
            "http://c.com",
        ]


class TestLoggingSettings:
    """Test LoggingSettings environment variables."""

    def test_defaults(self):
        """Test default values without environment variables."""
        settings = LoggingSettings()
        assert settings.level == "INFO"
        assert settings.format == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    def test_env_overrides(self, monkeypatch):
        """Test environment variable overrides."""
        monkeypatch.setenv("AGENTCONNECT_level", "DEBUG")
        monkeypatch.setenv("AGENTCONNECT_format", "%(levelname)s: %(message)s")

        settings = LoggingSettings()
        assert settings.level == "DEBUG"
        assert settings.format == "%(levelname)s: %(message)s"

    def test_invalid_log_level(self, monkeypatch):
        """Test invalid log level defaults to INFO."""
        monkeypatch.setenv("AGENTCONNECT_level", "INVALID")

        settings = LoggingSettings()
        assert settings.level == "INFO"


class TestRegistrySettings:
    """Test RegistrySettings integration."""

    def test_defaults(self):
        """Test default registry settings."""
        settings = RegistrySettings()
        assert (
            settings.vector_search.model_name
            == "sentence-transformers/all-mpnet-base-v2"
        )
        assert settings.api.host == "localhost"
        assert settings.logging.level == "INFO"

    def test_get_vector_search_config(self):
        """Test vector search config dictionary."""
        settings = RegistrySettings()
        config = settings.get_vector_search_config()

        assert isinstance(config, dict)
        assert config["model_name"] == "sentence-transformers/all-mpnet-base-v2"
        assert config["cache_folder"] == "./.cache/huggingface/embeddings"
        assert config["vector_store_path"] == "./.cache/vector_stores"
        assert config["in_memory"] is True
