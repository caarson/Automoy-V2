#!/usr/bin/env python3
"""
Simple manual Chrome coordinate test
"""

import pyautogui
import subprocess
import time
from datetime import datetime

def simple_chrome_test():
    """Simple test that clicks coordinates and checks Chrome"""
    
    print("=== SIMPLE CHROME COORDINATE TEST ===")
    print(f"Started at: {datetime.now()}")
    
    # Get screen size
    width, height = pyautogui.size()
    print(f"Screen: {width}x{height}")
    
    # Check if Chrome is already running
    def check_chrome():
        try:
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                                  capture_output=True, text=True)
            is_running = 'chrome.exe' in result.stdout
            if is_running:
                print("🎉 CHROME IS RUNNING!")
            else:
                print("❌ Chrome not running")
            return is_running
        except:
            return False
    
    print("\n1. Initial Chrome check:")
    if check_chrome():
        return True
    
    # Test coordinates
    coordinates = [
        (100, 100),
        (150, 100), 
        (200, 100),
        (250, 100),
        (300, 100),
        (100, 150),
        (100, 200)
    ]
    
    print(f"\n2. Testing {len(coordinates)} coordinates:")
    for i, (x, y) in enumerate(coordinates):
        print(f"\n   Test #{i+1}: Clicking ({x}, {y})")
        
        try:
            pyautogui.click(x, y)
            print(f"   ✅ Click executed at ({x}, {y})")
            
            print("   ⏳ Waiting 3 seconds...")
            time.sleep(3)
            
            if check_chrome():
                print(f"   🎉 SUCCESS! Chrome launched from ({x}, {y})")
                return True
                
        except Exception as e:
            print(f"   ❌ Error clicking ({x}, {y}): {e}")
    
    print("\n3. Trying Start menu approach:")
    try:
        print("   Opening Start menu...")
        pyautogui.press('win')
        time.sleep(1)
        
        print("   Typing chrome...")
        pyautogui.typewrite('chrome')
        time.sleep(1)
        
        print("   Pressing Enter...")
        pyautogui.press('enter')
        time.sleep(4)
        
        if check_chrome():
            print("   🎉 SUCCESS! Chrome launched via Start menu")
            return True
            
    except Exception as e:
        print(f"   ❌ Start menu error: {e}")
    
    print("\n❌ ALL ATTEMPTS FAILED")
    return False

if __name__ == "__main__":
    success = simple_chrome_test()
    print(f"\n🎯 FINAL: {'SUCCESS' if success else 'FAILED'}")
    print(f"Ended at: {datetime.now()}")
