"""Service Registry: Persistent JSON-based service tracking."""

import json
import time
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ServiceEntry:
    """Single service entry in registry."""
    name: str
    pid: int
    port: Optional[int] = None
    status: str = 'running'  # running, stopped, orphaned
    started_at: str = None
    last_checked: str = None
    metadata: Dict = None

    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.now().isoformat()
        if self.metadata is None:
            self.metadata = {}


class ServiceRegistry:
    """Persistent service registry using JSON."""

    def __init__(self, registry_path: Optional[Path] = None):
        """Initialize registry.
        
        Args:
            registry_path: Path to JSON registry file. Defaults to ~/.kicli/services.json
        """
        if registry_path is None:
            registry_path = Path.home() / '.kicli' / 'services.json'
        
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        """Load registry from disk."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, 'r') as f:
                    data = json.load(f)
                    self.services: Dict[str, ServiceEntry] = {
                        name: ServiceEntry(**entry) 
                        for name, entry in data.items()
                    }
            except (json.JSONDecodeError, TypeError):
                self.services = {}
        else:
            self.services = {}

    def _save(self):
        """Save registry to disk."""
        data = {
            name: {
                **asdict(entry),
                'started_at': entry.started_at,
                'last_checked': entry.last_checked,
            }
            for name, entry in self.services.items()
        }
        with open(self.registry_path, 'w') as f:
            json.dump(data, f, indent=2)

    def register(self, name: str, pid: int, port: Optional[int] = None, 
                 metadata: Optional[Dict] = None) -> ServiceEntry:
        """Register a new service.
        
        Args:
            name: Service name (e.g., 'kicli-backend', 'frontend')
            pid: Process ID
            port: Port number (optional)
            metadata: Additional metadata (optional)
        
        Returns:
            ServiceEntry
        """
        entry = ServiceEntry(
            name=name,
            pid=pid,
            port=port,
            status='running',
            metadata=metadata or {}
        )
        self.services[name] = entry
        self._save()
        return entry

    def unregister(self, name: str) -> bool:
        """Unregister a service.
        
        Returns:
            True if service was registered, False otherwise
        """
        if name in self.services:
            del self.services[name]
            self._save()
            return True
        return False

    def update_status(self, name: str, status: str) -> Optional[ServiceEntry]:
        """Update service status.
        
        Args:
            name: Service name
            status: New status (running, stopped, orphaned)
        
        Returns:
            Updated ServiceEntry or None if not found
        """
        if name in self.services:
            entry = self.services[name]
            entry.status = status
            entry.last_checked = datetime.now().isoformat()
            self._save()
            return entry
        return None

    def get_service(self, name: str) -> Optional[ServiceEntry]:
        """Get service by name."""
        return self.services.get(name)

    def list_services(self, status: Optional[str] = None) -> List[ServiceEntry]:
        """List all services, optionally filtered by status.
        
        Args:
            status: Filter by status (running, stopped, orphaned). None = all
        
        Returns:
            List of ServiceEntry objects
        """
        services = self.services.values()
        if status:
            services = [s for s in services if s.status == status]
        return list(services)

    def get_running_services(self) -> List[ServiceEntry]:
        """Get all running services."""
        return self.list_services(status='running')

    def get_orphaned_services(self) -> List[ServiceEntry]:
        """Get all orphaned services."""
        return self.list_services(status='orphaned')

    def mark_orphaned(self, name: str) -> Optional[ServiceEntry]:
        """Mark a service as orphaned."""
        return self.update_status(name, 'orphaned')

    def clear(self):
        """Clear all services from registry."""
        self.services = {}
        self._save()

    def to_dict(self) -> Dict:
        """Export registry as dict (for API responses)."""
        return {
            name: {
                'name': entry.name,
                'pid': entry.pid,
                'port': entry.port,
                'status': entry.status,
                'started_at': entry.started_at,
                'last_checked': entry.last_checked,
                'metadata': entry.metadata,
            }
            for name, entry in self.services.items()
        }
