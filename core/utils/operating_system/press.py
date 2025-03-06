import pyautogui
import time

def press(self, keys):
    try:
        if not keys or not isinstance(keys, list):
            print("[OperatingSystem][press] Invalid keys provided:", keys)
            return
        for key in keys:
            pyautogui.keyDown(key)
        time.sleep(0.1)
        for key in keys:
            pyautogui.keyUp(key)
    except Exception as e:
        print("[OperatingSystem][press] Error:", e)