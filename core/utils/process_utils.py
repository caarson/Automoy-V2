"""
Process utility functions for Automoy.

This module provides functions for managing processes, including
checking if a process is running, killing process trees, and finding
processes by port.
"""

import os
import signal
import subprocess
import sys
from typing import Optional, List, Dict, Any

import psutil


def is_process_running(pid: int) -> bool:
    """
    Check if a process with the given PID is running.
    
    Args:
        pid: Process ID to check
    
    Returns:
        True if the process is running, False otherwise
    """
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


def kill_process_tree(pid: int, including_parent: bool = True) -> List[int]:
    """
    Kill a process and all its children.
    
    Args:
        pid: PID of the parent process to kill
        including_parent: If True, kill the parent process as well
    
    Returns:
        List of PIDs that were killed
    """
    killed_pids = []
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        
        # Kill children first
        for child in children:
            try:
                child.terminate()
                killed_pids.append(child.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Give children some time to terminate
        _, still_alive = psutil.wait_procs(children, timeout=5)
        
        # Force kill if still alive
        for child in still_alive:
            try:
                child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Kill parent if requested
        if including_parent:
            try:
                parent.terminate()
                killed_pids.append(parent.pid)
                
                # Give parent time to terminate
                parent.wait(timeout=5)
                
                # Force kill if still alive
                if parent.is_running():
                    parent.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        return killed_pids
    
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return killed_pids


def get_process_by_port(port: int) -> Optional[psutil.Process]:
    """
    Find the process that is using the given port.
    
    Args:
        port: Port number to check
    
    Returns:
        Process object if found, None otherwise
    """
    for conn in psutil.net_connections():
        if conn.laddr.port == port:
            try:
                return psutil.Process(conn.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return None
    
    return None
