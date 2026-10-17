"""Encryption utilities for sensitive data at rest.

Uses Fernet (symmetric encryption) for chat history, credentials, and other
sensitive data that needs to persist encrypted on disk.
"""

import os
import json
from typing import Any, Optional
from datetime import datetime
from pathlib import Path
from base64 import b64encode, b64decode
import logging

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

logger = logging.getLogger(__name__)


class EncryptionManager:
    """Manage Fernet encryption for sensitive data."""

    def __init__(self, master_key: Optional[str] = None):
        """Initialize encryption manager.
        
        Args:
            master_key: Master encryption key (if None, generated from environment)
        """
        self.master_key = master_key or self._get_or_create_master_key()
        self.cipher = Fernet(self.master_key)

    @staticmethod
    def _get_or_create_master_key() -> bytes:
        """Get or create master encryption key from environment/disk.
        
        Priority:
        1. KI_MASTER_KEY environment variable
        2. ~/.ki/master.key file
        3. Generate new key and save to ~/.ki/master.key
        
        Returns:
            Master key as bytes
        """
        # Try environment variable
        env_key = os.environ.get("KI_MASTER_KEY")
        if env_key:
            try:
                return b64decode(env_key)
            except Exception:
                logger.warning("Invalid KI_MASTER_KEY in environment, generating new")

        # Try disk file
        key_file = Path.home() / ".ki" / "master.key"
        if key_file.exists():
            try:
                with open(key_file, "rb") as f:
                    key = f.read()
                    if len(key) == 44:  # Fernet key length
                        return key
            except Exception as e:
                logger.warning(f"Failed to read master key from {key_file}: {e}")

        # Generate new key
        logger.info("Generating new master encryption key...")
        new_key = Fernet.generate_key()
        
        # Save to disk
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.chmod(0o600)  # Read-only for owner
        with open(key_file, "wb") as f:
            f.write(new_key)
        logger.info(f"✓ Master key saved to {key_file}")
        
        return new_key

    def encrypt_text(self, plaintext: str) -> str:
        """Encrypt text to ciphertext.
        
        Args:
            plaintext: Text to encrypt
            
        Returns:
            Base64-encoded ciphertext
        """
        if not plaintext:
            return ""
        
        ciphertext = self.cipher.encrypt(plaintext.encode())
        return b64encode(ciphertext).decode()

    def decrypt_text(self, ciphertext_b64: str) -> str:
        """Decrypt ciphertext to plaintext.
        
        Args:
            ciphertext_b64: Base64-encoded ciphertext
            
        Returns:
            Decrypted plaintext
            
        Raises:
            cryptography.fernet.InvalidToken: If decryption fails
        """
        if not ciphertext_b64:
            return ""
        
        try:
            ciphertext = b64decode(ciphertext_b64)
            plaintext = self.cipher.decrypt(ciphertext).decode()
            return plaintext
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise

    def encrypt_dict(self, data: dict) -> dict:
        """Encrypt dictionary values (recursively).
        
        Args:
            data: Dictionary to encrypt
            
        Returns:
            Dictionary with encrypted values (marked with __encrypted__ flag)
        """
        encrypted = {}
        
        for key, value in data.items():
            if value is None:
                encrypted[key] = None
            elif isinstance(value, str):
                encrypted[key] = {
                    "__encrypted__": True,
                    "value": self.encrypt_text(value),
                }
            elif isinstance(value, dict):
                encrypted[key] = self.encrypt_dict(value)
            elif isinstance(value, list):
                encrypted[key] = [
                    self.encrypt_text(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                encrypted[key] = value
        
        return encrypted

    def decrypt_dict(self, data: dict) -> dict:
        """Decrypt dictionary values (recursively).
        
        Args:
            data: Dictionary with encrypted values
            
        Returns:
            Dictionary with decrypted plaintext values
        """
        decrypted = {}
        
        for key, value in data.items():
            if value is None:
                decrypted[key] = None
            elif isinstance(value, dict) and value.get("__encrypted__"):
                decrypted[key] = self.decrypt_text(value["value"])
            elif isinstance(value, dict):
                decrypted[key] = self.decrypt_dict(value)
            elif isinstance(value, list):
                decrypted[key] = value
            else:
                decrypted[key] = value
        
        return decrypted

    def encrypt_json(self, data: dict) -> str:
        """Encrypt dictionary as JSON string.
        
        Args:
            data: Dictionary to encrypt
            
        Returns:
            Encrypted JSON string
        """
        json_str = json.dumps(data)
        return self.encrypt_text(json_str)

    def decrypt_json(self, ciphertext: str) -> dict:
        """Decrypt JSON string.
        
        Args:
            ciphertext: Encrypted JSON string
            
        Returns:
            Decrypted dictionary
        """
        plaintext = self.decrypt_text(ciphertext)
        return json.loads(plaintext)


class EncryptedStorage:
    """File-based encrypted storage for chat history and other data."""

    def __init__(self, storage_dir: Path, encryption_manager: Optional[EncryptionManager] = None):
        """Initialize encrypted storage.
        
        Args:
            storage_dir: Directory for encrypted files
            encryption_manager: EncryptionManager instance (creates new if None)
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.encryption = encryption_manager or EncryptionManager()

    def save_encrypted(self, filename: str, data: dict) -> Path:
        """Save encrypted data to file.
        
        Args:
            filename: Filename (without directory)
            data: Dictionary to save
            
        Returns:
            Path to saved file
        """
        file_path = self.storage_dir / filename
        
        # Add metadata
        data["__metadata__"] = {
            "encrypted_at": datetime.now().isoformat(),
            "version": 1,
        }
        
        # Encrypt and save
        encrypted_json = self.encryption.encrypt_json(data)
        
        with open(file_path, "w") as f:
            f.write(encrypted_json)
        
        logger.info(f"✓ Saved encrypted data to {file_path}")
        return file_path

    def load_encrypted(self, filename: str) -> dict:
        """Load encrypted data from file.
        
        Args:
            filename: Filename to load
            
        Returns:
            Decrypted dictionary
            
        Raises:
            FileNotFoundError: If file doesn't exist
            cryptography.fernet.InvalidToken: If decryption fails
        """
        file_path = self.storage_dir / filename
        
        if not file_path.exists():
            raise FileNotFoundError(f"Encrypted file not found: {file_path}")
        
        with open(file_path, "r") as f:
            encrypted_json = f.read()
        
        data = self.encryption.decrypt_json(encrypted_json)
        logger.info(f"✓ Loaded encrypted data from {file_path}")
        return data

    def delete_encrypted(self, filename: str) -> None:
        """Delete encrypted file.
        
        Args:
            filename: Filename to delete
        """
        file_path = self.storage_dir / filename
        if file_path.exists():
            file_path.unlink()
            logger.info(f"✓ Deleted encrypted file: {file_path}")
