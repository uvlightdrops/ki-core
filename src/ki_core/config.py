"""Unified configuration management for ki ecosystem."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

from dotenv import find_dotenv, load_dotenv
from yaml_cfg_wizard import ConfigResolver


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


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _section(payload: dict[str, Any], *path: str) -> dict[str, Any]:
    current: Any = payload
    for part in path:
        if not isinstance(current, dict):
            return {}
        current = current.get(part)
    return current if isinstance(current, dict) else {}


def _value(payload: dict[str, Any], *path: str) -> Any:
    current: Any = payload
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _int_value(*values: Any, default: int) -> int:
    return int(_coalesce(*values, default) or default)


def _float_value(*values: Any, default: float) -> float:
    return float(_coalesce(*values, default) or default)


def _bool_value(*values: Any, default: bool) -> bool:
    value = _coalesce(*values, default)
    return default if value is None else bool(value)


def _schema_file() -> Path:
    return Path(__file__).resolve().parents[2] / "schema" / "config.schema.yaml"


def _read_yaml_config(path: Optional[Union[str, Path]] = None) -> dict[str, Any]:
    config_path = _find_yaml_config_path(path)
    if not config_path:
        return {}

    config_dir = config_path.resolve().parent
    layered_config_dir = config_dir / "config"
    runtime_file = layered_config_dir / "runtime" / "runtime.yaml"

    resolver = ConfigResolver(
        defaults=[config_path],
        defaults_dir=layered_config_dir / "defaults" if (layered_config_dir / "defaults").exists() else None,
        profiles_dir=layered_config_dir / "profiles" if (layered_config_dir / "profiles").exists() else None,
        stages_dir=layered_config_dir / "stages" if (layered_config_dir / "stages").exists() else None,
        runtime_file=runtime_file if runtime_file.exists() else None,
        schema_file=_schema_file() if _schema_file().exists() else None,
        env_prefix="KI_CFG_DISABLED_",
    )
    payload = resolver.resolve()
    if not isinstance(payload, dict):
        raise ValueError(f"YAML config must contain a mapping at {config_path}")
    return payload


def _read_creds_config(path: Optional[Union[str, Path]] = None) -> dict[str, Any]:
    creds_path = _find_creds_yaml_path(path)
    if not creds_path:
        return {}

    resolver = ConfigResolver(defaults=[creds_path], schema_file=_schema_file() if _schema_file().exists() else None)
    payload = resolver.resolve()
    if not isinstance(payload, dict):
        raise ValueError(f"Credentials config must contain a mapping at {creds_path}")
    return payload


def _canonicalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(payload)

    llm = _section(canonical, "llm")
    providers = _section(llm, "providers")
    ki_provider = dict(_section(providers, "ki"))
    openai_provider = dict(_section(providers, "openai"))
    ollama_provider = dict(_section(providers, "ollama"))

    ki_legacy = _section(canonical, "ki")
    openai_legacy = _section(canonical, "openai")
    ollama_legacy = _section(canonical, "ollama")
    knowledge_legacy = _section(canonical, "knowledge")
    storage_legacy = _section(canonical, "storage")
    kicli_legacy = _section(canonical, "kicli")
    apps_legacy = _section(canonical, "apps")
    apps_kicli = _section(apps_legacy, "kicli")
    http_legacy = _section(canonical, "http")
    jira_legacy = _section(canonical, "jira")
    infosite_legacy = _section(canonical, "infosite")
    context_legacy = _section(canonical, "context")
    diff_legacy = _section(canonical, "diff")

    ki_provider = {
        "base_url": _coalesce(ki_provider.get("base_url"), ki_legacy.get("base_url"), canonical.get("ki_base_url")),
        "api_key": _coalesce(ki_provider.get("api_key"), ki_legacy.get("api_key"), canonical.get("ki_api_key")),
        "model": _coalesce(ki_provider.get("model"), ki_legacy.get("model"), canonical.get("ki_model")),
        "endpoint": _coalesce(ki_provider.get("endpoint"), ki_legacy.get("endpoint"), canonical.get("ki_endpoint")),
    }
    openai_provider = {
        "base_url": _coalesce(openai_provider.get("base_url"), openai_legacy.get("base_url"), canonical.get("openai_base_url")),
        "api_key": _coalesce(openai_provider.get("api_key"), openai_legacy.get("api_key"), canonical.get("openai_api_key")),
        "model": _coalesce(openai_provider.get("model"), openai_legacy.get("model"), canonical.get("openai_model")),
    }
    ollama_provider = {
        "base_url": _coalesce(
            ollama_provider.get("base_url"),
            ollama_legacy.get("base_url"),
            ollama_legacy.get("url"),
            canonical.get("ollama_base_url"),
        ),
        "model": _coalesce(ollama_provider.get("model"), ollama_legacy.get("model"), canonical.get("ollama_model")),
    }

    knowledge_paths = dict(_section(knowledge_legacy, "paths"))
    knowledge_paths = {
        "markdown_root": _coalesce(knowledge_paths.get("markdown_root")),
        "jira_root": _coalesce(knowledge_paths.get("jira_root")),
        "ontology_root": _coalesce(knowledge_paths.get("ontology_root")),
        "pdf_root": _coalesce(knowledge_paths.get("pdf_root")),
    }

    storage = {
        "cache_dir": _coalesce(
            storage_legacy.get("cache_dir"),
            kicli_legacy.get("cache_dir"),
            canonical.get("kicli_cache_dir"),
        ),
        "session_dir": _coalesce(
            storage_legacy.get("session_dir"),
            kicli_legacy.get("session_dir"),
            canonical.get("kicli_session_dir"),
        ),
        "history_dir": _coalesce(
            storage_legacy.get("history_dir"),
            kicli_legacy.get("chat_history_dir"),
            canonical.get("kicli_chat_history_dir"),
        ),
    }

    canonical["llm"] = {
        "default_provider": _coalesce(_value(llm, "default_provider"), "ki"),
        "providers": {
            "ki": {key: value for key, value in ki_provider.items() if value is not None},
            "openai": {key: value for key, value in openai_provider.items() if value is not None},
            "ollama": {key: value for key, value in ollama_provider.items() if value is not None},
        },
    }
    canonical["knowledge"] = {
        **knowledge_legacy,
        "data_root": _coalesce(knowledge_legacy.get("data_root"), canonical.get("knowledge_data_root")),
        "cache_db": _coalesce(knowledge_legacy.get("cache_db"), canonical.get("knowledge_cache_db")),
        "graph_db": _coalesce(knowledge_legacy.get("graph_db"), canonical.get("knowledge_graph_db")),
        "embed_model": _coalesce(knowledge_legacy.get("embed_model"), canonical.get("knowledge_embed_model")),
        "default_domain": _coalesce(knowledge_legacy.get("default_domain"), "default"),
        "paths": {key: value for key, value in knowledge_paths.items() if value is not None},
    }
    canonical["storage"] = {key: value for key, value in storage.items() if value is not None}
    canonical["http"] = {
        **http_legacy,
        "request_timeout": _coalesce(http_legacy.get("request_timeout"), canonical.get("request_timeout")),
        "verify_ssl": _coalesce(http_legacy.get("verify_ssl"), canonical.get("http_verify_ssl")),
    }
    canonical["jira"] = {
        **jira_legacy,
        "url": _coalesce(jira_legacy.get("url"), jira_legacy.get("base_url"), canonical.get("jira_url")),
        "username": _coalesce(jira_legacy.get("username"), canonical.get("jira_username")),
        "api_token": _coalesce(jira_legacy.get("api_token"), jira_legacy.get("token"), canonical.get("jira_api_token")),
    }
    canonical["infosite"] = {
        **infosite_legacy,
        "enabled": _coalesce(infosite_legacy.get("enabled"), canonical.get("infosite_enabled")),
        "title": _coalesce(infosite_legacy.get("title"), canonical.get("infosite_title")),
        "output_base_dir": _coalesce(
            infosite_legacy.get("output_base_dir"),
            infosite_legacy.get("output_dir"),
            canonical.get("infosite_output_base_dir"),
        ),
        "domain": _coalesce(infosite_legacy.get("domain"), canonical.get("infosite_domain"), "default"),
    }

    apps = dict(apps_legacy)
    apps["kicli"] = {
        **apps_kicli,
        "workspace_root": _coalesce(
            apps_kicli.get("workspace_root"),
            kicli_legacy.get("allowed_base_path"),
            kicli_legacy.get("workspace_root"),
            canonical.get("kicli_allowed_base_path"),
        ),
        "prompt_history_dir": _coalesce(
            apps_kicli.get("prompt_history_dir"),
            kicli_legacy.get("chat_history_dir"),
            canonical.get("kicli_chat_history_dir"),
        ),
        "context": {
            **_section(apps_kicli, "context"),
            "max_files": _coalesce(_value(apps_kicli, "context", "max_files"), context_legacy.get("max_files"), canonical.get("context_max_files")),
            "max_size_mb": _coalesce(_value(apps_kicli, "context", "max_size_mb"), context_legacy.get("max_size_mb"), canonical.get("context_max_size_mb")),
            "relevance_threshold": _coalesce(_value(apps_kicli, "context", "relevance_threshold"), context_legacy.get("relevance_threshold"), canonical.get("context_relevance_threshold")),
            "cache_enabled": _coalesce(_value(apps_kicli, "context", "cache_enabled"), context_legacy.get("cache_enabled"), canonical.get("context_cache_enabled")),
            "cache_ttl_hours": _coalesce(_value(apps_kicli, "context", "cache_ttl_hours"), context_legacy.get("cache_ttl_hours"), canonical.get("context_cache_ttl_hours")),
            "cache_max_size_mb": _coalesce(_value(apps_kicli, "context", "cache_max_size_mb"), context_legacy.get("cache_max_size_mb"), canonical.get("context_cache_max_size_mb")),
            "ignore_patterns": _coalesce(_value(apps_kicli, "context", "ignore_patterns"), context_legacy.get("ignore_patterns"), canonical.get("context_ignore_patterns")),
        },
        "diff": {
            **_section(apps_kicli, "diff"),
            "context_lines": _coalesce(_value(apps_kicli, "diff", "context_lines"), diff_legacy.get("context_lines"), canonical.get("diff_context_lines")),
            "format": _coalesce(_value(apps_kicli, "diff", "format"), diff_legacy.get("format"), canonical.get("diff_format")),
            "highlight_syntax": _coalesce(_value(apps_kicli, "diff", "highlight_syntax"), diff_legacy.get("highlight_syntax"), canonical.get("diff_highlight_syntax")),
            "auto_apply_threshold": _coalesce(_value(apps_kicli, "diff", "auto_apply_threshold"), diff_legacy.get("auto_apply_threshold"), canonical.get("diff_auto_apply_threshold")),
            "max_file_size_kb": _coalesce(_value(apps_kicli, "diff", "max_file_size_kb"), diff_legacy.get("max_file_size_kb"), canonical.get("diff_max_file_size_kb")),
        },
    }
    canonical["apps"] = apps
    return canonical


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in ("true", "1", "yes")


@dataclass
class Config:
    ki_base_url: str = ""
    ki_api_key: str = ""
    ki_model: str = "google/gemma-4-26B-A4B-it"
    ki_endpoint: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    openai_api_key: str = ""
    openai_model: str = "gpt-4"
    openai_base_url: str = "https://api.openai.com/v1"
    knowledge_data_root: str = ""
    knowledge_cache_db: Optional[str] = None
    knowledge_graph_db: Optional[str] = None
    knowledge_embed_model: str = "nomic-embed-text"
    infosite_enabled: bool = False
    infosite_title: str = ""
    infosite_output_base_dir: str = ""
    infosite_domain: str = "default"
    jira_url: Optional[str] = None
    jira_username: Optional[str] = None
    jira_api_token: Optional[str] = None
    request_timeout: int = 30
    http_verify_ssl: bool = True
    kicli_cache_dir: str = ""
    kicli_session_dir: str = ""
    kicli_chat_history_dir: str = ""
    kicli_allowed_base_path: str = ""
    context_max_files: int = 10
    context_max_size_mb: int = 5
    context_relevance_threshold: float = 0.15
    context_cache_enabled: bool = True
    context_cache_ttl_hours: int = 24
    context_cache_max_size_mb: int = 50
    context_ignore_patterns: str = "__pycache__,*.pyc,node_modules,.git,.env"
    diff_context_lines: int = 3
    diff_format: str = "unified"
    diff_highlight_syntax: bool = True
    diff_auto_apply_threshold: float = 0.8
    diff_max_file_size_kb: int = 100

    @classmethod
    def from_yaml(cls, path: Optional[Union[str, Path]] = None) -> "Config":
        payload = _canonicalize_payload(_read_yaml_config(path))
        creds_payload = _canonicalize_payload(_read_creds_config(path))

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

        creds_cfg = _section(creds_payload, "creds")
        creds_ki_cfg = _section(_section(creds_payload, "llm", "providers"), "ki")
        creds_openai_cfg = _section(_section(creds_payload, "llm", "providers"), "openai")

        return cls(
            ki_base_url=_coalesce(creds_ki_cfg.get("base_url"), creds_cfg.get("base_url"), ki_cfg.get("base_url")) or "",
            ki_api_key=_coalesce(creds_ki_cfg.get("api_key"), creds_cfg.get("api_key"), ki_cfg.get("api_key")) or "",
            ki_model=_coalesce(ki_cfg.get("model")) or "google/gemma-4-26B-A4B-it",
            ki_endpoint=_coalesce(ki_cfg.get("endpoint")),
            ollama_base_url=_coalesce(ollama_cfg.get("base_url")) or "http://localhost:11434",
            ollama_model=_coalesce(ollama_cfg.get("model")) or "llama3.2",
            openai_api_key=_coalesce(creds_openai_cfg.get("api_key"), openai_cfg.get("api_key")) or "",
            openai_model=_coalesce(openai_cfg.get("model")) or "gpt-4",
            openai_base_url=_coalesce(openai_cfg.get("base_url")) or "https://api.openai.com/v1",
            knowledge_data_root=_coalesce(knowledge_cfg.get("data_root")) or "",
            knowledge_cache_db=_coalesce(knowledge_cfg.get("cache_db")),
            knowledge_graph_db=_coalesce(knowledge_cfg.get("graph_db")),
            knowledge_embed_model=_coalesce(knowledge_cfg.get("embed_model")) or "nomic-embed-text",
            infosite_enabled=_bool_value(infosite_cfg.get("enabled"), default=False),
            infosite_title=_coalesce(infosite_cfg.get("title"), "") or "",
            infosite_output_base_dir=_coalesce(infosite_cfg.get("output_base_dir"), "") or "",
            infosite_domain=_coalesce(infosite_cfg.get("domain"), "default") or "default",
            jira_url=_coalesce(jira_cfg.get("url")),
            jira_username=_coalesce(jira_cfg.get("username")),
            jira_api_token=_coalesce(jira_cfg.get("api_token")),
            request_timeout=_int_value(http_cfg.get("request_timeout"), default=30),
            http_verify_ssl=_bool_value(http_cfg.get("verify_ssl"), default=True),
            kicli_cache_dir=_coalesce(storage_cfg.get("cache_dir")) or "",
            kicli_session_dir=_coalesce(storage_cfg.get("session_dir")) or "",
            kicli_chat_history_dir=_coalesce(
                apps_kicli_cfg.get("prompt_history_dir"),
                storage_cfg.get("history_dir"),
            ) or "",
            kicli_allowed_base_path=_coalesce(apps_kicli_cfg.get("workspace_root")) or "",
            context_max_files=_int_value(context_cfg.get("max_files"), default=10),
            context_max_size_mb=_int_value(context_cfg.get("max_size_mb"), default=5),
            context_relevance_threshold=_float_value(context_cfg.get("relevance_threshold"), default=0.15),
            context_cache_enabled=_bool_value(context_cfg.get("cache_enabled"), default=True),
            context_cache_ttl_hours=_int_value(context_cfg.get("cache_ttl_hours"), default=24),
            context_cache_max_size_mb=_int_value(context_cfg.get("cache_max_size_mb"), default=50),
            context_ignore_patterns=_coalesce(
                context_cfg.get("ignore_patterns"),
                "__pycache__,*.pyc,node_modules,.git,.env",
            ) or "__pycache__,*.pyc,node_modules,.git,.env",
            diff_context_lines=_int_value(diff_cfg.get("context_lines"), default=3),
            diff_format=_coalesce(diff_cfg.get("format"), "unified") or "unified",
            diff_highlight_syntax=_bool_value(diff_cfg.get("highlight_syntax"), default=True),
            diff_auto_apply_threshold=_float_value(diff_cfg.get("auto_apply_threshold"), default=0.8),
            diff_max_file_size_kb=_int_value(diff_cfg.get("max_file_size_kb"), default=100),
        )

    @classmethod
    def from_env(cls, config_path: Optional[Union[str, Path]] = None) -> "Config":
        load_dotenv(find_dotenv(usecwd=True), override=False)
        yaml_cfg = cls.from_yaml(config_path)
        return cls(
            ki_base_url=os.getenv("KI_BASE_URL", yaml_cfg.ki_base_url),
            ki_api_key=os.getenv("KI_API_KEY", yaml_cfg.ki_api_key),
            ki_model=os.getenv("KI_MODEL", yaml_cfg.ki_model),
            ki_endpoint=os.getenv("KI_ENDPOINT", yaml_cfg.ki_endpoint or ""),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", yaml_cfg.ollama_base_url),
            ollama_model=os.getenv("OLLAMA_MODEL", yaml_cfg.ollama_model),
            openai_api_key=os.getenv("OPENAI_API_KEY", yaml_cfg.openai_api_key),
            openai_model=os.getenv("OPENAI_MODEL", yaml_cfg.openai_model),
            openai_base_url=os.getenv("OPENAI_BASE_URL", yaml_cfg.openai_base_url),
            knowledge_data_root=os.getenv("KNOWLEDGE_DATA_ROOT", os.getenv("KICLI_DATA_ROOT", yaml_cfg.knowledge_data_root)),
            knowledge_cache_db=os.getenv("KNOWLEDGE_CACHE_DB", os.getenv("KI_CACHE_DB", yaml_cfg.knowledge_cache_db or "")),
            knowledge_graph_db=os.getenv("KNOWLEDGE_GRAPH_DB", os.getenv("KI_GRAPH_DB", yaml_cfg.knowledge_graph_db or "")),
            knowledge_embed_model=os.getenv("KNOWLEDGE_EMBED_MODEL", os.getenv("KI_EMBED_MODEL", yaml_cfg.knowledge_embed_model)),
            jira_url=os.getenv("JIRA_URL", yaml_cfg.jira_url or ""),
            jira_username=os.getenv("JIRA_USERNAME", yaml_cfg.jira_username or ""),
            jira_api_token=os.getenv("JIRA_API_TOKEN", yaml_cfg.jira_api_token or ""),
            request_timeout=int(os.getenv("KI_REQUEST_TIMEOUT", str(yaml_cfg.request_timeout))),
            http_verify_ssl=_env_bool("KI_VERIFY_SSL", yaml_cfg.http_verify_ssl),
            kicli_cache_dir=os.getenv("KICLI_CACHE_DIR", yaml_cfg.kicli_cache_dir),
            kicli_session_dir=os.getenv("KICLI_SESSION_DIR", yaml_cfg.kicli_session_dir),
            kicli_chat_history_dir=os.getenv("KICLI_CHAT_HISTORY_DIR", yaml_cfg.kicli_chat_history_dir),
            kicli_allowed_base_path=os.getenv("KICLI_ALLOWED_BASE_PATH", yaml_cfg.kicli_allowed_base_path),
            context_max_files=int(os.getenv("CONTEXT_MAX_FILES", str(yaml_cfg.context_max_files))),
            context_max_size_mb=int(os.getenv("CONTEXT_MAX_SIZE_MB", str(yaml_cfg.context_max_size_mb))),
            context_relevance_threshold=float(os.getenv("CONTEXT_RELEVANCE_THRESHOLD", str(yaml_cfg.context_relevance_threshold))),
            context_cache_enabled=_env_bool("CONTEXT_CACHE_ENABLED", yaml_cfg.context_cache_enabled),
            context_cache_ttl_hours=int(os.getenv("CONTEXT_CACHE_TTL_HOURS", str(yaml_cfg.context_cache_ttl_hours))),
            context_cache_max_size_mb=int(os.getenv("CONTEXT_CACHE_MAX_SIZE_MB", str(yaml_cfg.context_cache_max_size_mb))),
            context_ignore_patterns=os.getenv("CONTEXT_IGNORE_PATTERNS", yaml_cfg.context_ignore_patterns),
            diff_context_lines=int(os.getenv("DIFF_CONTEXT_LINES", str(yaml_cfg.diff_context_lines))),
            diff_format=os.getenv("DIFF_FORMAT", yaml_cfg.diff_format),
            diff_highlight_syntax=_env_bool("DIFF_HIGHLIGHT_SYNTAX", yaml_cfg.diff_highlight_syntax),
            diff_auto_apply_threshold=float(os.getenv("DIFF_AUTO_APPLY_THRESHOLD", str(yaml_cfg.diff_auto_apply_threshold))),
            diff_max_file_size_kb=int(os.getenv("DIFF_MAX_FILE_SIZE_KB", str(yaml_cfg.diff_max_file_size_kb))),
        )

    def validate(self) -> None:
        pass
