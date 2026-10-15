"""Stage management commands (list, set, active).

Manages which stage is active for the config resolution chain.
"""

from pathlib import Path
from typing import Callable, Optional


ACTIVE_STAGE_MARKER = ".active_stage"


def run_stage_list(
    echo_fn: Optional[Callable[[str], None]] = None,
    stages_dir: str = "config/stages",
) -> None:
    """List available stages.

    Args:
        echo_fn: Custom output function (defaults to print).
        stages_dir: Directory containing stage YAML files.
    """
    if echo_fn is None:
        echo_fn = print

    try:
        stages_path = Path(stages_dir)
        if not stages_path.exists():
            echo_fn(f"Stages directory not found: {stages_dir}")
            return

        stages = sorted([f.stem for f in stages_path.glob("*.yaml")] + 
                       [f.stem for f in stages_path.glob("*.yml")])
        
        if not stages:
            echo_fn("No stages found")
            return

        # Check which is active
        active_marker = stages_path / ACTIVE_STAGE_MARKER
        active_stage = None
        if active_marker.exists():
            active_stage = active_marker.read_text().strip()

        echo_fn("Available stages:")
        for stage in stages:
            marker = " ✓" if stage == active_stage else ""
            echo_fn(f"  - {stage}{marker}")
            
        if active_stage:
            echo_fn(f"\nActive stage: {active_stage}")
        else:
            echo_fn("\nNo active stage set")

    except Exception as e:
        echo_fn(f"❌ Error listing stages: {e}")
        raise


def run_stage_set(
    echo_fn: Optional[Callable[[str], None]] = None,
    stage_name: str = "",
    stages_dir: str = "config/stages",
) -> None:
    """Set active stage.

    Args:
        echo_fn: Custom output function (defaults to print).
        stage_name: Name of stage to activate (without .yaml/.yml).
        stages_dir: Directory containing stage YAML files.
    """
    if echo_fn is None:
        echo_fn = print

    try:
        stages_path = Path(stages_dir)
        stages_path.mkdir(parents=True, exist_ok=True)

        # Check if stage exists
        stage_file = stages_path / f"{stage_name}.yaml"
        if not stage_file.exists():
            stage_file = stages_path / f"{stage_name}.yml"
        
        if not stage_file.exists():
            echo_fn(f"❌ Stage not found: {stage_name}")
            return

        # Write active marker
        active_marker = stages_path / ACTIVE_STAGE_MARKER
        active_marker.write_text(stage_name)
        echo_fn(f"✅ Stage activated: {stage_name}")

    except Exception as e:
        echo_fn(f"❌ Error setting stage: {e}")
        raise


def run_stage_active(
    echo_fn: Optional[Callable[[str], None]] = None,
    stages_dir: str = "config/stages",
) -> None:
    """Show currently active stage.

    Args:
        echo_fn: Custom output function (defaults to print).
        stages_dir: Directory containing stage YAML files.
    """
    if echo_fn is None:
        echo_fn = print

    try:
        stages_path = Path(stages_dir)
        active_marker = stages_path / ACTIVE_STAGE_MARKER

        if active_marker.exists():
            active_stage = active_marker.read_text().strip()
            echo_fn(f"Active stage: {active_stage}")
        else:
            echo_fn("No active stage set")

    except Exception as e:
        echo_fn(f"❌ Error checking active stage: {e}")
        raise
