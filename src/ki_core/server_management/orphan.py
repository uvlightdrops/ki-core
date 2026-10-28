"""Orphan Detector: Finds ghost processes not in registry."""

from typing import List, Dict
from .registry import ServiceRegistry
from .detector import ServiceDetector


class OrphanDetector:
    """Detects and handles orphaned services."""

    def __init__(self, registry: ServiceRegistry):
        """Initialize orphan detector.
        
        Args:
            registry: ServiceRegistry instance
        """
        self.registry = registry
        self.detector = ServiceDetector()

    def detect_orphans(self) -> List[Dict]:
        """Find all orphaned services (PIDs in registry that don't exist).
        
        Returns:
            List of orphaned service dicts
        """
        orphans = []
        
        for service in self.registry.list_services():
            # Check if PID still exists
            if not self.detector.is_pid_running(service.pid):
                orphans.append({
                    'name': service.name,
                    'pid': service.pid,
                    'port': service.port,
                    'started_at': service.started_at,
                    'reason': 'Process not found',
                })
                # Mark in registry
                self.registry.mark_orphaned(service.name)
        
        return orphans

    def detect_ghost_processes(self, known_ports: List[int] = None) -> List[Dict]:
        """Find running processes not in registry (ghost processes).
        
        This is a basic heuristic - looks for common service patterns.
        
        Args:
            known_ports: List of ports to check for ghosts
        
        Returns:
            List of potential ghost processes
        """
        ghosts = []
        
        if known_ports:
            for port in known_ports:
                pid = self.detector.find_process_by_port(port)
                if pid:
                    # Check if this PID is in registry
                    found_in_registry = any(
                        s.pid == pid for s in self.registry.list_services()
                    )
                    
                    if not found_in_registry:
                        info = self.detector.get_process_info(pid)
                        ghosts.append({
                            'pid': pid,
                            'port': port,
                            'info': info,
                            'reason': 'Not in registry',
                        })
        
        return ghosts

    def cleanup_orphans(self) -> Dict:
        """Clean up orphaned services from registry.
        
        Returns:
            Dict with cleanup stats
        """
        orphans = []
        
        for service in self.registry.list_services():
            if not self.detector.is_pid_running(service.pid):
                orphans.append(service.name)
                self.registry.unregister(service.name)
        
        return {
            'cleaned': len(orphans),
            'services': orphans,
        }

    def sync_with_actual_processes(self, detection_config: List[Dict]) -> Dict:
        """Sync registry with actual running processes.
        
        Args:
            detection_config: List of dicts with 'name', 'port', 'cmdline_keyword'
        
        Returns:
            Dict with stats on synced, added, removed services
        """
        stats = {
            'synced': 0,
            'added': 0,
            'removed': 0,
            'errors': [],
        }
        
        # Check each configured service
        for config in detection_config:
            name = config.get('name')
            port = config.get('port')
            cmdline_keyword = config.get('cmdline_keyword')
            
            detected = self.detector.detect_service(
                name, port=port, cmdline_keyword=cmdline_keyword
            )
            
            if detected and detected['running']:
                existing = self.registry.get_service(name)
                if existing:
                    # Update existing
                    self.registry.register(
                        name, detected['pid'], port=port
                    )
                    stats['synced'] += 1
                else:
                    # Add new
                    self.registry.register(
                        name, detected['pid'], port=port
                    )
                    stats['added'] += 1
        
        # Clean up services not in detection_config
        configured_names = {c['name'] for c in detection_config}
        for service in self.registry.list_services():
            if service.name not in configured_names:
                self.registry.unregister(service.name)
                stats['removed'] += 1
        
        return stats
