import pyautogui
import time

def write(self, content):
    try:
        if not content:
            print("[OperatingSystem][write] No content provided to write.")
            return
        content = content.replace("\\n", "\n")
        pyautogui.write(content)
    except Exception as e:
        print("[OperatingSystem][write] Error:", e)