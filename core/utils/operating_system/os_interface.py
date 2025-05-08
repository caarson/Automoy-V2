import platform
import pyautogui
import time
import ctypes
import mouse
import pyperclip
import pyscreeze
import keyboard
from typing import Union, Sequence


class OSInterface:
    def __init__(self):
        self.os_type = platform.system()
        if self.os_type not in ["Windows", "Linux", "Darwin"]:
            raise RuntimeError(f"Unsupported OS: {self.os_type}")

    # Press Keys or Type Text
    def press(self,
              keys: Union[str, Sequence[str]],
              interval: float = 0.05) -> None:
        """
        Simulates:
         • a simultaneous combo press if you pass a list/tuple of valid key names
         • a single key press if you pass a string that's a known key
         • or types the string literally if the 'key' isn't recognized.
        """
        try:
            # try real key-press
            if isinstance(keys, (list, tuple)):
                combo = "+".join(keys)
                keyboard.press_and_release(combo)
            else:
                keyboard.press(keys)
                time.sleep(interval)
                keyboard.release(keys)
        except ValueError:
            # fallback: type the literal text
            text = "".join(keys) if isinstance(keys, (list, tuple)) else keys
            self.type_text(text)

    def hotkey(self, *keys: str) -> None:
        """Simulates pressing multiple keys simultaneously (e.g., Ctrl+C)."""
        keyboard.press_and_release("+".join(keys))

    # Mouse Functions
    def move_mouse(self, x: int, y: int, duration: float = 0) -> None:
        """Moves the mouse to (x, y) over a specified duration."""
        pyautogui.moveTo(x, y, duration=duration)

    def click_mouse(self, button: str = "left") -> None:
        """Clicks the mouse using the specified button (left or right)."""
        if button == "left":
            mouse.click()
        elif button == "right":
            mouse.right_click()
        else:
            raise ValueError("Unsupported mouse button. Use 'left' or 'right'.")

    def drag_mouse(self, x: int, y: int, duration: float = 0.5) -> None:
        """Drags the mouse to a new position."""
        pyautogui.dragTo(x, y, duration=duration)

    # Typing and Clipboard Functions
    def type_text(self, text: str) -> None:
        """Types text into the active window."""
        pyautogui.write(text, interval=0.05)

    def copy_to_clipboard(self, text: str) -> None:
        """Copies text to the clipboard."""
        pyperclip.copy(text)

    def paste_from_clipboard(self) -> str:
        """Pastes text from the clipboard."""
        return pyperclip.paste()

    # Screenshot Functions
    def take_screenshot(self, filename: str = "screenshot.png") -> str:
        """Captures a screenshot and saves it to a file."""
        screenshot = pyautogui.screenshot()
        screenshot.save(filename)
        return filename

    def locate_on_screen(self, image: str, confidence: float = 0.8):
        """Locates an image on the screen with optional confidence threshold."""
        return pyscreeze.locateCenterOnScreen(image, confidence=confidence)

    # OS-Specific Functions
    def lock_screen(self) -> None:
        """Locks the screen (Windows only)."""
        if self.os_type == "Windows":
            ctypes.windll.user32.LockWorkStation()
        elif self.os_type == "Linux":
            import subprocess
            subprocess.run("xdg-screensaver lock", shell=True)
        elif self.os_type == "Darwin":
            import subprocess
            subprocess.run(
                "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession -suspend",
                shell=True
            )


if __name__ == "__main__":
    os_interface = OSInterface()
    print(f"Running on {os_interface.os_type}")
    os_interface.press(["win", "r"])
