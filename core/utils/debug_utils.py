"""
Debug and logging utilities for Automoy.

This module provides functions for setting up logging and various debug information
collection functions to help diagnose issues with the application.
"""

import asyncio
import logging
import os
import platform
import socket
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Union

def setup_logging(
    logger_name: str = "Automoy",
    log_file_path: str = None,
    level: str = "INFO",
    max_bytes: int = 5 * 1024 * 1024,  # 5MB default
    backup_count: int = 3,  # 3 backup files by default
    format_str: str = "%(asctime)s - %(name)s - %(threadName)s - %(levelname)s - %(message)s",
    console_level: Optional[str] = None  # None means use the same as file level
) -> logging.Logger:
    """
    Set up logging for the application.

    Args:
        logger_name: The name of the logger.
        log_file_path: Path to log file. If None, only console logging is enabled.
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        max_bytes: Maximum size of log file in bytes before rotation.
        backup_count: Number of backup log files to keep.
        format_str: Log line format string.
        console_level: Console logging level. If None, same as file level.

    Returns:
        The configured logger instance.
    """
    # Convert string level to logging level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    console_numeric_level = getattr(logging, console_level.upper(), numeric_level) if console_level else numeric_level

    # Get or create the logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)  # Set to lowest level so handlers control

    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create formatters
    formatter = logging.Formatter(format_str)

    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Add file handler if log_file_path is provided
    if log_file_path:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

def log_current_thread_async_loop_info(logger: logging.Logger) -> None:
    """Log information about the current thread and its asyncio event loop (if any)."""
    thread = threading.current_thread()
    thread_info = f"Thread: {thread.name} (ID: {thread.ident})"
    
    try:
        loop = asyncio.get_event_loop()
        loop_info = f"Event loop: {loop}, running: {loop.is_running()}"
    except RuntimeError as e:
        loop_info = f"Event loop: Not available in this thread ({e})"
    
    logger.info(f"{thread_info}, {loop_info}")

def log_system_info(logger: logging.Logger) -> None:
    """Log information about the system."""
    logger.info(f"Platform: {platform.platform()}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Machine: {platform.machine()}")
    logger.info(f"Processor: {platform.processor()}")
    logger.info(f"Hostname: {socket.gethostname()}")
    
    try:
        import psutil
        # RAM info
        memory = psutil.virtual_memory()
        logger.info(f"Memory: Total: {memory.total / (1024**3):.2f} GB, Available: {memory.available / (1024**3):.2f} GB")
        
        # CPU info
        logger.info(f"CPU count: {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count(logical=True)} logical")
        logger.info(f"CPU usage: {psutil.cpu_percent(interval=1, percpu=False)}%")
        
        # Disk info
        disk = psutil.disk_usage('/')
        logger.info(f"Disk: Total: {disk.total / (1024**3):.2f} GB, Used: {disk.used / (1024**3):.2f} GB, Free: {disk.free / (1024**3):.2f} GB")
    except ImportError:
        logger.info("psutil not available, skipping detailed system info")

def log_python_environment_info(logger: logging.Logger) -> None:
    """Log information about the Python environment."""
    logger.info(f"PYTHONPATH: {sys.path}")
    
    try:
        import pip
        installed_packages = sorted([f"{pkg.key}=={pkg.version}" for pkg in pip._internal.metadata.get_environment_distributions()])
        logger.info(f"Installed packages: {installed_packages}")
    except (ImportError, AttributeError):
        logger.info("Could not retrieve installed packages list")

def log_webview_details(logger: logging.Logger, webview_window=None) -> None:
    """Log details about the PyWebview window configuration."""
    try:
        import webview
        logger.info(f"PyWebview version: {webview.__version__}")
        logger.info(f"Webview renderer: {webview.WEBVIEW_GTK or webview.WEBVIEW_COCOA or webview.WEBVIEW_EDGEHTML or webview.WEBVIEW_EDGECHROMIUM}")
        
        if webview_window:
            logger.info(f"Window URL: {webview_window.url}")
            logger.info(f"Window title: {webview_window.title}")
            logger.info(f"Window size: {webview_window.width}x{webview_window.height}")
            logger.info(f"Window position: ({webview_window.x}, {webview_window.y})")
    except ImportError:
        logger.info("PyWebview not available")
    except Exception as e:
        logger.error(f"Error getting webview details: {e}")

def log_gui_process_details(logger: logging.Logger, process=None) -> None:
    """Log details about the GUI subprocess."""
    if not process:
        logger.info("No GUI process provided")
        return
    
    logger.info(f"GUI process PID: {process.pid}")
    try:
        import psutil
        if psutil.pid_exists(process.pid):
            p = psutil.Process(process.pid)
            logger.info(f"GUI process status: {p.status()}")
            logger.info(f"GUI process CPU usage: {p.cpu_percent(interval=0.1)}%")
            logger.info(f"GUI process memory usage: {p.memory_info().rss / (1024*1024):.2f} MB")
            logger.info(f"GUI process command: {' '.join(p.cmdline())}")
        else:
            logger.info(f"GUI process {process.pid} does not exist")
    except ImportError:
        logger.info("psutil not available, skipping detailed process info")
    except Exception as e:
        logger.error(f"Error getting GUI process details: {e}")

def log_async_thread_details(logger: logging.Logger, thread=None) -> None:
    """Log details about an async operations thread."""
    if not thread:
        logger.info("No async thread provided")
        return
    
    logger.info(f"Async thread name: {thread.name}")
    logger.info(f"Async thread ID: {thread.ident}")
    logger.info(f"Async thread alive: {thread.is_alive()}")
    logger.info(f"Async thread daemon: {thread.daemon}")

def log_main_thread_details(logger: logging.Logger) -> None:
    """Log details about the main thread."""
    main_thread = threading.main_thread()
    logger.info(f"Main thread name: {main_thread.name}")
    logger.info(f"Main thread ID: {main_thread.ident}")
    logger.info(f"Main thread alive: {main_thread.is_alive()}")
    logger.info(f"Current thread is main thread: {threading.current_thread() is main_thread}")

def log_process_and_thread_info(logger: logging.Logger) -> None:
    """Log information about the current process and thread."""
    import os
    import threading
    try:
        logger.info(f"Process ID: {os.getpid()}")
        logger.info(f"Thread name: {threading.current_thread().name}")
        logger.info(f"Thread ID: {threading.get_ident()}")
        logger.info(f"Active thread count: {threading.active_count()}")
    except Exception as e:
        logger.warning(f"Could not log process/thread info: {e}")

def get_caller_info() -> str:
    """Get information about the caller function."""
    import inspect
    try:
        frame = inspect.currentframe().f_back
        return f"{frame.f_code.co_filename}:{frame.f_code.co_name}:{frame.f_lineno}"
    except Exception:
        return "unknown_caller"
