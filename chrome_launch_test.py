"""
Simple Chrome check - just try to launch Chrome directly to verify it works
"""

try:
    import subprocess
    import time
    
    print("Testing Chrome launch...")
    
    # Check if Chrome is already running
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                          capture_output=True, text=True)
    
    if 'chrome.exe' in result.stdout:
        print("Chrome is already running!")
    else:
        print("Chrome not running - attempting to launch via Start menu search")
        
        # Try launching Chrome via Windows search
        import pyautogui
        
        # Press Windows key
        pyautogui.press('win')
        time.sleep(1)
        
        # Type chrome
        pyautogui.typewrite('chrome')
        time.sleep(1)
        
        # Press enter
        pyautogui.press('enter')
        time.sleep(3)
        
        # Check again
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                              capture_output=True, text=True)
        
        if 'chrome.exe' in result.stdout:
            print("SUCCESS: Chrome launched via Start menu!")
        else:
            print("FAILED: Chrome did not launch")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("Chrome test complete")
