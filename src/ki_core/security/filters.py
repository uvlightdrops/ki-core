"""Sensitive data filtering to prevent secret leakage to LLM APIs.

This module detects and redacts API keys, passwords, database credentials,
and other sensitive data before sending to LLM providers.
"""

import re
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SensitiveDataFilter:
    """Filter sensitive data (secrets, credentials, PII) from text."""

    # Regex patterns for detecting secrets
    PATTERNS = {
        "api_key": {
            "pattern": r'(?:api[_-]?key|sk[_-]|rk[_-]|pk[_-])\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]+)["\']?',
            "replace": "[REDACTED-API_KEY]",
        },
        "password": {
            "pattern": r'(?:password|passwd|pwd|pass)\s*[:=]\s*["\']?([^\s"\'\n]+)["\']?',
            "replace": "[REDACTED-PASSWORD]",
        },
        "token": {
            "pattern": r'(?:token|auth_token|jwt|bearer)\s*[:=]\s*["\']?([^\s"\'\n]+)["\']?',
            "replace": "[REDACTED-TOKEN]",
        },
        "connection_string": {
            "pattern": r'(?:Server|Database|User|Password)=([^\s;]+)',
            "replace": "[REDACTED-CONNECTION_STRING]",
        },
        "private_key": {
            "pattern": r'-----BEGIN (?:RSA |DSA |EC |OpenSSH )?PRIVATE KEY',
            "replace": "[REDACTED-PRIVATE_KEY]",
        },
        "aws_secret": {
            "pattern": r'(?:aws_secret_access_key|aws_access_key_id)\s*[:=]\s*["\']?([a-zA-Z0-9/+=]+)["\']?',
            "replace": "[REDACTED-AWS_SECRET]",
        },
        "database_url": {
            "pattern": r'(?:postgres|mysql|mongodb|redis)://[^/]*:([^@]+)@',
            "replace": "://[REDACTED-CREDENTIALS]@",
        },
        "github_token": {
            "pattern": r'gh[pousr]_[A-Za-z0-9_]{36,255}',
            "replace": "[REDACTED-GITHUB_TOKEN]",
        },
        "slack_token": {
            "pattern": r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,34}',
            "replace": "[REDACTED-SLACK_TOKEN]",
        },
        "azure_key": {
            "pattern": r'[a-zA-Z0-9/+]{88}==',  # Base64 88 chars
            "replace": "[REDACTED-AZURE_KEY]",
        },
    }

    def __init__(self, aggressive: bool = False):
        """Initialize filter.
        
        Args:
            aggressive: If True, apply stricter patterns (may have more false positives)
        """
        self.aggressive = aggressive
        self.redaction_count = 0

    def filter(self, text: str) -> str:
        """Filter sensitive data from text.
        
        Args:
            text: Text to filter
            
        Returns:
            Text with secrets replaced by [REDACTED-TYPE]
        """
        if not text:
            return text

        original_text = text
        
        for secret_type, config in self.PATTERNS.items():
            pattern = config["pattern"]
            replace = config["replace"]
            
            # Count matches before replacement
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            match_count = sum(1 for _ in matches)
            
            if match_count > 0:
                self.redaction_count += match_count
                logger.info(f"Redacted {match_count} {secret_type} secret(s)")
            
            # Replace secrets
            text = re.sub(pattern, replace, text, flags=re.IGNORECASE | re.MULTILINE)

        if text != original_text:
            logger.debug(f"Total redactions: {self.redaction_count}")

        return text

    def filter_dict(self, data: dict) -> dict:
        """Filter sensitive data from dictionary values.
        
        Args:
            data: Dictionary to filter
            
        Returns:
            Dictionary with sensitive values redacted
        """
        filtered = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                filtered[key] = self.filter(value)
            elif isinstance(value, dict):
                filtered[key] = self.filter_dict(value)
            elif isinstance(value, list):
                filtered[key] = [
                    self.filter(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                filtered[key] = value
        
        return filtered

    def filter_list(self, items: list[str]) -> list[str]:
        """Filter sensitive data from list of strings.
        
        Args:
            items: List of strings to filter
            
        Returns:
            List with sensitive data redacted
        """
        return [self.filter(item) for item in items]

    def get_redaction_count(self) -> int:
        """Get count of redactions made.
        
        Returns:
            Number of secrets redacted
        """
        return self.redaction_count

    def reset_count(self) -> None:
        """Reset redaction counter."""
        self.redaction_count = 0

    @staticmethod
    def is_likely_secret(text: str) -> bool:
        """Quick check if text likely contains a secret.
        
        Args:
            text: Text to check
            
        Returns:
            True if text contains suspicious patterns
        """
        suspicious_patterns = [
            r'(?:api[_-]?key|password|token|secret)\s*[:=]',
            r'-----BEGIN.*PRIVATE KEY',
            r'gh[pousr]_[A-Za-z0-9_]{36,}',
            r'xox[baprs]-[0-9]{10,13}',
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False


class RedactionLog:
    """Track what was redacted for audit purposes."""

    def __init__(self):
        """Initialize redaction log."""
        self.redactions = []

    def log_redaction(self, secret_type: str, line_number: Optional[int] = None, file_path: Optional[str] = None) -> None:
        """Log a redaction event.
        
        Args:
            secret_type: Type of secret redacted (api_key, password, etc)
            line_number: Optional line number in source file
            file_path: Optional file path where secret was found
        """
        self.redactions.append({
            "secret_type": secret_type,
            "line": line_number,
            "file": file_path,
        })

    def get_summary(self) -> dict:
        """Get summary of redactions.
        
        Returns:
            Dict with redaction statistics
        """
        secret_types = {}
        for redaction in self.redactions:
            secret_type = redaction["secret_type"]
            secret_types[secret_type] = secret_types.get(secret_type, 0) + 1

        return {
            "total_redactions": len(self.redactions),
            "by_type": secret_types,
        }

    def clear(self) -> None:
        """Clear redaction log."""
        self.redactions = []
