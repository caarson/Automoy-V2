"""
Screenshot utilities for Automoy.

This module provides functions for capturing screenshots and getting information
about the active window or screen.
"""

import logging
import os
import platform
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any, Union

# Get a logger for this module
logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageGrab
    PILLOW_AVAILABLE = True
except ImportError:
    logger.warning("Pillow library not available, some screenshot functionality will be limited")
    PILLOW_AVAILABLE = False


def get_screen_size() -> Tuple[int, int]:
    """
    Get the screen size.
    
    Returns:
        Tuple of (width, height)
    """
    if not PILLOW_AVAILABLE:
        logger.error("Cannot get screen size without Pillow library")
        return (1920, 1080)  # Default fallback
    
    try:
        # Use a small screenshot to determine screen size
        img = ImageGrab.grab()
        return img.size
    except Exception as e:
        logger.error(f"Error getting screen size: {e}")
        return (1920, 1080)  # Default fallback


def capture_screen_pil(output_path: Optional[str] = None) -> Optional[Image.Image]:
    """
    Capture the screen using PIL.
    
    Args:
        output_path: Path to save the screenshot. If None, the screenshot is not saved.
    
    Returns:
        PIL Image object if successful, None otherwise
    """
    if not PILLOW_AVAILABLE:
        logger.error("Cannot capture screen without Pillow library")
        return None
    
    try:
        screenshot = ImageGrab.grab()
        
        if output_path:
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            screenshot.save(output_path)
            logger.info(f"Screenshot saved to {output_path}")
            
        return screenshot
    
    except Exception as e:
        logger.error(f"Error capturing screen: {e}")
        return None


def get_active_window_title() -> Optional[str]:
    """
    Get the title of the active window based on the current platform.
    
    Returns:
        Window title if available, None otherwise
    """
    if platform.system() == "Windows":
        return get_active_window_title_windows()
    elif platform.system() == "Darwin":
        return get_active_window_title_mac()
    elif platform.system() == "Linux":
        return get_active_window_title_linux()
    else:
        logger.warning(f"Unsupported platform for getting active window title: {platform.system()}")
        return None


def get_active_window_title_windows() -> Optional[str]:
    """
    Get the title of the active window on Windows.
    
    Returns:
        Window title if available, None otherwise
    """
    try:
        import win32gui
        window = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(window)
        return title if title else None
    except ImportError:
        logger.warning("win32gui not available, cannot get active window title on Windows")
        return None
    except Exception as e:
        logger.error(f"Error getting active window title on Windows: {e}")
        return None


def get_active_window_title_mac() -> Optional[str]:
    """
    Get the title of the active window on macOS.
    
    Returns:
        Window title if available, None otherwise
    """
    try:
        script = '''
        tell application "System Events"
            set frontApp to name of first application process whose frontmost is true
            tell process frontApp
                try
                    set windowTitle to name of front window
                on error
                    set windowTitle to ""
                end try
            end tell
        end tell
        return {frontApp & ": " & windowTitle}
        '''
        
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    
    except Exception as e:
        logger.error(f"Error getting active window title on macOS: {e}")
        return None


def get_active_window_title_linux() -> Optional[str]:
    """
    Get the title of the active window on Linux.
    
    Returns:
        Window title if available, None otherwise
    """
    try:
        # Try xdotool first
        try:
            result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'], 
                                  capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except FileNotFoundError:
            pass
        
        # Try xprop as backup
        try:
            result = subprocess.run(['xprop', '-id', '$(xprop -root _NET_ACTIVE_WINDOW | cut -d" " -f5)', 
                                   'WM_NAME'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                # Extract title from xprop output format: WM_NAME(STRING) = "Window Title"
                import re
                match = re.search(r'WM_NAME\(\w+\) = "(.*)"', result.stdout)
                if match:
                    return match.group(1)
        except FileNotFoundError:
            pass
        
        return None
    
    except Exception as e:
        logger.error(f"Error getting active window title on Linux: {e}")
        return None
