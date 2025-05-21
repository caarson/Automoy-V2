import ctypes
import platform
import subprocess


def show_desktop():
    """Minimize all windows and show the desktop (Windows only)."""
    if platform.system() == "Windows":
        # Minimize the console window first
        console_window = ctypes.windll.kernel32.GetConsoleWindow()
        if console_window:
            ctypes.windll.user32.ShowWindow(console_window, 6)  # SW_MINIMIZE value is 6

        # Then minimize all other windows using the Shell.Application object
        minimize_all_windows()
    else:
        # For other OS, not implemented
        raise NotImplementedError("Show desktop is only implemented for Windows.")


def minimize_all_windows():
    """Minimize all windows (Windows only)."""
    if platform.system() == "Windows":
        # Use PowerShell to minimize all windows
        try:
            subprocess.run([
                "powershell",
                "-Command",
                "(New-Object -ComObject Shell.Application).MinimizeAll()"
            ], check=True, capture_output=True, text=True)
            print("[INFO] Minimized all windows via PowerShell.")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to minimize all windows using PowerShell: {e}")
            print(f"Stdout: {e.stdout}")
            print(f"Stderr: {e.stderr}")
            # Fallback or alternative method could be considered here if needed
        except FileNotFoundError:
            print("[ERROR] PowerShell not found. Cannot minimize all windows.")
    else:
        raise NotImplementedError("Minimize all windows is only implemented for Windows.")


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
