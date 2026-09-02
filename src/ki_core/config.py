"""Unified configuration management for ki ecosystem.

Supports YAML config files and environment variables for:
- LLM providers (OpenAI, Ollama, KI-Server)
- Knowledge base settings
- Code assistant preferences
- HTTP client settings
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

import yaml
from dotenv import find_dotenv, load_dotenv


def _find_yaml_config_path(path: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """Find a YAML config file in common locations."""
    if path is not None:
        p = Path(path)
        if p.exists():
            return p

    candidates = [
        Path("ki.yaml"),
        Path("kicli.yaml"),
        Path("config.yaml"),
        Path(".ki.yaml"),
        Path(".kicli.yaml"),
        Path("config") / "ki.yaml",
        Path("config") / "config.yaml",
        Path("config") / "dev.yaml",
        Path("config") / "prod.yaml",
        Path.home() / ".config" / "ki" / "config.yaml",
        Path.home() / ".config" / "kicli" / "config.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _find_creds_yaml_path(path: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """Find credentials file (kept separate for security)."""
    if path is not None:
        base_dir = Path(path).resolve().parent
        for candidate in [base_dir / "creds.yaml", base_dir / "config" / "creds.yaml"]:
            if candidate.exists():
                return candidate

    candidates = [
        Path("creds.yaml"),
        Path("config") / "creds.yaml",
        Path.home() / ".config" / "ki" / "creds.yaml",
        Path.home() / ".config" / "kicli" / "creds.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _coalesce(*values: Any) -> Any:
    """Return first non-None, non-empty value."""
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _read_yaml_config(path: Optional[Union[str, Path]] = None) -> dict:
    """Read a YAML config file."""
    config_path = _find_yaml_config_path(path)
    if not config_path:
        return {}
    with config_path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML config must contain a mapping at {config_path}")
    return payload


def _read_creds_config(path: Optional[Union[str, Path]] = None) -> dict:
    """Read the global credentials YAML."""
    creds_path = _find_creds_yaml_path(path)
    if not creds_path:
        return {}
    return _read_yaml_config(creds_path)


@dataclass
class Config:
    """Unified configuration for ki ecosystem."""

    # LLM Provider: Company KI Server
    ki_base_url: str = ""
    ki_api_key: str = ""
    ki_model: str = "google/gemma-4-26B-A4B-it"
    ki_endpoint: Optional[str] = None

    # LLM Provider: Ollama (local)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # LLM Provider: OpenAI (or compatible)
    openai_api_key: str = ""
    openai_model: str = "gpt-4"
    openai_base_url: str = "https://api.openai.com/v1"

    # Knowledge base settings
    knowledge_data_root: str = ""
    knowledge_cache_db: Optional[str] = None
    knowledge_graph_db: Optional[str] = None
    knowledge_embed_model: str = "nomic-embed-text"

    # JIRA (optional, for legacy integration)
    jira_url: Optional[str] = None
    jira_username: Optional[str] = None
    jira_api_token: Optional[str] = None

    # HTTP/Request settings
    request_timeout: int = 30
    http_verify_ssl: bool = True

    # KI CLI / Code Assistant settings
    kicli_cache_dir: str = ""
    kicli_session_dir: str = ""
    kicli_chat_history_dir: str = ""

    @classmethod
    def from_yaml(cls, path: Optional[Union[str, Path]] = None) -> "Config":
        """Load configuration from YAML files."""
        payload = _read_yaml_config(path)
        creds_payload = _read_creds_config(path)

        # Get config sections
        ki_cfg = payload.get("ki", {}) if isinstance(payload.get("ki"), dict) else {}
        ollama_cfg = payload.get("ollama", {}) if isinstance(payload.get("ollama"), dict) else {}
        openai_cfg = payload.get("openai", {}) if isinstance(payload.get("openai"), dict) else {}
        knowledge_cfg = (
            payload.get("knowledge", {})
            if isinstance(payload.get("knowledge"), dict)
            else {}
        )
        jira_cfg = payload.get("jira", {}) if isinstance(payload.get("jira"), dict) else {}
        http_cfg = payload.get("http", {}) if isinstance(payload.get("http"), dict) else {}
        kicli_cfg = payload.get("kicli", {}) if isinstance(payload.get("kicli"), dict) else {}

        # Get creds sections
        creds_cfg = creds_payload.get("creds", {}) if isinstance(creds_payload.get("creds"), dict) else {}
        creds_ki_cfg = creds_payload.get("ki", {}) if isinstance(creds_payload.get("ki"), dict) else {}

        # Build config
        return cls(
            # KI Server
            ki_base_url=_coalesce(
                creds_payload.get("ki", {}).get("base_url") if isinstance(creds_payload.get("ki"), dict) else None,
                creds_cfg.get("base_url"),
                creds_ki_cfg.get("base_url"),
                payload.get("ki_base_url"),
                ki_cfg.get("base_url"),
            ) or "",
            ki_api_key=_coalesce(
                creds_payload.get("ki", {}).get("api_key") if isinstance(creds_payload.get("ki"), dict) else None,
                creds_cfg.get("api_key"),
                creds_ki_cfg.get("api_key"),
                payload.get("ki_api_key"),
                ki_cfg.get("api_key"),
            ) or "",
            ki_model=_coalesce(payload.get("ki_model"), ki_cfg.get("model"))
            or "google/gemma-4-26B-A4B-it",
            ki_endpoint=_coalesce(payload.get("ki_endpoint"), ki_cfg.get("endpoint")),
            # Ollama
            ollama_base_url=_coalesce(
                payload.get("ollama_base_url"),
                ollama_cfg.get("base_url"),
                ollama_cfg.get("url"),
            )
            or "http://localhost:11434",
            ollama_model=_coalesce(payload.get("ollama_model"), ollama_cfg.get("model"))
            or "llama3.2",
            # OpenAI
            openai_api_key=_coalesce(
                creds_payload.get("openai", {}).get("api_key")
                if isinstance(creds_payload.get("openai"), dict)
                else None,
                payload.get("openai_api_key"),
                openai_cfg.get("api_key"),
            )
            or "",
            openai_model=_coalesce(payload.get("openai_model"), openai_cfg.get("model"))
            or "gpt-4",
            openai_base_url=_coalesce(
                payload.get("openai_base_url"),
                openai_cfg.get("base_url"),
            )
            or "https://api.openai.com/v1",
            # Knowledge
            knowledge_data_root=_coalesce(
                payload.get("knowledge_data_root"),
                knowledge_cfg.get("data_root"),
            )
            or "",
            knowledge_cache_db=_coalesce(payload.get("knowledge_cache_db"), knowledge_cfg.get("cache_db")),
            knowledge_graph_db=_coalesce(payload.get("knowledge_graph_db"), knowledge_cfg.get("graph_db")),
            knowledge_embed_model=_coalesce(
                payload.get("knowledge_embed_model"),
                knowledge_cfg.get("embed_model"),
            )
            or "nomic-embed-text",
            # JIRA
            jira_url=_coalesce(payload.get("jira_url"), jira_cfg.get("url"), jira_cfg.get("base_url")),
            jira_username=_coalesce(payload.get("jira_username"), jira_cfg.get("username")),
            jira_api_token=_coalesce(payload.get("jira_api_token"), jira_cfg.get("api_token"), jira_cfg.get("token")),
            # HTTP
            request_timeout=int(_coalesce(payload.get("request_timeout"), http_cfg.get("request_timeout"), 30)
                               or 30),
            http_verify_ssl=_coalesce(payload.get("http_verify_ssl"), http_cfg.get("verify_ssl"), True),
            # KI CLI / Code Assistant
            kicli_cache_dir=_coalesce(
                payload.get("kicli_cache_dir"),
                kicli_cfg.get("cache_dir"),
            ) or "",
            kicli_session_dir=_coalesce(
                payload.get("kicli_session_dir"),
                kicli_cfg.get("session_dir"),
            ) or "",
            kicli_chat_history_dir=_coalesce(
                payload.get("kicli_chat_history_dir"),
                kicli_cfg.get("chat_history_dir"),
            ) or "",
        )

    @classmethod
    def from_env(cls, config_path: Optional[Union[str, Path]] = None) -> "Config":
        """Load configuration from environment, with YAML as fallback."""
        load_dotenv(find_dotenv(usecwd=True), override=False)
        yaml_cfg = cls.from_yaml(config_path)

        return cls(
            # KI Server (env overrides YAML)
            ki_base_url=os.getenv("KI_BASE_URL", yaml_cfg.ki_base_url),
            ki_api_key=os.getenv("KI_API_KEY", yaml_cfg.ki_api_key),
            ki_model=os.getenv("KI_MODEL", yaml_cfg.ki_model),
            ki_endpoint=os.getenv("KI_ENDPOINT", yaml_cfg.ki_endpoint or ""),
            # Ollama
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", yaml_cfg.ollama_base_url),
            ollama_model=os.getenv("OLLAMA_MODEL", yaml_cfg.ollama_model),
            # OpenAI
            openai_api_key=os.getenv("OPENAI_API_KEY", yaml_cfg.openai_api_key),
            openai_model=os.getenv("OPENAI_MODEL", yaml_cfg.openai_model),
            openai_base_url=os.getenv("OPENAI_BASE_URL", yaml_cfg.openai_base_url),
            # Knowledge
            knowledge_data_root=os.getenv("KNOWLEDGE_DATA_ROOT", yaml_cfg.knowledge_data_root),
            knowledge_cache_db=os.getenv("KNOWLEDGE_CACHE_DB", yaml_cfg.knowledge_cache_db or ""),
            knowledge_graph_db=os.getenv("KNOWLEDGE_GRAPH_DB", yaml_cfg.knowledge_graph_db or ""),
            knowledge_embed_model=os.getenv("KNOWLEDGE_EMBED_MODEL", yaml_cfg.knowledge_embed_model),
            # JIRA
            jira_url=os.getenv("JIRA_URL", yaml_cfg.jira_url or ""),
            jira_username=os.getenv("JIRA_USERNAME", yaml_cfg.jira_username or ""),
            jira_api_token=os.getenv("JIRA_API_TOKEN", yaml_cfg.jira_api_token or ""),
            # HTTP
            request_timeout=int(os.getenv("KI_REQUEST_TIMEOUT", str(yaml_cfg.request_timeout))),
            http_verify_ssl=os.getenv("KI_VERIFY_SSL", str(yaml_cfg.http_verify_ssl)).lower() in ("true", "1"),
            # KI CLI / Code Assistant
            kicli_cache_dir=os.getenv("KICLI_CACHE_DIR", yaml_cfg.kicli_cache_dir),
            kicli_session_dir=os.getenv("KICLI_SESSION_DIR", yaml_cfg.kicli_session_dir),
            kicli_chat_history_dir=os.getenv("KICLI_CHAT_HISTORY_DIR", yaml_cfg.kicli_chat_history_dir),
        )

    def validate(self) -> None:
        """Validate required configuration (depends on use case)."""
        pass  # Validation depends on which provider is being used
