"""Service Detector: Finds running services via PID/Port scanning."""

import os
import psutil
from typing import Optional, List, Dict
from pathlib import Path


class ServiceDetector:
    """Detect running services by PID and port."""

    @staticmethod
    def is_pid_running(pid: int) -> bool:
        """Check if a process with given PID is running.
        
        Args:
            pid: Process ID
        
        Returns:
            True if process exists, False otherwise
        """
        try:
            return psutil.pid_exists(pid)
        except Exception:
            return False

    @staticmethod
    def get_process_info(pid: int) -> Optional[Dict]:
        """Get process info by PID.
        
        Args:
            pid: Process ID
        
        Returns:
            Dict with 'name', 'cmdline', 'status', or None if not found
        """
        try:
            process = psutil.Process(pid)
            return {
                'pid': pid,
                'name': process.name(),
                'cmdline': ' '.join(process.cmdline()) if process.cmdline() else '',
                'status': process.status(),
                'create_time': process.create_time(),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    @staticmethod
    def is_port_listening(port: int) -> bool:
        """Check if a port is listening.
        
        Args:
            port: Port number
        
        Returns:
            True if port is listening, False otherwise
        """
        try:
            for conn in psutil.net_connections():
                if conn.laddr.port == port and conn.status == 'LISTEN':
                    return True
            return False
        except Exception:
            return False

    @staticmethod
    def find_process_by_port(port: int) -> Optional[int]:
        """Find PID listening on given port.
        
        Args:
            port: Port number
        
        Returns:
            PID if found, None otherwise
        """
        try:
            for conn in psutil.net_connections():
                if conn.laddr.port == port and conn.status == 'LISTEN':
                    return conn.pid
            return None
        except Exception:
            return None

    @staticmethod
    def find_process_by_cmdline(keyword: str) -> List[int]:
        """Find all processes matching command line keyword.
        
        Args:
            keyword: Search keyword (e.g., 'kicli_code_assist', 'vite')
        
        Returns:
            List of PIDs matching keyword
        """
        pids = []
        try:
            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if keyword.lower() in cmdline.lower():
                        pids.append(proc.info['pid'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        return pids

    @staticmethod
    def detect_service(name: str, port: Optional[int] = None, 
                      cmdline_keyword: Optional[str] = None) -> Optional[Dict]:
        """Detect a service by port or command line.
        
        Args:
            name: Service name (for reporting)
            port: Port to check (optional)
            cmdline_keyword: Command line keyword to search (optional)
        
        Returns:
            Dict with 'pid', 'port', 'running', 'info' or None if not found
        """
        pid = None
        
        # Try port first
        if port:
            pid = ServiceDetector.find_process_by_port(port)
        
        # Try command line keyword
        if not pid and cmdline_keyword:
            pids = ServiceDetector.find_process_by_cmdline(cmdline_keyword)
            if pids:
                pid = pids[0]  # Take first match
        
        if pid:
            info = ServiceDetector.get_process_info(pid)
            return {
                'name': name,
                'pid': pid,
                'port': port,
                'running': True,
                'info': info,
            }
        
        return None
