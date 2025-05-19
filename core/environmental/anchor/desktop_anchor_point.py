import ctypes
import platform
import subprocess


def show_desktop():
    """Minimize all windows and show the desktop (Windows only)."""
    if platform.system() == "Windows":
        # Use Windows Shell to show desktop
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 6)  # Minimize console
        ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)  # Press Win key
        ctypes.windll.user32.keybd_event(0x44, 0, 0, 0)  # Press D key
        ctypes.windll.user32.keybd_event(0x44, 0, 2, 0)  # Release D key
        ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0)  # Release Win key
    else:
        # For other OS, not implemented
        raise NotImplementedError("Show desktop is only implemented for Windows.")


def minimize_all_windows():
    """Minimize all windows (Windows only)."""
    if platform.system() == "Windows":
        # Use PowerShell to minimize all windows
        subprocess.run([
            "powershell",
            "-Command",
            "(New-Object -ComObject Shell.Application).MinimizeAll()"
        ], check=True)
    else:
        raise NotImplementedError("Minimize all windows is only implemented for Windows.")


if __name__ == "__main__":
    # Example usage: show desktop and minimize all windows
    show_desktop()
    minimize_all_windows()
