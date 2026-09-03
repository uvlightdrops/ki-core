"""Unified configuration management for ki ecosystem.

Uses schema-based config generation and yaml-cfg-wizard ConfigResolver
for layered config resolution. No code-based fallbacks - all defaults come from schema.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

from dotenv import find_dotenv, load_dotenv
from yaml_cfg_wizard import ConfigResolver


load_dotenv(find_dotenv())


def _find_yaml_config_path(path: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """Find a YAML config file in common locations."""
    if path is not None:
        candidate = Path(path)
        if candidate.exists():
            return candidate

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


def _schema_file() -> Path:
    """Get path to ki-core base schema."""
    return Path(__file__).resolve().parents[2] / "schema" / "config.schema.yaml"


def _get_merged_schemas() -> list[Path]:
    """Get list of schemas to merge (base + app-specific)."""
    schemas = [_schema_file()]
    
    # Try to find app-specific schemas in parent directories
    # This allows kicli-code-assist to provide its own schema
    current = Path.cwd()
    for _ in range(5):  # Limit depth to 5 levels
        candidate = current / "schema" / "kicli.schema.yaml"
        if candidate.exists():
            schemas.append(candidate)
            break
        current = current.parent
    
    return schemas


def _resolve_config(path: Optional[Union[str, Path]] = None) -> dict[str, Any]:
    """Resolve complete config from all sources using ConfigResolver."""
    config_path = _find_yaml_config_path(path)
    creds_path = _find_creds_yaml_path(path)

    config_dir = config_path.resolve().parent if config_path else Path.cwd()
    layered_config_dir = config_dir / "config"

    # Get all schemas for validation
    schemas = _get_merged_schemas()

    resolver = ConfigResolver(
        defaults=[config_path] if config_path else [],
        defaults_dir=layered_config_dir / "defaults" if (layered_config_dir / "defaults").exists() else None,
        profiles_dir=layered_config_dir / "profiles" if (layered_config_dir / "profiles").exists() else None,
        stages_dir=layered_config_dir / "stages" if (layered_config_dir / "stages").exists() else None,
        runtime_file=(layered_config_dir / "runtime" / "runtime.yaml")
        if (layered_config_dir / "runtime" / "runtime.yaml").exists()
        else None,
        schema_file=schemas[0] if schemas else None,  # Use merged schema for validation
        env_prefix="KI_CFG_",
    )

    payload = resolver.resolve()
    if not isinstance(payload, dict):
        return {}

    # Merge in creds if available (separate for security)
    if creds_path:
        creds_resolver = ConfigResolver(
            defaults=[creds_path],
            schema_file=schemas[0] if schemas else None,
        )
        creds_payload = creds_resolver.resolve()
        if isinstance(creds_payload, dict):
            # Deep merge creds into payload
            from yaml_cfg_wizard import deep_merge

            payload = deep_merge(payload, creds_payload)

    return payload


def _section(payload: dict[str, Any], *path: str) -> dict[str, Any]:
    """Get a nested section from config dict."""
    current: Any = payload
    for part in path:
        if not isinstance(current, dict):
            return {}
        current = current.get(part)
    return current if isinstance(current, dict) else {}


def _value(payload: dict[str, Any], *path: str) -> Any:
    """Get a nested value from config dict."""
    current: Any = payload
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


@dataclass
class Config:
    """Unified config object populated from YAML + env.
    
    All defaults come from the merged schema, not code.
    """

    # LLM Providers
    ki_base_url: str = ""
    ki_api_key: str = ""
    ki_model: str = "google/gemma-4-26B-A4B-it"
    ki_endpoint: Optional[str] = None

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    openai_api_key: str = ""
    openai_model: str = "gpt-4"
    openai_base_url: str = "https://api.openai.com/v1"

    # Knowledge
    knowledge_data_root: str = ""
    knowledge_cache_db: Optional[str] = None
    knowledge_graph_db: Optional[str] = None
    knowledge_embed_model: str = "nomic-embed-text"

    # InfoSite
    infosite_enabled: bool = False
    infosite_title: str = ""
    infosite_output_base_dir: str = ""
    infosite_domain: str = "default"

    # Jira
    jira_url: Optional[str] = None
    jira_username: Optional[str] = None
    jira_api_token: Optional[str] = None

    # HTTP
    request_timeout: int = 30
    http_verify_ssl: bool = True

    # Storage
    kicli_cache_dir: str = ""
    kicli_session_dir: str = ""
    kicli_chat_history_dir: str = ""
    kicli_allowed_base_path: str = ""

    # Context (apps.kicli.context)
    context_max_files: int = 10
    context_max_size_mb: int = 5
    context_relevance_threshold: float = 0.15
    context_cache_enabled: bool = True
    context_cache_ttl_hours: int = 24
    context_cache_max_size_mb: int = 50
    context_ignore_patterns: str = "__pycache__,*.pyc,node_modules,.git,.env"

    # Diff (apps.kicli.diff)
    diff_context_lines: int = 3
    diff_format: str = "unified"
    diff_highlight_syntax: bool = True
    diff_auto_apply_threshold: float = 0.8
    diff_max_file_size_kb: int = 100

    @classmethod
    def from_yaml(cls, path: Optional[Union[str, Path]] = None) -> "Config":
        """Load config from YAML file and environment variables.

        Resolution order (highest to lowest priority):
        1. Environment variables (KI_CFG_* prefix)
        2. Runtime files (config/runtime/runtime.yaml)
        3. Stages (config/stages/*.yaml)
        4. Profiles (config/profiles/*.yaml)
        5. Defaults (config/defaults/*.yaml)
        6. Main config (ki.yaml)
        7. Dataclass defaults
        """
        payload = _resolve_config(path)

        # Navigate through the resolved config
        llm_cfg = _section(payload, "llm")
        providers_cfg = _section(llm_cfg, "providers")
        ki_cfg = _section(providers_cfg, "ki")
        openai_cfg = _section(providers_cfg, "openai")
        ollama_cfg = _section(providers_cfg, "ollama")
        knowledge_cfg = _section(payload, "knowledge")
        infosite_cfg = _section(payload, "infosite")
        jira_cfg = _section(payload, "jira")
        http_cfg = _section(payload, "http")
        storage_cfg = _section(payload, "storage")
        apps_kicli_cfg = _section(payload, "apps", "kicli")
        context_cfg = _section(apps_kicli_cfg, "context")
        diff_cfg = _section(apps_kicli_cfg, "diff")

        # Handle credentials section
        creds_cfg = _section(payload, "creds")
        creds_ki_cfg = _section(_section(payload, "llm", "providers"), "ki")
        creds_openai_cfg = _section(_section(payload, "llm", "providers"), "openai")

        # Extract values from resolved config
        # Use get() with None default - schema ensures type correctness
        return cls(
            ki_base_url=creds_ki_cfg.get("base_url") or ki_cfg.get("base_url") or "",
            ki_api_key=creds_ki_cfg.get("api_key") or ki_cfg.get("api_key") or "",
            ki_model=ki_cfg.get("model") or "google/gemma-4-26B-A4B-it",
            ki_endpoint=ki_cfg.get("endpoint"),
            ollama_base_url=ollama_cfg.get("base_url") or "http://localhost:11434",
            ollama_model=ollama_cfg.get("model") or "llama3.2",
            openai_api_key=creds_openai_cfg.get("api_key") or openai_cfg.get("api_key") or "",
            openai_model=openai_cfg.get("model") or "gpt-4",
            openai_base_url=openai_cfg.get("base_url") or "https://api.openai.com/v1",
            knowledge_data_root=knowledge_cfg.get("data_root") or "",
            knowledge_cache_db=knowledge_cfg.get("cache_db"),
            knowledge_graph_db=knowledge_cfg.get("graph_db"),
            knowledge_embed_model=knowledge_cfg.get("embed_model") or "nomic-embed-text",
            infosite_enabled=bool(infosite_cfg.get("enabled", False)),
            infosite_title=infosite_cfg.get("title") or "",
            infosite_output_base_dir=infosite_cfg.get("output_base_dir") or "",
            infosite_domain=infosite_cfg.get("domain") or "default",
            jira_url=jira_cfg.get("url"),
            jira_username=jira_cfg.get("username"),
            jira_api_token=jira_cfg.get("api_token"),
            request_timeout=int(http_cfg.get("request_timeout", 30) or 30),
            http_verify_ssl=bool(http_cfg.get("verify_ssl", True)),
            kicli_cache_dir=storage_cfg.get("cache_dir") or "",
            kicli_session_dir=storage_cfg.get("session_dir") or "",
            kicli_chat_history_dir=apps_kicli_cfg.get("prompt_history_dir")
            or storage_cfg.get("history_dir")
            or "",
            kicli_allowed_base_path=apps_kicli_cfg.get("workspace_root") or "",
            context_max_files=int(context_cfg.get("max_files", 10) or 10),
            context_max_size_mb=int(context_cfg.get("max_size_mb", 5) or 5),
            context_relevance_threshold=float(context_cfg.get("relevance_threshold", 0.15) or 0.15),
            context_cache_enabled=bool(context_cfg.get("cache_enabled", True)),
            context_cache_ttl_hours=int(context_cfg.get("cache_ttl_hours", 24) or 24),
            context_cache_max_size_mb=int(context_cfg.get("cache_max_size_mb", 50) or 50),
            context_ignore_patterns=context_cfg.get("ignore_patterns")
            or "__pycache__,*.pyc,node_modules,.git,.env",
            diff_context_lines=int(diff_cfg.get("context_lines", 3) or 3),
            diff_format=diff_cfg.get("format") or "unified",
            diff_highlight_syntax=bool(diff_cfg.get("highlight_syntax", True)),
            diff_auto_apply_threshold=float(diff_cfg.get("auto_apply_threshold", 0.8) or 0.8),
            diff_max_file_size_kb=int(diff_cfg.get("max_file_size_kb", 100) or 100),
        )

    @classmethod
    def from_env(cls) -> "Config":
        """Load config from environment variables (KI_CFG_* prefix) only."""
        return cls.from_yaml(None)
