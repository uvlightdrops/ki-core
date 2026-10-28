"""Server management commands for KI ecosystem.

Handles service registration, lifecycle tracking, and orphan detection.
Works across all projects and can manage any service (backend, frontend, etc).
"""

from typing import Callable, Optional, List, Dict
from pathlib import Path


def run_server_status(
    echo_fn: Optional[Callable[[str], None]] = None,
    verbose: bool = False,
) -> Dict:
    """Show status of all registered services.
    
    Args:
        echo_fn: Custom output function (defaults to print).
        verbose: Show detailed info per service.
    
    Returns:
        Dict with service status data.
    """
    # Import here to avoid circular dependencies
    from kicli_code_assist.server_management import ServiceRegistry, ServiceDetector
    
    if echo_fn is None:
        echo_fn = print
    
    registry = ServiceRegistry()
    detector = ServiceDetector()
    services = registry.list_services()
    
    if not services:
        echo_fn("No services registered.")
        return {"services": [], "counts": {"total": 0}}
    
    echo_fn(f"\n{'Service':<20} {'PID':<10} {'Port':<8} {'Status':<12} {'Running'}")
    echo_fn("-" * 70)
    
    running_count = 0
    orphaned_count = 0
    
    for service in services:
        is_running = detector.is_pid_running(service.pid)
        status = service.status
        running_marker = "✓" if is_running else "✗"
        
        if is_running:
            running_count += 1
        if status == "orphaned":
            orphaned_count += 1
        
        echo_fn(
            f"{service.name:<20} {service.pid:<10} "
            f"{(service.port or '-'):<8} {status:<12} {running_marker}"
        )
        
        if verbose and service.metadata:
            echo_fn(f"  Metadata: {service.metadata}")
            echo_fn(f"  Started: {service.started_at}")
    
    echo_fn("-" * 70)
    echo_fn(
        f"Total: {len(services)} | "
        f"Running: {running_count} | "
        f"Orphaned: {orphaned_count}"
    )
    
    return {
        "services": registry.to_dict(),
        "counts": {
            "total": len(services),
            "running": running_count,
            "orphaned": orphaned_count,
        }
    }


def run_server_register(
    name: str,
    pid: int,
    port: Optional[int] = None,
    echo_fn: Optional[Callable[[str], None]] = None,
) -> bool:
    """Register a new service.
    
    Args:
        name: Service name.
        pid: Process ID.
        port: Port number (optional).
        echo_fn: Custom output function.
    
    Returns:
        True if successful.
    """
    from kicli_code_assist.server_management import ServiceRegistry
    
    if echo_fn is None:
        echo_fn = print
    
    registry = ServiceRegistry()
    
    try:
        entry = registry.register(name, pid, port=port)
        echo_fn(
            f"✓ Registered: {name} (PID {pid}, Port {port or 'N/A'})"
        )
        return True
    except Exception as e:
        echo_fn(f"✗ Failed to register {name}: {e}")
        return False


def run_server_unregister(
    name: str,
    echo_fn: Optional[Callable[[str], None]] = None,
) -> bool:
    """Unregister a service.
    
    Args:
        name: Service name.
        echo_fn: Custom output function.
    
    Returns:
        True if successful.
    """
    from kicli_code_assist.server_management import ServiceRegistry
    
    if echo_fn is None:
        echo_fn = print
    
    registry = ServiceRegistry()
    
    if registry.unregister(name):
        echo_fn(f"✓ Unregistered: {name}")
        return True
    else:
        echo_fn(f"✗ Service not found: {name}")
        return False


def run_server_detect_orphans(
    echo_fn: Optional[Callable[[str], None]] = None,
) -> Dict:
    """Detect orphaned services (PIDs that don't exist).
    
    Args:
        echo_fn: Custom output function.
    
    Returns:
        Dict with orphan data.
    """
    from kicli_code_assist.server_management import (
        ServiceRegistry, OrphanDetector
    )
    
    if echo_fn is None:
        echo_fn = print
    
    registry = ServiceRegistry()
    detector = OrphanDetector(registry)
    orphans = detector.detect_orphans()
    
    if not orphans:
        echo_fn("✓ No orphaned services found.")
        return {"orphaned_count": 0, "orphans": []}
    
    echo_fn(f"\n⚠ Found {len(orphans)} orphaned service(s):\n")
    echo_fn(f"{'Service':<20} {'PID':<10} {'Port':<8} {'Reason'}")
    echo_fn("-" * 50)
    
    for orphan in orphans:
        echo_fn(
            f"{orphan['name']:<20} {orphan['pid']:<10} "
            f"{(orphan.get('port') or '-'):<8} {orphan['reason']}"
        )
    
    echo_fn()
    return {
        "orphaned_count": len(orphans),
        "orphans": orphans,
    }


def run_server_cleanup(
    echo_fn: Optional[Callable[[str], None]] = None,
) -> Dict:
    """Clean up orphaned services from registry.
    
    Args:
        echo_fn: Custom output function.
    
    Returns:
        Dict with cleanup stats.
    """
    from kicli_code_assist.server_management import (
        ServiceRegistry, OrphanDetector
    )
    
    if echo_fn is None:
        echo_fn = print
    
    registry = ServiceRegistry()
    detector = OrphanDetector(registry)
    result = detector.cleanup_orphans()
    
    cleaned = result['cleaned']
    
    if cleaned == 0:
        echo_fn("✓ No orphaned services to clean up.")
    else:
        echo_fn(f"\n✓ Cleaned up {cleaned} orphaned service(s):\n")
        for service_name in result['services']:
            echo_fn(f"  - {service_name}")
        echo_fn()
    
    return result


def run_server_sync(
    detection_config: Optional[List[Dict]] = None,
    echo_fn: Optional[Callable[[str], None]] = None,
) -> Dict:
    """Sync registry with actual running processes.
    
    Args:
        detection_config: List of service configs to detect.
                         Each dict should have: name, port, cmdline_keyword
        echo_fn: Custom output function.
    
    Returns:
        Dict with sync stats.
    """
    from kicli_code_assist.server_management import (
        ServiceRegistry, OrphanDetector
    )
    
    if echo_fn is None:
        echo_fn = print
    
    if detection_config is None:
        # Default detection config
        detection_config = [
            {
                "name": "kicli-backend",
                "port": 8000,
                "cmdline_keyword": "kicli_code_assist.web.server",
            },
            {
                "name": "frontend",
                "port": 3000,
                "cmdline_keyword": "vite",
            },
        ]
    
    registry = ServiceRegistry()
    detector = OrphanDetector(registry)
    stats = detector.sync_with_actual_processes(detection_config)
    
    echo_fn("\n📊 Sync Results:")
    echo_fn(f"  Synced: {stats['synced']}")
    echo_fn(f"  Added: {stats['added']}")
    echo_fn(f"  Removed: {stats['removed']}")
    
    if stats['errors']:
        echo_fn(f"\n⚠ Errors:")
        for error in stats['errors']:
            echo_fn(f"  - {error}")
    
    echo_fn()
    
    # Show updated status
    return run_server_status(echo_fn=echo_fn)
