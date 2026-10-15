"""Config resolution diagnostics command.

Shows the complete configuration resolution chain and where each setting
comes from in the layered config system.
"""

from pathlib import Path
from typing import Any, Callable, Optional, Union

from ki_core.config import active_layers, find_config_path


def run_doctor(
    echo_fn: Optional[Callable[[str], None]] = None,
    show_config_path: bool = True,
) -> None:
    """Display configuration resolution diagnostics.

    Args:
        echo_fn: Custom output function (defaults to print).
        show_config_path: Whether to display the config file location.

    This is used by both ki-chat and downstream apps (kicli-assist, etc.)
    as a shared base diagnostics command.
    """
    from ki_core.config import ConfigDict, load_config

    if echo_fn is None:
        echo_fn = print

    config = load_config()
    layers = active_layers()
    config_file = find_config_path()

    if show_config_path:
        echo_fn(f"Config: {config_file.resolve()}")
        echo_fn()

    echo_fn("Configuration resolution chain (highest to lowest priority):")
    echo_fn("  1. creds.yaml (secrets)")
    echo_fn("  2. Environment variables (KI_CFG_*)")
    echo_fn("  3. config/runtime/runtime.yaml (host-local overrides)")
    if layers.get("stage"):
        echo_fn(f"  4. config/stages/{layers.get('stage')}.yaml (active stage)")
    else:
        echo_fn("  4. config/stages/<stage>.yaml (no active stage)")
    if layers.get("profile"):
        echo_fn(f"  5. config/profiles/{layers.get('profile')}.yaml (active profile)")
    else:
        echo_fn("  5. config/profiles/<profile>.yaml (no active profile)")
    echo_fn(f"  6. {config_file.resolve()} (main config)")
    echo_fn("  7. config/defaults/*.yaml (per-layer defaults)")
    echo_fn("  8. ki-core schema defaults (fallback)")
    echo_fn()

    echo_fn("Active layers:")
    echo_fn(
        f"  - Profile: {layers.get('profile') or '(none - using schema defaults)'}"
    )
    echo_fn(f"  - Stage:   {layers.get('stage') or '(none - using schema defaults)'}")
    echo_fn()

    echo_fn("LLM Provider configuration (detection order: ollama → openai → ki → mock):")
    providers = config.get_path("llm.providers", {}) or {}
    ollama_cfg = providers.get("ollama", {}) or {}
    openai_cfg = providers.get("openai", {}) or {}
    ki_cfg = providers.get("ki", {}) or {}

    echo_fn(
        f"  - Ollama base_url: {ollama_cfg.get('base_url') or '(ki-core schema default: http://localhost:11434)'}"
    )
    echo_fn(
        f"  - Ollama model:    {ollama_cfg.get('model') or '(ki-core schema default: llama3.2)'}"
    )
    echo_fn(f"  - OpenAI base_url: {openai_cfg.get('base_url') or '(unset)'}")
    echo_fn(f"  - OpenAI API key:  {'set' if openai_cfg.get('api_key') else 'missing'}")
    echo_fn(f"  - KI base_url:     {ki_cfg.get('base_url') or '(unset)'}")
    echo_fn(f"  - KI API key:      {'set' if ki_cfg.get('api_key') else 'missing'}")
    echo_fn()

    echo_fn("HTTP settings:")
    echo_fn(
        f"  - Request timeout: {config.get_path('http.request_timeout', 30)}s"
    )
    echo_fn(
        f"  - Verify SSL:      {config.get_path('http.verify_ssl', True)}"
    )
    echo_fn()

    echo_fn("Storage paths (app-defined in schema):")
    echo_fn(f"  - Cache dir:   {config.get_path('storage.cache_dir', '') or '(unset)'}")
    echo_fn(
        f"  - Session dir: {config.get_path('storage.session_dir', '') or '(unset)'}"
    )
    echo_fn(
        f"  - History dir: {config.get_path('storage.history_dir', '') or '(unset)'}"
    )
    echo_fn()

    echo_fn("To change defaults, edit in order of precedence:")
    echo_fn(
        f"  - Environment: export KI_CFG_LLM__PROVIDERS__OLLAMA__BASE_URL=... (highest)"
    )
    echo_fn(f"  - Runtime:     vim config/runtime/runtime.yaml")
    echo_fn(f"  - Stage:       vim config/stages/<name>.yaml")
    echo_fn(f"  - Profile:     vim config/profiles/<name>.yaml")
    echo_fn(f"  - Main config: vim {config_file.resolve()}")
    echo_fn(f"  - Defaults:    vim config/defaults/*.yaml (lowest)")
