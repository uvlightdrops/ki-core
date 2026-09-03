"""Config skeleton generation and schema merging utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from yaml_cfg_wizard import merge_schemas, scaffold_skeleton_from_schema, write_skeleton_to_file


def load_merged_schema(
    base_schema_path: str | Path,
    additional_schemas: Optional[list[str | Path]] = None,
) -> Dict[str, Any]:
    """Load and merge base schema with additional app-specific schemas.
    
    Args:
        base_schema_path: Path to base (ki-core) schema
        additional_schemas: List of additional schema paths to merge
    
    Returns:
        Merged schema dictionary
    """
    all_schemas = [base_schema_path]
    if additional_schemas:
        all_schemas.extend(additional_schemas)
    
    return merge_schemas(*all_schemas)


def generate_config_skeleton(
    schema_path: str | Path,
    output_path: str | Path,
    additional_schemas: Optional[list[str | Path]] = None,
) -> None:
    """Generate a config skeleton with defaults from merged schemas.
    
    Args:
        schema_path: Path to base schema
        output_path: Where to write the skeleton YAML
        additional_schemas: Additional schemas to merge
    """
    merged = load_merged_schema(schema_path, additional_schemas)
    skeleton = scaffold_skeleton_from_schema(merged)
    write_skeleton_to_file(skeleton, output_path)


def get_schema_path() -> Path:
    """Get path to ki-core base schema.
    
    The schema is packaged with ki-core as package data.
    """
    schema_path = Path(__file__).resolve().parent / "schema" / "config.schema.yaml"
    if schema_path.exists():
        return schema_path
    
    # Fallback for source tree
    fallback = Path(__file__).resolve().parents[2] / "schema" / "config.schema.yaml"
    if fallback.exists():
        return fallback
    
    # Default to package location
    return schema_path
