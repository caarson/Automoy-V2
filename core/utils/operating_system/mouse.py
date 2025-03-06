import pyautogui
import time

def mouse(self, click_detail, region=None):
    try:
        x = convert_percent_to_decimal(click_detail.get("x"))
        y = convert_percent_to_decimal(click_detail.get("y"))

        screen_width, screen_height = pyautogui.size()
        x_pixel = int(screen_width * float(x))
        y_pixel = int(screen_height * float(y))

        if region:
            x1, y1, x2, y2 = region
            if not (x1 <= x_pixel <= x2 and y1 <= y_pixel <= y2):
                print(f"Click at ({x_pixel}, {y_pixel}) ignored (out of bounds).")
                return  # Skip the action if out of bounds

        print(f"Mouse click at ({x_pixel}, {y_pixel}) within region.")
        pyautogui.click(x_pixel, y_pixel)

    except Exception as e:
        print("[OperatingSystem][mouse] Error:", e)