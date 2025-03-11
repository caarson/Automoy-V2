import platform
import pyautogui
import time
import ctypes
import keyboard
import mouse
import pyperclip
import pyscreeze

class OSInterface:
    def __init__(self):
        self.os_type = platform.system()
        if self.os_type not in ["Windows", "Linux", "Darwin"]:
            raise RuntimeError(f"Unsupported OS: {self.os_type}")

    # Press Keys
    def press(self, key, interval=0.1):
        """Simulates a key press with an optional delay."""
        keyboard.press(key)
        time.sleep(interval)
        keyboard.release(key)

    def hotkey(self, *keys):
        """Simulates pressing multiple keys simultaneously (e.g., Ctrl+C)."""
        keyboard.press_and_release("+".join(keys))

    # Mouse Functions
    def move_mouse(self, x, y, duration=0):
        """Moves the mouse to (x, y) over a specified duration."""
        pyautogui.moveTo(x, y, duration=duration)

    def click_mouse(self, button="left"):
        """Clicks the mouse using the specified button (left or right)."""
        if button == "left":
            mouse.click()
        elif button == "right":
            mouse.right_click()
        else:
            raise ValueError("Unsupported mouse button. Use 'left' or 'right'.")

    def drag_mouse(self, x, y, duration=0.5):
        """Drags the mouse to a new position."""
        pyautogui.dragTo(x, y, duration=duration)

    # Typing and Clipboard Functions
    def type_text(self, text):
        """Types text into the active window."""
        pyautogui.write(text, interval=0.05)

    def copy_to_clipboard(self, text):
        """Copies text to the clipboard."""
        pyperclip.copy(text)

    def paste_from_clipboard(self):
        """Pastes text from the clipboard."""
        return pyperclip.paste()

    # Screenshot Functions
    def take_screenshot(self, filename="screenshot.png"):
        """Captures a screenshot and saves it to a file."""
        screenshot = pyautogui.screenshot()
        screenshot.save(filename)
        return filename

    def locate_on_screen(self, image, confidence=0.8):
        """Locates an image on the screen with optional confidence threshold."""
        return pyscreeze.locateCenterOnScreen(image, confidence=confidence)

    # OS-Specific Functions
    def lock_screen(self):
        """Locks the screen (Windows only)."""
        if self.os_type == "Windows":
            ctypes.windll.user32.LockWorkStation()
        elif self.os_type == "Linux":
            subprocess.run("xdg-screensaver lock", shell=True)
        elif self.os_type == "Darwin":
            subprocess.run("/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession -suspend", shell=True)
            
if __name__ == "__main__":
    os_interface = OSInterface()
    print(f"Running on {os_interface.os_type}")
