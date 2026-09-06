"""Tests for the `verify` (TLS verification) wiring in the HTTP-based adapters."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from ki_core.adapters.ollama import OllamaClient
from ki_core.adapters.openai_compat import OpenAICompatibleClient
from ki_core.core.errors import ProviderError
from ki_core.core.models import ChatRequest, Message, Role


def _mock_response(json_payload):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = json_payload
    return resp


class TestOpenAICompatibleVerify:
    def test_defaults_to_verify_true(self):
        client = OpenAICompatibleClient(base_url="https://api.example.com", api_key="k")
        assert client.verify is True

    def test_accepts_custom_ca_bundle_path(self):
        client = OpenAICompatibleClient(
            base_url="https://api.example.com", api_key="k", verify="/etc/ssl/internal-ca.pem"
        )
        assert client.verify == "/etc/ssl/internal-ca.pem"

    @patch("ki_core.adapters.openai_compat.requests.post")
    def test_chat_passes_verify_through_to_requests(self, mock_post):
        mock_post.return_value = _mock_response(
            {"model": "gpt-4", "choices": [{"message": {"content": "hi"}}]}
        )
        client = OpenAICompatibleClient(
            base_url="https://api.example.com", api_key="k", verify=False
        )
        client.chat(ChatRequest(messages=[Message(role=Role.USER, content="hello")]))

        assert mock_post.call_args.kwargs["verify"] is False

    @patch("ki_core.adapters.openai_compat.requests.post")
    def test_ssl_error_raises_helpful_provider_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.SSLError("certificate verify failed")
        client = OpenAICompatibleClient(base_url="https://api.example.com", api_key="k")

        with pytest.raises(ProviderError, match="cert-diagnose"):
            client.chat(ChatRequest(messages=[Message(role=Role.USER, content="hello")]))


class TestOllamaVerify:
    def test_defaults_to_verify_true(self):
        client = OllamaClient()
        assert client.verify is True

    @patch("ki_core.adapters.ollama.requests.post")
    def test_chat_passes_verify_through_to_requests(self, mock_post):
        mock_post.return_value = _mock_response(
            {"model": "llama2", "message": {"content": "hi"}}
        )
        client = OllamaClient(base_url="https://ollama.internal", verify="/etc/ssl/internal-ca.pem")
        client.chat(ChatRequest(messages=[Message(role=Role.USER, content="hello")]))

        assert mock_post.call_args.kwargs["verify"] == "/etc/ssl/internal-ca.pem"

    @patch("ki_core.adapters.ollama.requests.post")
    def test_ssl_error_raises_helpful_provider_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.SSLError("certificate verify failed")
        client = OllamaClient(base_url="https://ollama.internal")

        with pytest.raises(ProviderError, match="cert-diagnose"):
            client.chat(ChatRequest(messages=[Message(role=Role.USER, content="hello")]))
