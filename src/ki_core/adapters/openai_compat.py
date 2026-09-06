"""OpenAI-compatible provider (supports OpenAI, Azure, local servers)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Optional

import requests

from ki_core.core.client import AIClient
from ki_core.core.errors import AuthError, ProviderError, TimeoutError, ValidationError
from ki_core.core.models import ChatRequest, ChatResponse, Message, Role, StreamEvent, StreamEventType


class OpenAICompatibleClient(AIClient):
    """Client for OpenAI-compatible APIs (OpenAI, Azure, vLLM, etc.)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: Optional[str] = None,
        timeout: int = 30,
        verify: bool | str = True,
    ) -> None:
        """
        Initialize OpenAI-compatible client.
        
        Args:
            base_url: API endpoint base URL (e.g., https://api.openai.com/v1)
            api_key: Authentication token
            model: Default model name
            timeout: Request timeout in seconds
            verify: TLS verification - True (default, system/certifi CA bundle),
                False (disable, insecure), or a path to a custom CA bundle/cert
                file (e.g. for self-signed/internal CAs). Maps to the
                `http.verify_ssl` config field.
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = model
        self.timeout = timeout
        self.verify = verify

        if not api_key:
            raise AuthError("api_key is required")

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat request."""
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
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
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
            raise TimeoutError(f"Request timed out: {e}")
        except requests.exceptions.RequestException as e:
            raise ProviderError(f"Provider request failed: {e}")

        data = response.json()

        if "error" in data:
            raise ProviderError(f"Provider error: {data['error']}")

        choice = data["choices"][0]
        content = choice["message"]["content"]

        return ChatResponse(
            message=Message(role=Role.ASSISTANT, content=content),
            provider="openai-compatible",
            model=data["model"],
        )

    def chat_stream(self, request: ChatRequest) -> Iterator[StreamEvent]:
        """Stream a chat request."""
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
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
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
            raise TimeoutError(f"Request timed out: {e}")
        except requests.exceptions.RequestException as e:
            raise ProviderError(f"Provider request failed: {e}")

        for line in response.iter_lines():
            if not line:
                continue

            line = line.decode("utf-8") if isinstance(line, bytes) else line

            if line.startswith("data: "):
                data_str = line[6:]  # Remove "data: " prefix

                if data_str == "[DONE]":
                    yield StreamEvent(type=StreamEventType.DONE)
                    break

                try:
                    import json

                    data = json.loads(data_str)
                    delta = data["choices"][0]["delta"]

                    if "content" in delta:
                        yield StreamEvent(type=StreamEventType.TOKEN, text=delta["content"])
                except Exception:
                    continue
