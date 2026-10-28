"""Service Controller: Manages service lifecycle (start, stop, restart)."""

import os
import subprocess
import signal
import time
from pathlib import Path
from typing import Optional, Dict, List
from .registry import ServiceRegistry
from .detector import ServiceDetector


class ServiceController:
    """Control service lifecycle: start, stop, restart."""

    def __init__(self, registry: ServiceRegistry, config: Optional[Dict] = None):
        """Initialize controller.
        
        Args:
            registry: ServiceRegistry instance
            config: Service configuration dict with 'services' key:
                {
                    'services': {
                        'backend': {
                            'command': 'python -m ...',
                            'cwd': '/path/to/dir',
                            'port': 8000,
                            'pidfile': '~/.kicli/pids/backend.pid'
                        }
                    }
                }
        """
        self.registry = registry
        self.detector = ServiceDetector()
        self.config = config or {}
        self.services_config = self.config.get('services', {})

    def start(self, service_name: str) -> Dict:
        """Start a service.
        
        Args:
            service_name: Name of service to start
        
        Returns:
            Dict with 'success', 'pid', 'message'
        """
        if service_name not in self.services_config:
            return {
                'success': False,
                'message': f"Service '{service_name}' not configured"
            }
        
        service_conf = self.services_config[service_name]
        command = service_conf.get('command')
        cwd = service_conf.get('cwd')
        pidfile = service_conf.get('pidfile')
        
        if not command:
            return {
                'success': False,
                'message': f"No command configured for '{service_name}'"
            }
        
        try:
            # Expand paths
            if cwd:
                cwd = os.path.expanduser(os.path.expandvars(cwd))
            
            # Start process
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            pid = process.pid
            
            # Give process time to start
            time.sleep(0.5)
            
            # Verify it's still running
            if not self.detector.is_pid_running(pid):
                return {
                    'success': False,
                    'pid': pid,
                    'message': f"Process started but exited immediately"
                }
            
            # Write pidfile if configured
            if pidfile:
                pidfile_path = Path(pidfile).expanduser()
                pidfile_path.parent.mkdir(parents=True, exist_ok=True)
                pidfile_path.write_text(str(pid))
            
            # Register in registry
            self.registry.register(
                service_name,
                pid,
                port=service_conf.get('port'),
                metadata={'command': command, 'cwd': cwd}
            )
            
            return {
                'success': True,
                'pid': pid,
                'service': service_name,
                'message': f"Started '{service_name}' (PID {pid})"
            }
        
        except Exception as e:
            return {
                'success': False,
                'service': service_name,
                'message': f"Failed to start: {str(e)}"
            }

    def stop(self, service_name: str, force: bool = False) -> Dict:
        """Stop a service.
        
        Args:
            service_name: Name of service to stop
            force: If True, use SIGKILL instead of SIGTERM
        
        Returns:
            Dict with 'success', 'message'
        """
        service = self.registry.get_service(service_name)
        if not service:
            return {
                'success': False,
                'message': f"Service '{service_name}' not registered"
            }
        
        pid = service.pid
        
        try:
            # Check if process exists
            if not self.detector.is_pid_running(pid):
                self.registry.unregister(service_name)
                return {
                    'success': True,
                    'service': service_name,
                    'message': f"Service '{service_name}' already stopped"
                }
            
            # Send signal
            signal_to_use = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, signal_to_use)
            
            # Wait for process to die (with timeout)
            timeout = 5.0
            start_time = time.time()
            while self.detector.is_pid_running(pid):
                if time.time() - start_time > timeout:
                    if not force:
                        # Try harder
                        os.kill(pid, signal.SIGKILL)
                        time.sleep(0.5)
                    break
                time.sleep(0.1)
            
            # Update registry
            self.registry.unregister(service_name)
            
            # Clean up pidfile
            service_conf = self.services_config.get(service_name, {})
            pidfile = service_conf.get('pidfile')
            if pidfile:
                pidfile_path = Path(pidfile).expanduser()
                try:
                    pidfile_path.unlink()
                except:
                    pass
            
            return {
                'success': True,
                'service': service_name,
                'message': f"Stopped '{service_name}' (PID {pid})"
            }
        
        except Exception as e:
            return {
                'success': False,
                'service': service_name,
                'message': f"Failed to stop: {str(e)}"
            }

    def restart(self, service_name: str) -> Dict:
        """Restart a service (stop + start).
        
        Args:
            service_name: Name of service to restart
        
        Returns:
            Dict with 'success', 'message'
        """
        # Stop
        stop_result = self.stop(service_name)
        if not stop_result.get('success'):
            return {
                'success': False,
                'service': service_name,
                'message': f"Failed to stop during restart: {stop_result.get('message')}"
            }
        
        # Wait a moment
        time.sleep(1.0)
        
        # Start
        start_result = self.start(service_name)
        
        return {
            'success': start_result.get('success'),
            'service': service_name,
            'pid': start_result.get('pid'),
            'message': f"Restarted '{service_name}': {start_result.get('message')}"
        }

    def get_config(self, service_name: str) -> Optional[Dict]:
        """Get service configuration."""
        return self.services_config.get(service_name)

    def list_configured_services(self) -> List[str]:
        """List all configured services."""
        return list(self.services_config.keys())
