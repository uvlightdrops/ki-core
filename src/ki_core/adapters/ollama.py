"""Ollama provider for local LLM inference."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Optional

import requests

from ki_core.core.client import AIClient
from ki_core.core.errors import ProviderError, TimeoutError, ValidationError
from ki_core.core.models import ChatRequest, ChatResponse, Message, Role, StreamEvent, StreamEventType


class OllamaClient(AIClient):
    """Client for Ollama local LLM inference."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: Optional[str] = None,
        timeout: int = 300,
        verify: bool | str = True,
    ) -> None:
        """
        Initialize Ollama client.
        
        Args:
            base_url: Ollama server URL
            model: Default model name (e.g., "llama2", "mistral", "neural-chat")
            timeout: Request timeout in seconds (local inference can be slow)
            verify: TLS verification - True (default), False (disable), or a
                path to a custom CA bundle/cert file. Maps to the
                `http.verify_ssl` config field. Irrelevant for plain http://
                URLs (the common case for local Ollama).
        """
        self.base_url = base_url.rstrip("/")
        self.default_model = model or "llama2"
        self.timeout = timeout
        self.verify = verify

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat request to Ollama."""
        if not request.messages:
            raise ValidationError("chat request must include at least one message")

        messages = [{"role": msg.role.value, "content": msg.content} for msg in request.messages]

        payload = {
            "model": request.model or self.default_model,
            "messages": messages,
            "stream": False,
        }

        if request.temperature is not None:
            payload["temperature"] = request.temperature

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
                verify=self.verify,
            )
            response.raise_for_status()
        except requests.exceptions.SSLError as e:
            raise ProviderError(
                f"TLS certificate verification failed for {self.base_url}: {e}. "
                f"Run `ki-chat cert-diagnose {self.base_url}` for details."
            )
        except requests.exceptions.Timeout as e:
            raise TimeoutError(f"Ollama request timed out: {e}")
        except requests.exceptions.RequestException as e:
            raise ProviderError(f"Ollama provider request failed: {e}")

        data = response.json()

        return ChatResponse(
            message=Message(role=Role.ASSISTANT, content=data["message"]["content"]),
            provider="ollama",
            model=data["model"],
        )

    def chat_stream(self, request: ChatRequest) -> Iterator[StreamEvent]:
        """Stream a chat request from Ollama."""
        if not request.messages:
            raise ValidationError("chat request must include at least one message")

        messages = [{"role": msg.role.value, "content": msg.content} for msg in request.messages]

        payload = {
            "model": request.model or self.default_model,
            "messages": messages,
            "stream": True,
        }

        if request.temperature is not None:
            payload["temperature"] = request.temperature

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
                verify=self.verify,
                stream=True,
            )
            response.raise_for_status()
        except requests.exceptions.SSLError as e:
            raise ProviderError(
                f"TLS certificate verification failed for {self.base_url}: {e}. "
                f"Run `ki-chat cert-diagnose {self.base_url}` for details."
            )
        except requests.exceptions.Timeout as e:
            raise TimeoutError(f"Ollama request timed out: {e}")
        except requests.exceptions.RequestException as e:
            raise ProviderError(f"Ollama provider request failed: {e}")

        for line in response.iter_lines():
            if not line:
                continue

            try:
                import json

                data = json.loads(line)

                if "message" in data and "content" in data["message"]:
                    text = data["message"]["content"]
                    if text:
                        yield StreamEvent(type=StreamEventType.TOKEN, text=text)

                if data.get("done", False):
                    yield StreamEvent(type=StreamEventType.DONE)
                    break
            except Exception:
                continue

    @staticmethod
    def get_available_models(base_url: str = "http://localhost:11434") -> list[str]:
        """Get list of available models from Ollama."""
        try:
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            raise ProviderError(f"Failed to fetch Ollama models: {e}")
