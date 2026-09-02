"""Test Ollama provider."""

import pytest
from unittest.mock import Mock, patch
from kicli.providers.ollama import OllamaProvider


class TestOllamaProvider:
    """Test Ollama provider implementation."""
    
    def test_provider_initialization(self):
        """Test creating Ollama provider."""
        provider = OllamaProvider(
            base_url="http://localhost:11434",
            model="mistral"
        )
        
        assert provider.base_url == "http://localhost:11434"
        assert provider.model == "mistral"
    
    def test_provider_defaults(self):
        """Test provider defaults."""
        provider = OllamaProvider()
        
        assert provider.base_url == "http://localhost:11434"
        assert provider.model == "mistral"
    
    @patch("kicli.providers.ollama.OpenAI")
    def test_chat(self, mock_openai_class):
        """Test chat completion."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        
        # Mock response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Hello from Ollama!"))]
        mock_client.chat.completions.create.return_value = mock_response
        
        provider = OllamaProvider()
        messages = [{"role": "user", "content": "Hi"}]
        
        response = provider.chat(messages)
        
        assert response == "Hello from Ollama!"
        mock_client.chat.completions.create.assert_called_once()
    
    @patch("kicli.providers.ollama.OpenAI")
    def test_chat_stream(self, mock_openai_class):
        """Test streaming chat."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        
        # Mock stream chunks
        chunk1 = Mock(choices=[Mock(delta=Mock(content="Hello"))])
        chunk2 = Mock(choices=[Mock(delta=Mock(content=" from"))])
        chunk3 = Mock(choices=[Mock(delta=Mock(content=" Ollama"))])
        
        mock_client.chat.completions.create.return_value = [chunk1, chunk2, chunk3]
        
        provider = OllamaProvider()
        messages = [{"role": "user", "content": "Hi"}]
        
        chunks = list(provider.chat_stream(messages))
        
        assert chunks == ["Hello", " from", " Ollama"]
    
    @patch("kicli.providers.ollama.OpenAI")
    def test_chat_error_handling(self, mock_openai_class):
        """Test error handling in chat."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("Connection refused")
        
        provider = OllamaProvider(base_url="http://localhost:11434", model="mistral")
        messages = [{"role": "user", "content": "Hi"}]
        
        with pytest.raises(RuntimeError) as exc_info:
            provider.chat(messages)
        
        assert "Ollama request failed" in str(exc_info.value)
        assert "localhost:11434" in str(exc_info.value)
        assert "mistral" in str(exc_info.value)
    
    @patch("kicli.providers.ollama.requests.get")
    def test_get_available_models(self, mock_get):
        """Test fetching available models."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [
                {"name": "mistral:latest"},
                {"name": "llama2:latest"},
                {"name": "neural-chat:latest"}
            ]
        }
        mock_get.return_value = mock_response
        
        models = OllamaProvider.get_available_models()
        
        assert len(models) == 3
        assert "mistral:latest" in models
        assert "llama2:latest" in models
    
    @patch("kicli.providers.ollama.requests.get")
    def test_get_available_models_error(self, mock_get):
        """Test error handling when getting models."""
        mock_get.side_effect = Exception("Connection refused")
        
        with pytest.raises(RuntimeError) as exc_info:
            OllamaProvider.get_available_models("http://localhost:11434")
        
        assert "Failed to get Ollama models" in str(exc_info.value)
