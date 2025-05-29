"""
Process and port utilities for Automoy.

This module provides utilities for checking and managing processes and ports,
particularly useful for ensuring clean startup and shutdown of services.
"""

import socket
import psutil
import logging
import platform
from typing import Optional, List

logger = logging.getLogger(__name__)


def is_process_running_on_port(port: int, host: str = "127.0.0.1") -> bool:
    """
    Check if a process is listening on the specified port.
    
    Args:
        port: The port number to check
        host: The host address to check (default: 127.0.0.1)
        
    Returns:
        True if a process is listening on the port, False otherwise
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            return result == 0
    except Exception as e:
        logger.debug(f"Error checking port {port}: {e}")
        return False


def kill_process_on_port(port: int, host: str = "127.0.0.1") -> bool:
    """
    Kill the process that is listening on the specified port.
    
    Args:
        port: The port number where the process is listening
        host: The host address to check (default: 127.0.0.1)
        
    Returns:
        True if the process was successfully killed, False otherwise
    """
    try:
        # Find processes listening on the port
        listening_processes = []
        
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                # Get connections separately to avoid attribute issues
                connections = proc.connections()
                if connections:
                    for conn in connections:
                        if (hasattr(conn, 'laddr') and 
                            conn.laddr and 
                            conn.laddr.port == port and
                            conn.laddr.ip in [host, '0.0.0.0', '::']):
                            listening_processes.append(proc.info['pid'])
                            break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        if not listening_processes:
            logger.info(f"No process found listening on port {port}")
            return True
        
        # Kill the processes
        killed_count = 0
        for pid in listening_processes:
            try:
                process = psutil.Process(pid)
                process_name = process.name()
                logger.info(f"Terminating process {process_name} (PID: {pid}) on port {port}")
                
                # Try graceful termination first
                process.terminate()
                
                # Wait for termination
                try:
                    process.wait(timeout=3)
                    logger.info(f"Process {process_name} (PID: {pid}) terminated gracefully")
                    killed_count += 1
                except psutil.TimeoutExpired:
                    # Force kill if graceful termination fails
                    logger.warning(f"Force killing process {process_name} (PID: {pid})")
                    process.kill()
                    process.wait(timeout=2)
                    logger.info(f"Process {process_name} (PID: {pid}) force killed")
                    killed_count += 1
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.warning(f"Could not kill process {pid}: {e}")
                continue
        
        logger.info(f"Successfully killed {killed_count} process(es) on port {port}")
        return killed_count > 0
        
    except Exception as e:
        logger.error(f"Error killing process on port {port}: {e}")
        return False


def get_processes_by_name(process_name: str) -> List[psutil.Process]:
    """
    Get all running processes with the specified name.
    
    Args:
        process_name: The name of the process to search for
        
    Returns:
        List of Process objects matching the name
    """
    processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == process_name.lower():
                processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return processes


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """
    Check if a port is available for binding.
    
    Args:
        port: The port number to check
        host: The host address to check (default: 127.0.0.1)
        
    Returns:
        True if the port is available, False if it's in use
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            return True
    except OSError:
        return False


def find_free_port(start_port: int = 8000, end_port: int = 9000, host: str = "127.0.0.1") -> Optional[int]:
    """
    Find a free port in the specified range.
    
    Args:
        start_port: The starting port number
        end_port: The ending port number
        host: The host address to check (default: 127.0.0.1)
        
    Returns:
        A free port number if found, None otherwise
    """
    for port in range(start_port, end_port + 1):
        if is_port_available(port, host):
            return port
    return None


def get_process_info_by_port(port: int, host: str = "127.0.0.1") -> Optional[dict]:
    """
    Get information about the process listening on a specific port.
    
    Args:
        port: The port number to check
        host: The host address to check (default: 127.0.0.1)
        
    Returns:
        Dictionary with process information if found, None otherwise
    """
    try:
        for proc in psutil.process_iter(['pid', 'name', 'connections', 'cmdline']):
            try:
                connections = proc.info['connections']
                if connections:
                    for conn in connections:
                        if (hasattr(conn, 'laddr') and 
                            conn.laddr and 
                            conn.laddr.port == port and
                            conn.laddr.ip in [host, '0.0.0.0', '::']):
                            return {
                                'pid': proc.info['pid'],
                                'name': proc.info['name'],
                                'cmdline': proc.info['cmdline'],
                                'port': port,
                                'host': conn.laddr.ip
                            }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        logger.error(f"Error getting process info for port {port}: {e}")
    
    return None
