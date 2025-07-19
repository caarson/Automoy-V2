"""
Simple click test - will create a result file
"""

import pyautogui
import subprocess
import time
from datetime import datetime

# Test clicking coordinates
result_log = []
result_log.append(f"Chrome click test started: {datetime.now()}")

try:
    # Get screen size
    width, height = pyautogui.size()
    result_log.append(f"Screen: {width}x{height}")
    
    # Check initial Chrome status
    try:
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                              capture_output=True, text=True)
        initial_chrome = 'chrome.exe' in result.stdout
        result_log.append(f"Initial Chrome status: {'RUNNING' if initial_chrome else 'NOT RUNNING'}")
    except:
        result_log.append("Initial Chrome check failed")
        initial_chrome = False
    
    if not initial_chrome:
        # Test coordinates
        coords = [(250, 100), (300, 100), (350, 100), (100, 150)]
        
        for i, (x, y) in enumerate(coords):
            result_log.append(f"Test {i+1}: Clicking ({x}, {y})")
            
            try:
                pyautogui.click(x, y)
                result_log.append(f"  Click executed at ({x}, {y})")
                
                time.sleep(3)
                
                # Check Chrome
                try:
                    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                                          capture_output=True, text=True)
                    chrome_running = 'chrome.exe' in result.stdout
                    
                    if chrome_running:
                        result_log.append(f"  SUCCESS: Chrome launched from ({x}, {y})!")
                        break
                    else:
                        result_log.append(f"  No Chrome after clicking ({x}, {y})")
                        
                except Exception as e:
                    result_log.append(f"  Error checking Chrome: {e}")
                    
            except Exception as e:
                result_log.append(f"  Click error at ({x}, {y}): {e}")
        
        # Try Start menu if no success
        if not any("SUCCESS" in line for line in result_log):
            result_log.append("Trying Start menu approach...")
            try:
                pyautogui.press('win')
                time.sleep(1)
                pyautogui.typewrite('chrome')
                time.sleep(1)
                pyautogui.press('enter')
                time.sleep(4)
                
                result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                                      capture_output=True, text=True)
                if 'chrome.exe' in result.stdout:
                    result_log.append("SUCCESS: Chrome launched via Start menu!")
                else:
                    result_log.append("Start menu approach failed")
                    
            except Exception as e:
                result_log.append(f"Start menu error: {e}")

except Exception as e:
    result_log.append(f"Test error: {e}")

result_log.append(f"Test completed: {datetime.now()}")

# Write results to file
with open("chrome_click_results.txt", "w") as f:
    for line in result_log:
        f.write(line + "\n")

print("Test completed - check chrome_click_results.txt")
