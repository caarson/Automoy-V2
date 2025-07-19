#!/usr/bin/env python3
"""
Direct coordinate test - force click and verify Chrome
"""

import pyautogui
import subprocess
import time

def force_chrome_click_test():
    """Force click coordinates and verify Chrome opens"""
    
    print("=== FORCE CHROME CLICK TEST ===")
    
    def check_chrome():
        try:
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                                  capture_output=True, text=True)
            chrome_running = 'chrome.exe' in result.stdout
            print(f"Chrome status: {'RUNNING' if chrome_running else 'NOT RUNNING'}")
            return chrome_running
        except Exception as e:
            print(f"Error checking Chrome: {e}")
            return False
    
    print("Initial Chrome check:")
    if check_chrome():
        print("Chrome already running!")
        return True
    
    # Test specific coordinates
    coords = [(250, 100), (300, 100), (350, 100), (400, 100), (100, 150), (150, 150)]
    
    for i, (x, y) in enumerate(coords):
        print(f"\nTest #{i+1}: Clicking ({x}, {y})")
        
        try:
            # Execute click
            pyautogui.click(x, y)
            print(f"✅ CLICK EXECUTED at ({x}, {y})")
            
            # Wait for Chrome
            print("Waiting 3 seconds for Chrome...")
            time.sleep(3)
            
            # Check Chrome
            if check_chrome():
                print(f"🎉 SUCCESS! Chrome launched from coordinate ({x}, {y})")
                return True
            else:
                print(f"❌ No Chrome after clicking ({x}, {y})")
                
        except Exception as e:
            print(f"❌ Click error at ({x}, {y}): {e}")
    
    # Final fallback - Start menu
    print("\nFallback: Start menu approach")
    try:
        pyautogui.press('win')
        time.sleep(1)
        pyautogui.typewrite('chrome')
        time.sleep(1)
        pyautogui.press('enter')
        time.sleep(4)
        
        if check_chrome():
            print("✅ SUCCESS via Start menu!")
            return True
        else:
            print("❌ Start menu approach failed")
            
    except Exception as e:
        print(f"❌ Start menu error: {e}")
    
    print("❌ ALL ATTEMPTS FAILED")
    return False

if __name__ == "__main__":
    success = force_chrome_click_test()
    print(f"\nFINAL RESULT: {'SUCCESS' if success else 'FAILED'}")
