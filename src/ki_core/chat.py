"""Configuration-driven chat provider access shared by KI applications."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict

from ki_core.adapters.mock import MockAIClient
from ki_core.adapters.ollama import OllamaClient
from ki_core.adapters.openai_compat import OpenAICompatibleClient
from ki_core.config import ConfigManager
from ki_core.core.client import AIClient
from ki_core.core.errors import ValidationError


class ChatSettings(TypedDict):
    provider: str
    base_url: str
    model: str


ChatConfig = ConfigManager | Mapping[str, Any] | None
CHAT_PROVIDERS = ("ki", "openai", "ollama", "mock")


def _manager(config: ChatConfig) -> ConfigManager:
    return config if isinstance(config, ConfigManager) else ConfigManager(config=config)


def get_chat_settings(
    config: ChatConfig = None, *, provider: str | None = None, resolve_auto: bool = False,
) -> ChatSettings:
    """Read provider settings without network I/O unless auto-resolution is requested.

    With ``resolve_auto=True``, ConfigManager owns provider detection. Merely
    displaying settings must not probe services. An explicit provider overrides
    ``llm.provider`` without changing the resolved configuration.
    """
    manager = _manager(config)
    payload = manager.load()
    selected = provider if provider is not None else payload.get_path("llm.provider", "auto")
    if not isinstance(selected, str):
        raise ValidationError("llm.provider must be a string")
    selected = selected.strip().lower()
    if selected == "auto":
        if not resolve_auto:
            return {"provider": "auto", "base_url": "", "model": ""}
        if provider is not None:
            # An explicit "auto" must ignore a concrete provider in the payload.
            manager = ConfigManager(config={
                **payload, "llm": {**payload.get("llm", {}), "provider": "auto"},
            })
        selected = manager.get_llm_provider()
    if selected not in CHAT_PROVIDERS:
        raise ValidationError(
            f"Unknown llm.provider '{selected}' (expected: auto, {', '.join(CHAT_PROVIDERS)})"
        )
    if selected == "mock":
        return {"provider": "mock", "base_url": "", "model": "mock-1"}
    return {
        "provider": selected,
        "base_url": payload.get_path(f"llm.providers.{selected}.base_url", "").strip(),
        "model": payload.get_path(f"llm.providers.{selected}.model", "").strip(),
    }


def create_chat_client(
    config: ChatConfig = None,
    *,
    provider: str | None = None,
    model: str | None = None,
    ollama_base_url: str | None = None,
) -> AIClient:
    """Create a sync/streaming AIClient for the selected provider.

    HTTP timeout and TLS options apply to every real provider. An endpoint
    override is restricted to Ollama; remote credentials always go to the
    configured endpoint. Explicit provider failures never trigger failover.
    The returned AIClient also provides achat()/achat_stream() thread wrappers.
    """
    manager = _manager(config)
    settings = get_chat_settings(manager, provider=provider, resolve_auto=True)
    selected = settings["provider"]
    resolved_model = (model or settings["model"]).strip()
    if selected == "mock":
        return MockAIClient(model=resolved_model or "mock-1")
    base_url = (
        (ollama_base_url if selected == "ollama" else None) or settings["base_url"]
    ).strip()
    prefix = f"llm.providers.{selected}"
    if not base_url:
        raise ValidationError(f"{prefix}.base_url is required")
    if not resolved_model:
        raise ValidationError(f"{prefix}.model is required")
    payload = manager.load()
    timeout = payload.get_path("http.request_timeout", 30)
    verify = payload.get_path("http.verify_ssl", True)
    if selected == "ollama":
        return OllamaClient(base_url=base_url, model=resolved_model, timeout=timeout, verify=verify)
    api_key = payload.get_path(f"{prefix}.api_key", "")
    if not api_key or api_key.startswith("${"):
        raise ValidationError(f"{prefix}.api_key is required and must not be an unresolved placeholder")
    return OpenAICompatibleClient(
        base_url=base_url, api_key=api_key, model=resolved_model, timeout=timeout, verify=verify,
    )


def get_chat_models(settings: ChatSettings) -> list[str]:
    """Installed Ollama models, or the configured model; provider errors propagate."""
    if settings["provider"] == "ollama":
        return OllamaClient.get_available_models(settings["base_url"])
    return [settings["model"]] if settings["model"] else []
