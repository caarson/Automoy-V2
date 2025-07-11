import ctypes
import platform
import subprocess
import time
import logging

logger = logging.getLogger(__name__)

def show_desktop():
    """Minimize all windows and show the desktop (Windows only)."""
    if platform.system() == "Windows":
        try:
            logger.info("Returning to desktop anchor point - minimizing all windows")
            
            # Method 1: Use Windows API to minimize all windows
            minimize_all_windows_api()
            time.sleep(0.5)
            
            # Method 2: Fallback to PowerShell if API method fails
            minimize_all_windows()
            time.sleep(0.5)
            
            # Method 3: Ensure desktop is focused
            focus_desktop()
            
            logger.info("Desktop anchor point established successfully")
            
        except Exception as e:
            logger.error(f"Error returning to desktop anchor point: {e}")
            # Continue execution even if desktop anchor fails
    else:
        # For other OS, not implemented
        raise NotImplementedError("Show desktop is only implemented for Windows.")

def minimize_all_windows_api():
    """Minimize all windows using Windows API (Windows only)."""
    if platform.system() == "Windows":
        try:
            # Get the desktop window
            desktop_hwnd = ctypes.windll.user32.GetDesktopWindow()
            
            # Use Shell API to minimize all windows
            shell32 = ctypes.windll.shell32
            shell32.SHGetDesktopFolder()
            
            # Alternative: Use ShowWindow with SW_MINIMIZE on all visible windows
            user32 = ctypes.windll.user32
            
            # Minimize all visible windows
            def enum_window_callback(hwnd, lParam):
                if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
                    # Don't minimize the desktop itself
                    if hwnd != desktop_hwnd:
                        user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
                return True
            
            # Define the callback type
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            callback = EnumWindowsProc(enum_window_callback)
            
            # Enumerate all windows
            user32.EnumWindows(callback, 0)
            
            logger.debug("Windows minimized using API method")
            
        except Exception as e:
            logger.warning(f"API method for minimizing windows failed: {e}")
            raise

def minimize_all_windows():
    """Minimize all windows using PowerShell (Windows only)."""
    if platform.system() == "Windows":
        # Use PowerShell to minimize all windows
        try:
            subprocess.run([
                "powershell",
                "-Command",
                "(New-Object -ComObject Shell.Application).MinimizeAll()"
            ], check=True, capture_output=True, text=True, timeout=5)
            logger.debug("Minimized all windows via PowerShell.")
        except subprocess.TimeoutExpired:
            logger.warning("PowerShell minimize command timed out after 5 seconds")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to minimize all windows using PowerShell: {e}")
            logger.debug(f"PowerShell stdout: {e.stdout}")
            logger.debug(f"PowerShell stderr: {e.stderr}")
        except FileNotFoundError:
            logger.warning("PowerShell not found. Cannot minimize all windows.")
    else:
        raise NotImplementedError("Minimize all windows is only implemented for Windows.")

def focus_desktop():
    """Focus the desktop to ensure clean state."""
    if platform.system() == "Windows":
        try:
            # Click on the desktop to ensure it's focused
            user32 = ctypes.windll.user32
            
            # Get desktop window
            desktop_hwnd = user32.GetDesktopWindow()
            
            # Get desktop dimensions
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)
            
            # Click on an empty area of the desktop (bottom-right corner)
            click_x = screen_width - 50
            click_y = screen_height - 50
            
            # Set cursor position and click
            user32.SetCursorPos(click_x, click_y)
            user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
            user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
            
            logger.debug("Desktop focused via click")
            
        except Exception as e:
            logger.warning(f"Failed to focus desktop: {e}")


if __name__ == "__main__":
    # Example usage: show desktop
    print("Attempting to show desktop...")
    show_desktop()
    print("Desktop should now be visible, with all (other) windows minimized.")
    # To test restoration, you would manually restore a window or use pygetwindow
    # For example, find a specific window and restore it.
    # import pygetwindow as gw
    # import time
    # time.sleep(3)
    # try:
    #   notepad = gw.getWindowsWithTitle('Untitled - Notepad')[0] # Example
    #   if notepad:
    #       notepad.restore()
    #       notepad.activate()
    #       print("Notepad restored and activated.")
    # except IndexError:
    #   print("Notepad not found to test restoration.")
