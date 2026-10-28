"""Shared configuration-driven provider access; no live requests."""

from copy import deepcopy

import pytest
import requests

from ki_core import ConfigManager, create_chat_client, get_chat_models, get_chat_settings
from ki_core.adapters.mock import MockAIClient
from ki_core.adapters.ollama import OllamaClient
from ki_core.adapters.openai_compat import OpenAICompatibleClient
from ki_core.core.errors import ProviderError, ValidationError


@pytest.fixture
def config():
    return {
        "llm": {
            "provider": "ki",
            "providers": {
                "ki": {"base_url": "https://ki.invalid/v1", "api_key": "test-key", "model": "ki-model"},
                "openai": {"base_url": "https://openai.invalid/v1", "api_key": "test-key", "model": "openai-model"},
                "ollama": {"base_url": "http://ollama.invalid:11434", "model": "local-model"},
            },
        },
        "http": {"request_timeout": 90, "verify_ssl": False},
    }


def test_config_manager_accepts_isolated_snapshot_without_loading_files(config, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Resolved snapshots must not reload files")

    monkeypatch.setattr("ki_core.config.load_config", forbidden)
    manager = ConfigManager(config=config)
    config["llm"]["provider"] = "mock"
    assert manager.get_llm_provider() == "ki"
    assert get_chat_settings(manager)["provider"] == "ki"
    assert isinstance(create_chat_client(manager), OpenAICompatibleClient)


@pytest.mark.parametrize("provider,client_type", [
    ("ki", OpenAICompatibleClient), ("openai", OpenAICompatibleClient),
    ("ollama", OllamaClient), ("mock", MockAIClient),
])
def test_factory_selects_provider_and_propagates_options(config, provider, client_type):
    original = deepcopy(config)
    client = create_chat_client(config, provider=provider, model="override", ollama_base_url="http://other:11434")
    assert isinstance(client, client_type)
    if provider != "mock":
        assert client.default_model == "override"
        assert client.timeout == 90 and client.verify is False
        assert client.base_url == (
            "http://other:11434" if provider == "ollama" else config["llm"]["providers"][provider]["base_url"]
        )
    assert config == original


def test_auto_display_does_not_detect_or_reload(config, monkeypatch):
    config["llm"]["provider"] = "auto"

    def forbidden(*args, **kwargs):
        raise AssertionError("Display must not probe providers")

    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    monkeypatch.setattr("ki_core.config.load_config", forbidden)
    assert get_chat_settings(config) == {"provider": "auto", "base_url": "", "model": ""}
    assert get_chat_models(get_chat_settings(config)) == []
    assert isinstance(create_chat_client(config), OpenAICompatibleClient)


def test_explicit_auto_override_uses_core_detection_without_mutating_config(config):
    original = deepcopy(config)
    assert get_chat_settings(config, provider="auto", resolve_auto=True)["provider"] == "openai"
    assert config == original


def test_auto_uses_snapshot_instead_of_other_host_config(config, monkeypatch):
    config["llm"]["provider"] = "auto"
    config["llm"]["providers"]["openai"]["api_key"] = ""
    config["llm"]["providers"]["ki"]["api_key"] = ""
    calls = []

    def head(url, **kwargs):
        calls.append(url)

    monkeypatch.setattr(requests, "head", head)
    assert isinstance(create_chat_client(config), OllamaClient)
    assert calls == ["http://ollama.invalid:11434"]


@pytest.mark.parametrize("provider", ["ki", "openai", "ollama"])
@pytest.mark.parametrize("field", ["base_url", "model"])
def test_missing_endpoint_and_model_are_errors(config, provider, field):
    config["llm"]["providers"][provider][field] = ""
    with pytest.raises(ValidationError, match=f"llm.providers.{provider}.{field}"):
        create_chat_client(config, provider=provider)


@pytest.mark.parametrize("key", ["", "${UNRESOLVED_KEY}"])
def test_missing_or_placeholder_credentials_are_errors(config, key):
    config["llm"]["providers"]["ki"]["api_key"] = key
    with pytest.raises(ValidationError, match="llm.providers.ki.api_key"):
        create_chat_client(config)


@pytest.mark.parametrize("provider", ["unknown", "", 42])
def test_invalid_provider_is_rejected(config, provider):
    config["llm"]["provider"] = provider
    with pytest.raises(ValidationError, match="llm.provider"):
        create_chat_client(config)


def test_model_discovery_delegates_to_adapter_and_propagates_errors(config, monkeypatch):
    def models(url):
        assert url == "http://ollama.invalid:11434"
        return ["installed-model"]

    monkeypatch.setattr(OllamaClient, "get_available_models", models)
    assert get_chat_models(get_chat_settings(config, provider="ollama")) == ["installed-model"]
    assert get_chat_models(get_chat_settings(config)) == ["ki-model"]

    def fail(url):
        raise ProviderError("offline")

    monkeypatch.setattr(OllamaClient, "get_available_models", fail)
    with pytest.raises(ProviderError, match="offline"):
        get_chat_models(get_chat_settings(config, provider="ollama"))
