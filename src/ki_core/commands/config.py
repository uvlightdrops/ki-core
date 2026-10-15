"""Config management commands (resolve, verify, skeleton, show).

These are shared implementations used by all apps via delegation.
cli-agnostic: work with any echo function (print, click.echo, typer.echo).
"""

from pathlib import Path
from typing import Callable, List, Optional, Union

from ki_core.config import find_config_path
from yaml_cfg_wizard import ConfigResolver, deep_merge, write_skeleton_to_file


def run_resolve(
    echo_fn: Optional[Callable[[str], None]] = None,
    defaults_dir: Optional[str] = None,
    defaults: Optional[List[str]] = None,
    profile: Optional[str] = None,
    stage: Optional[str] = None,
    runtime_file: Optional[str] = None,
    env_prefix: str = "KI_CFG_",
    schema_file: Optional[str] = None,
    output_file: Optional[str] = None,
) -> None:
    """Resolve config from all layers and display (or write) result.

    Args:
        echo_fn: Custom output function (defaults to print).
        defaults_dir: Directory with default YAML files.
        defaults: Explicit default YAML files.
        profile: Active profile YAML file path.
        stage: Active stage YAML file path.
        runtime_file: Runtime override YAML file.
        env_prefix: Environment variable prefix (e.g., KI_CFG_).
        schema_file: Schema file for validation and defaults.
        output_file: Write resolved config to file (YAML format).
    """
    if echo_fn is None:
        echo_fn = print

    try:
        resolver = ConfigResolver(
            defaults=[Path(d) for d in (defaults or [])] if defaults else None,
            defaults_dir=Path(defaults_dir) if defaults_dir else None,
            profiles=[Path(profile)] if profile else None,
            stage=[Path(stage)] if stage else None,
            runtime_file=Path(runtime_file) if runtime_file else None,
            schema_file=Path(schema_file) if schema_file else None,
            env_prefix=env_prefix,
        )

        payload = resolver.resolve()

        if output_file:
            import yaml

            with open(output_file, "w") as f:
                yaml.safe_dump(payload, f, sort_keys=False, default_flow_style=False)
            echo_fn(f"✅ Resolved config written to: {output_file}")
        else:
            import yaml

            echo_fn(yaml.safe_dump(payload, sort_keys=False, default_flow_style=False))

    except Exception as e:
        echo_fn(f"❌ Error resolving config: {e}")
        raise


def run_verify(
    echo_fn: Optional[Callable[[str], None]] = None,
    config_file: Optional[str] = None,
    schema_file: Optional[str] = None,
) -> None:
    """Verify config file against schema.

    Args:
        echo_fn: Custom output function (defaults to print).
        config_file: Path to config YAML file.
        schema_file: Path to JSON schema file.
    """
    if echo_fn is None:
        echo_fn = print

    try:
        import json

        import jsonschema
        import yaml

        if not config_file:
            config_file = str(find_config_path())

        with open(config_file) as f:
            config = yaml.safe_load(f) or {}

        if not schema_file:
            raise ValueError("Schema file required for verification")

        with open(schema_file) as f:
            schema = json.load(f)

        jsonschema.validate(instance=config, schema=schema)
        echo_fn(f"✅ {config_file} is valid according to schema")

    except jsonschema.ValidationError as e:
        echo_fn(f"❌ Validation error: {e.message}")
        raise
    except Exception as e:
        echo_fn(f"❌ Error verifying config: {e}")
        raise


def run_skeleton(
    echo_fn: Optional[Callable[[str], None]] = None,
    schema_file: Optional[str] = None,
    output_file: str = "ki.yaml",
    additional_schemas: Optional[List[str]] = None,
) -> None:
    """Generate config skeleton with schema defaults.

    Args:
        echo_fn: Custom output function (defaults to print).
        schema_file: Path to JSON schema.
        output_file: Where to write skeleton (default: ki.yaml).
        additional_schemas: Additional schema files to merge.
    """
    if echo_fn is None:
        echo_fn = print

    try:
        from ki_core.schema_manager import get_schema_path
        from yaml_cfg_wizard import merge_schemas, scaffold_skeleton_from_schema

        base_schema = schema_file or get_schema_path()

        schemas_to_merge = [Path(base_schema)]
        if additional_schemas:
            schemas_to_merge.extend(Path(s) for s in additional_schemas)

        merged = merge_schemas(*[str(s) for s in schemas_to_merge])
        skeleton = scaffold_skeleton_from_schema(merged)

        write_skeleton_to_file(skeleton, output_file)
        echo_fn(f"✅ Config skeleton generated: {output_file}")

    except Exception as e:
        echo_fn(f"❌ Error generating skeleton: {e}")
        raise


def run_show(
    echo_fn: Optional[Callable[[str], None]] = None,
    config_file: Optional[str] = None,
    key: Optional[str] = None,
) -> None:
    """Show resolved config or specific key.

    Args:
        echo_fn: Custom output function (defaults to print).
        config_file: Path to config YAML file (or auto-detect).
        key: Specific top-level key to show (or all if None).
    """
    if echo_fn is None:
        echo_fn = print

    try:
        import yaml

        if not config_file:
            config_file = str(find_config_path())

        with open(config_file) as f:
            config = yaml.safe_load(f) or {}

        if key:
            if key in config:
                echo_fn(yaml.safe_dump({key: config[key]}, sort_keys=False))
            else:
                echo_fn(f"❌ Key '{key}' not found in config")
        else:
            echo_fn(yaml.safe_dump(config, sort_keys=False, default_flow_style=False))

    except Exception as e:
        echo_fn(f"❌ Error showing config: {e}")
        raise
