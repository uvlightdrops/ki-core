"""Profile management commands (list, set, active).

Manages which profile is active for the config resolution chain.
"""

from pathlib import Path
from typing import Callable, Optional


ACTIVE_PROFILE_MARKER = ".active_profile"


def run_profile_list(
    echo_fn: Optional[Callable[[str], None]] = None,
    profiles_dir: str = "config/profiles",
) -> None:
    """List available profiles.

    Args:
        echo_fn: Custom output function (defaults to print).
        profiles_dir: Directory containing profile YAML files.
    """
    if echo_fn is None:
        echo_fn = print

    try:
        profiles_path = Path(profiles_dir)
        if not profiles_path.exists():
            echo_fn(f"Profiles directory not found: {profiles_dir}")
            return

        profiles = sorted([f.stem for f in profiles_path.glob("*.yaml")] + 
                         [f.stem for f in profiles_path.glob("*.yml")])
        
        if not profiles:
            echo_fn("No profiles found")
            return

        # Check which is active
        active_marker = profiles_path / ACTIVE_PROFILE_MARKER
        active_profile = None
        if active_marker.exists():
            active_profile = active_marker.read_text().strip()

        echo_fn("Available profiles:")
        for profile in profiles:
            marker = " ✓" if profile == active_profile else ""
            echo_fn(f"  - {profile}{marker}")
            
        if active_profile:
            echo_fn(f"\nActive profile: {active_profile}")
        else:
            echo_fn("\nNo active profile set")

    except Exception as e:
        echo_fn(f"❌ Error listing profiles: {e}")
        raise


def run_profile_set(
    echo_fn: Optional[Callable[[str], None]] = None,
    profile_name: str = "",
    profiles_dir: str = "config/profiles",
) -> None:
    """Set active profile.

    Args:
        echo_fn: Custom output function (defaults to print).
        profile_name: Name of profile to activate (without .yaml/.yml).
        profiles_dir: Directory containing profile YAML files.
    """
    if echo_fn is None:
        echo_fn = print

    try:
        profiles_path = Path(profiles_dir)
        profiles_path.mkdir(parents=True, exist_ok=True)

        # Check if profile exists
        profile_file = profiles_path / f"{profile_name}.yaml"
        if not profile_file.exists():
            profile_file = profiles_path / f"{profile_name}.yml"
        
        if not profile_file.exists():
            echo_fn(f"❌ Profile not found: {profile_name}")
            return

        # Write active marker
        active_marker = profiles_path / ACTIVE_PROFILE_MARKER
        active_marker.write_text(profile_name)
        echo_fn(f"✅ Profile activated: {profile_name}")

    except Exception as e:
        echo_fn(f"❌ Error setting profile: {e}")
        raise


def run_profile_active(
    echo_fn: Optional[Callable[[str], None]] = None,
    profiles_dir: str = "config/profiles",
) -> None:
    """Show currently active profile.

    Args:
        echo_fn: Custom output function (defaults to print).
        profiles_dir: Directory containing profile YAML files.
    """
    if echo_fn is None:
        echo_fn = print

    try:
        profiles_path = Path(profiles_dir)
        active_marker = profiles_path / ACTIVE_PROFILE_MARKER

        if active_marker.exists():
            active_profile = active_marker.read_text().strip()
            echo_fn(f"Active profile: {active_profile}")
        else:
            echo_fn("No active profile set")

    except Exception as e:
        echo_fn(f"❌ Error checking active profile: {e}")
        raise
