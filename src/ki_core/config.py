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
from pathlib import Path
from typing import Any, Optional, Union

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
