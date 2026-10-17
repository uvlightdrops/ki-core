"""Tests for Phase 4.2 features (encryption, response parsing, etc)."""

import pytest
import tempfile
from pathlib import Path
from cryptography.fernet import InvalidToken

from ki_core.security.encryption import EncryptionManager, EncryptedStorage
from ki_core.core.response_parser import ResponseParser, ResponsePartType


class TestEncryption:
    """Test encryption utilities."""

    def test_encrypt_decrypt_text(self):
        """Test basic text encryption/decryption."""
        manager = EncryptionManager()
        plaintext = "my-secret-api-key-12345"
        
        ciphertext = manager.encrypt_text(plaintext)
        decrypted = manager.decrypt_text(ciphertext)
        
        assert decrypted == plaintext
        assert ciphertext != plaintext  # Should be different

    def test_encrypt_empty_text(self):
        """Test encrypting empty string."""
        manager = EncryptionManager()
        
        ciphertext = manager.encrypt_text("")
        assert ciphertext == ""

    def test_encrypt_dict_with_nested_values(self):
        """Test encrypting dictionary with nested structure."""
        manager = EncryptionManager()
        data = {
            "username": "admin",
            "password": "secret123",
            "settings": {
                "api_key": "sk-12345",
                "is_enabled": True,
            }
        }
        
        encrypted = manager.encrypt_dict(data)
        
        # Check encryption markers
        assert encrypted["username"]["__encrypted__"] == True
        assert encrypted["settings"]["api_key"]["__encrypted__"] == True
        assert encrypted["settings"]["is_enabled"] == True  # Non-string not encrypted

    def test_decrypt_dict(self):
        """Test decrypting dictionary."""
        manager = EncryptionManager()
        original = {
            "user": "admin",
            "pass": "secret",
        }
        
        encrypted = manager.encrypt_dict(original)
        decrypted = manager.decrypt_dict(encrypted)
        
        assert decrypted["user"] == original["user"]
        assert decrypted["pass"] == original["pass"]

    def test_encrypt_json_roundtrip(self):
        """Test JSON encryption/decryption roundtrip."""
        manager = EncryptionManager()
        data = {
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"}
            ],
            "model": "gpt-4"
        }
        
        json_encrypted = manager.encrypt_json(data)
        decrypted = manager.decrypt_json(json_encrypted)
        
        assert decrypted == data

    def test_invalid_decryption(self):
        """Test that invalid ciphertext raises error."""
        manager = EncryptionManager()
        
        with pytest.raises(InvalidToken):
            manager.decrypt_text("invalid-base64-not-real-ciphertext")


class TestEncryptedStorage:
    """Test encrypted file storage."""

    def test_save_and_load_encrypted_file(self):
        """Test saving and loading encrypted data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = EncryptedStorage(Path(tmpdir))
            
            original_data = {
                "chat_id": "session-123",
                "messages": [
                    {"role": "user", "content": "How to use Python?"},
                ]
            }
            
            # Save
            storage.save_encrypted("chat.enc", original_data)
            
            # Load
            loaded_data = storage.load_encrypted("chat.enc")
            
            assert loaded_data["chat_id"] == original_data["chat_id"]
            assert len(loaded_data["messages"]) == 1

    def test_file_with_metadata(self):
        """Test that metadata is added automatically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = EncryptedStorage(Path(tmpdir))
            data = {"test": "data"}
            
            storage.save_encrypted("test.enc", data)
            loaded = storage.load_encrypted("test.enc")
            
            assert "__metadata__" in loaded
            assert "encrypted_at" in loaded["__metadata__"]
            assert loaded["__metadata__"]["version"] == 1

    def test_load_nonexistent_file(self):
        """Test loading nonexistent file raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = EncryptedStorage(Path(tmpdir))
            
            with pytest.raises(FileNotFoundError):
                storage.load_encrypted("does_not_exist.enc")

    def test_delete_encrypted_file(self):
        """Test deleting encrypted file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = EncryptedStorage(Path(tmpdir))
            
            storage.save_encrypted("to_delete.enc", {"data": "test"})
            assert (Path(tmpdir) / "to_delete.enc").exists()
            
            storage.delete_encrypted("to_delete.enc")
            assert not (Path(tmpdir) / "to_delete.enc").exists()


class TestResponseParser:
    """Test response parsing."""

    def test_parse_text_only(self):
        """Test parsing text-only response."""
        parser = ResponseParser()
        response = "This is just plain text without any code."
        
        parts = parser.parse(response)
        
        assert len(parts) == 1
        assert parts[0].type == ResponsePartType.TEXT
        assert parts[0].content == response

    def test_parse_with_single_code_block(self):
        """Test parsing response with code block."""
        parser = ResponseParser()
        response = """Here's the solution:

```python
def hello():
    print("Hello, World!")
```

Run this function to greet."""
        
        parts = parser.parse(response)
        
        # Should have 3 parts: text, code, text
        assert len(parts) == 3
        assert parts[0].type == ResponsePartType.TEXT
        assert parts[1].type == ResponsePartType.CODE
        assert parts[1].language == "python"
        assert 'def hello()' in parts[1].content
        assert parts[2].type == ResponsePartType.TEXT

    def test_parse_shell_commands(self):
        """Test parsing shell commands."""
        parser = ResponseParser()
        response = """Install the package with:

```bash
pip install my-package
python -m my_package
```

Done!"""
        
        parts = parser.parse(response)
        
        # Should have text, shell, text
        shell_parts = parser.extract_shell_commands()
        assert len(shell_parts) == 1
        assert "pip install" in shell_parts[0].content

    def test_multiple_code_blocks(self):
        """Test parsing multiple code blocks."""
        parser = ResponseParser()
        response = """First solution:

```javascript
console.log("solution 1");
```

Second solution:

```javascript
console.log("solution 2");
```
"""
        
        parts = parser.parse(response)
        code_parts = parser.extract_code_blocks()
        
        assert len(code_parts) == 2
        assert code_parts[0].language == "javascript"
        assert code_parts[1].language == "javascript"

    def test_has_code(self):
        """Test has_code detection."""
        parser = ResponseParser()
        
        # No code
        parser.parse("Just text here")
        assert not parser.has_code()
        
        # With code
        parser.parse("```python\nprint('hi')\n```")
        assert parser.has_code()

    def test_has_shell(self):
        """Test has_shell detection."""
        parser = ResponseParser()
        
        # No shell
        parser.parse("Just text here")
        assert not parser.has_shell()
        
        # With shell
        parser.parse("```bash\nls -la\n```")
        assert parser.has_shell()

    def test_extract_text(self):
        """Test extracting all text."""
        parser = ResponseParser()
        response = """Step 1: Setup

```python
import os
```

Step 2: Done"""
        
        parts = parser.parse(response)
        text = parser.extract_text()
        
        assert "Step 1:" in text
        assert "Step 2:" in text
        assert "import os" not in text  # Code excluded


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
