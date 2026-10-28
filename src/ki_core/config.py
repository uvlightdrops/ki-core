"""Unified configuration resolution for the ki ecosystem.

Uses schema-based config generation and yaml-cfg-wizard ConfigResolver
for layered config resolution. There are no code-based fallbacks - all
defaults come from the merged JSON schema (ki-core's generic base schema
plus each app's own schema, e.g. schema/kicli.schema.yaml).

ki-core intentionally does not expose a fat, cross-app "Config" object.
Each app owns its own thin config accessor (see e.g.
kicli_code_assist.app_config.AppConfig) built on top of the plain dict
returned by load_config().
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Optional, Union

from dotenv import find_dotenv, load_dotenv
from yaml_cfg_wizard import ConfigResolver, deep_merge
from yaml_cfg_wizard.schema_utils import merge_schemas, scaffold_skeleton_from_schema


load_dotenv(find_dotenv())

# One stage (dev-lokal, prod, ...) and at most one profile are active per host:
# env var first, then a marker file in the layer directory (same marker
# convention as `yaml-cfg profile set`). Nothing selected -> layer skipped.
STAGE_ENV = "KI_STAGE"
PROFILE_ENV = "KI_PROFILE"
ACTIVE_STAGE_MARKER = ".active_stage"
ACTIVE_PROFILE_MARKER = ".active_profile"


def _find_yaml_config_path(path: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """Find a YAML config file in common locations."""
    if path is not None:
        candidate = Path(path)
        if candidate.exists():
            return candidate

    candidates = [
        Path("ki.yaml"),
        Path.home() / ".config" / "ki" / "ki.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def find_config_path(path: Optional[Union[str, Path]] = None) -> Path:
    """Find the active YAML config file, or a sensible default write target.

    Public wrapper around the same discovery logic used internally by
    ``load_config()``, for callers (e.g. a TUI settings editor) that need
    to know exactly which file resolved values came from, or where to
    write edits back to. Unlike ``_find_yaml_config_path()``, this never
    returns None: if no existing config file is found, it returns
    ``Path("ki.yaml")`` in the current directory as the default location
    a new one would be created at.
    """
    return _find_yaml_config_path(path) or Path("ki.yaml")


def _find_creds_yaml_path(path: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """Find credentials file (kept separate for security)."""
    if path is not None:
        base_dir = Path(path).resolve().parent
        for candidate in [base_dir / "creds.yaml", base_dir / "config" / "creds.yaml"]:
            if candidate.exists():
                return candidate

    candidates = [
        Path("creds.yaml"),
        Path.home() / ".config" / "ki" / "creds.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _schema_file() -> Path:
    """Get path to ki-core's base (generic) schema."""
    from ki_core.schema_manager import get_schema_path
    return get_schema_path()


def find_app_schemas(start: Optional[Path] = None, max_depth: int = 5) -> list[Path]:
    """Discover app-specific schema files (schema/*.schema.yaml) by walking
    up from the current (or given) directory.

    Any file matching schema/*.schema.yaml is treated as an app schema to be
    merged on top of ki-core's generic base schema, except the base schema
    file itself. This lets any app (kicli-code-assist, ki-knowledge, ...)
    provide its own schema without ki-core needing to know about it.
    """
    base_schema = _schema_file().resolve()
    found: list[Path] = []
    current = (start or Path.cwd()).resolve()
    for _ in range(max_depth):
        schema_dir = current / "schema"
        if schema_dir.is_dir():
            for candidate in sorted(schema_dir.glob("*.schema.yaml")):
                if candidate.resolve() != base_schema:
                    found.append(candidate)
        current = current.parent
    return found


def get_merged_schemas(start: Optional[Path] = None) -> list[Path]:
    """Get list of schemas to merge (ki-core base + any app-specific schemas)."""
    return [_schema_file(), *find_app_schemas(start)]


def _layered_config_dir(path: Optional[Union[str, Path]] = None) -> Path:
    config_path = _find_yaml_config_path(path)
    config_dir = config_path.resolve().parent if config_path else Path.cwd()
    return config_dir / "config"


def _active_name(directory: Path, env_var: str, marker: str) -> Optional[str]:
    name = os.getenv(env_var, "").strip()
    if not name and (directory / marker).is_file():
        name = (directory / marker).read_text(encoding="utf-8").strip()
    return name or None


def _layer_file(directory: Path, env_var: str, marker: str) -> Optional[Path]:
    """The selected ``<name>.yaml`` in ``directory``; error if the name does not exist."""
    name = _active_name(directory, env_var, marker)
    if not name:
        return None
    for ext in (".yaml", ".yml"):
        candidate = directory / f"{name}{ext}"
        if candidate.is_file():
            return candidate
    available = sorted(f.stem for f in directory.glob("*.y*ml")) if directory.is_dir() else []
    raise ValueError(
        f"{env_var} / {directory / marker}: '{name}' not found in {directory} (available: {', '.join(available) or '-'})"
    )


def active_layers(path: Optional[Union[str, Path]] = None) -> dict[str, Optional[str]]:
    """Names of the active stage and profile (``None`` if not selected)."""
    layered = _layered_config_dir(path)
    return {
        "stage": _active_name(layered / "stages", STAGE_ENV, ACTIVE_STAGE_MARKER),
        "profile": _active_name(layered / "profiles", PROFILE_ENV, ACTIVE_PROFILE_MARKER),
    }


def _resolve_config(path: Optional[Union[str, Path]] = None) -> dict[str, Any]:
    """Resolve complete config from all sources using ConfigResolver."""
    config_path = _find_yaml_config_path(path)
    creds_path = _find_creds_yaml_path(path)

    layered_config_dir = _layered_config_dir(path)
    stage_file = _layer_file(layered_config_dir / "stages", STAGE_ENV, ACTIVE_STAGE_MARKER)
    profile_file = _layer_file(layered_config_dir / "profiles", PROFILE_ENV, ACTIVE_PROFILE_MARKER)

    # Get all schemas for validation (base + app-specific)
    schemas = get_merged_schemas()

    resolver = ConfigResolver(
        defaults=[config_path] if config_path else [],
        defaults_dir=layered_config_dir / "defaults" if (layered_config_dir / "defaults").exists() else None,
        profiles=[profile_file] if profile_file else [],
        stage=[stage_file] if stage_file else [],
        runtime_file=(layered_config_dir / "runtime" / "runtime.yaml")
        if (layered_config_dir / "runtime" / "runtime.yaml").exists()
        else None,
        schema_file=schemas[0] if schemas else None,  # Use base schema for validation
        env_prefix="KI_CFG_",
    )

    payload = resolver.resolve()
    if not isinstance(payload, dict):
        payload = {}

    # Merge in creds if available (separate for security)
    if creds_path:
        creds_resolver = ConfigResolver(
            defaults=[creds_path],
            schema_file=schemas[0] if schemas else None,
        )
        creds_payload = creds_resolver.resolve()
        if isinstance(creds_payload, dict):
            payload = deep_merge(payload, creds_payload)

    # Fill in anything not explicitly set with the merged schema's defaults,
    # so there is no need for hardcoded fallback values in application code.
    schema_defaults = scaffold_skeleton_from_schema(merge_schemas(*schemas)) if schemas else {}
    return deep_merge(schema_defaults, payload)


class ConfigDict(dict):
    """Resolved config dict with convenient dotted-path access.

    Behaves exactly like a plain dict (so `config.get("prompts", {})` etc.
    keep working), but adds `get_path()` for ergonomic nested lookups.
    """

    def get_path(self, dotted_path: str, default: Any = None) -> Any:
        """Get a nested value using a dotted path, e.g. "llm.providers.ollama.base_url"."""
        current: Any = self
        for part in dotted_path.split("."):
            if not isinstance(current, dict):
                return default
            current = current.get(part)
        return default if current is None else current


def load_config(path: Optional[Union[str, Path]] = None) -> ConfigDict:
    """Load and resolve the full config from YAML files + environment variables.

    Resolution order (highest to lowest priority):
    1. creds.yaml (deep-merged on top for secrets)
    2. Environment variables (KI_CFG_* prefix, ``__`` for nesting)
    3. Runtime file (config/runtime/runtime.yaml) - host-local overrides
    4. Active stage (config/stages/<KI_STAGE or stages/.active_stage>.yaml)
    5. Active profile (config/profiles/<KI_PROFILE or profiles/.active_profile>.yaml)
    6. Main config (ki.yaml)
    7. Defaults (config/defaults/*.yaml)
    8. Schema defaults (ki-core base schema + app schemas)

    Only the selected stage/profile file is loaded, never all of them.

    Returns a plain, JSON-schema-validated dict (ConfigDict) - there is no
    hardcoded dataclass shape. Apps should build their own thin, typed
    accessor on top of this if they want attribute-style access.
    """
    return ConfigDict(_resolve_config(path))


class ConfigManager:
    """Orchestration layer for config resolution with provider detection & logging setup.

    Single source of truth for:
    - LLM provider selection (follows 9-layer precedence exactly)
    - Logging configuration (extracted from ki.yaml)
    - Config path discovery (for status output, diagnostics, etc.)

    Designed to be thin (not fat config object): delegates to load_config()
    for layering, provides convenience methods for common app needs.
    """

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        echo_fn: Optional[Callable[[str], None]] = None,
        *,
        config: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Initialize ConfigManager.

        Args:
            config_path: Explicit path to ki.yaml, or None for auto-discovery.
            echo_fn: Optional callback for status output (e.g., cli.echo, typer.echo, print).
            config: Already resolved config snapshot. When supplied, load() does
                not read files again; useful for apps with their own config cache.
        """
        self.config_path = find_config_path(config_path)
        self.echo_fn = echo_fn or (lambda x: None)
        self._config: Optional[ConfigDict] = ConfigDict(deepcopy(dict(config))) if config is not None else None
        self._active_layers: Optional[dict[str, Optional[str]]] = None

    def load(self) -> ConfigDict:
        """Load the full resolved config (caches after first call)."""
        if self._config is None:
            self._config = load_config(str(self.config_path))
        return self._config

    def get_active_layers(self) -> dict[str, Optional[str]]:
        """Get the active stage and profile names (None if not selected)."""
        if self._active_layers is None:
            self._active_layers = active_layers(str(self.config_path))
        return self._active_layers

    def get_llm_provider(self) -> str:
        """Detect best available LLM provider from resolved config.

        Priority (in order of checks):
        1. Explicit provider field in config (llm.provider if set to non-"auto")
        2. OpenAI (if API key is configured and not a placeholder)
        3. Ollama (if reachable)
        4. Company KI (if API key configured)
        5. Mock (fallback for testing)

        Returns the provider name as string: "openai", "ollama", "ki", or "mock".
        This is the SINGLE SOURCE OF TRUTH for provider selection - consolidates
        logic that was previously duplicated in cli.py and llm_integration.py.
        """
        config = self.load()

        # Check for explicit provider selection (if user set it to non-"auto")
        explicit_provider = config.get_path("llm.provider", "auto").strip().lower()
        if explicit_provider and explicit_provider != "auto":
            return explicit_provider

        # Priority 1: OpenAI
        openai_key = config.get_path("llm.providers.openai.api_key", "")
        if openai_key and not openai_key.startswith("${"):
            return "openai"

        # Priority 2: Ollama (try to reach it)
        ollama_url = config.get_path("llm.providers.ollama.base_url", "")
        if ollama_url:
            try:
                import requests
                requests.head(ollama_url, timeout=2)
                return "ollama"
            except Exception:
                pass

        # Priority 3: Company KI
        ki_key = config.get_path("llm.providers.ki.api_key", "")
        if ki_key and not ki_key.startswith("${"):
            return "ki"

        # Priority 4: Mock (fallback)
        return "mock"

    def get_logging_config(self) -> dict[str, Any]:
        """Extract logging configuration from ki.yaml.

        Returns a dict with keys:
        - level: global log level (DEBUG, INFO, WARNING, ERROR)
        - format: format string for log records
        - per_module: dict mapping module names to override levels
        - handlers: list of handler definitions (file paths, etc.)

        This allows logging_integration.py to read from config instead of
        hardcoded logconf.ini paths.
        """
        config = self.load()
        logging_section = config.get_path("logging", {}) or {}

        return {
            "level": logging_section.get("level", "INFO"),
            "format": logging_section.get("format", "%(asctime)s [%(levelname)s] %(message)s"),
            "per_module": logging_section.get("per_module", {}),
            "handlers": logging_section.get("handlers", []),
        }

    def echo_config_path(self) -> None:
        """Output the resolved config path via echo_fn (for CLI status output).

        Useful for `kicli-assist tui` and similar commands that want to show
        where the config is being loaded from.
        """
        self.echo_fn(f"Config: {self.config_path}")
