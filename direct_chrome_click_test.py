#!/usr/bin/env python3
"""
Direct Chrome clicking test without OmniParser dependency
"""

import os
import sys
import time
import pyautogui
import psutil
from PIL import Image, ImageDraw

# Add project root to Python path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def is_chrome_running():
    """Check if Chrome is running"""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if 'chrome' in proc.info['name'].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

def find_and_click_chrome_icon():
    """Find and click Chrome icon using multiple strategies"""
    print("=== Direct Chrome Icon Clicking ===")
    
    # Strategy 1: Desktop shortcut
    print("\n1. Looking for Chrome desktop shortcut...")
    
    # Take screenshot
    screenshot = pyautogui.screenshot()
    screenshot.save("current_desktop.png")
    print("✅ Desktop screenshot saved as current_desktop.png")
    
    # Strategy 2: Try common desktop locations for Chrome icon
    print("\n2. Trying common Chrome icon locations...")
    
    # Get screen dimensions
    screen_width, screen_height = pyautogui.size()
    print(f"Screen size: {screen_width}x{screen_height}")
    
    # Common desktop icon locations (left side, arranged vertically)
    potential_locations = []
    
    # Left side of desktop (typical icon arrangement)
    for y in range(100, screen_height - 100, 80):  # Icons usually 80px apart
        potential_locations.append((100, y))  # Left margin
    
    # Check each potential location
    for i, (x, y) in enumerate(potential_locations[:10]):  # Check first 10 locations
        print(f"   Checking location {i+1}: ({x}, {y})")
        
        # Take a small screenshot around this location
        try:
            region = pyautogui.screenshot(region=(x-40, y-40, 80, 80))
            region.save(f"icon_check_{i+1}.png")
            
            # Simple click test at this location
            print(f"   Attempting click at ({x}, {y})")
            pyautogui.click(x, y)
            time.sleep(2)  # Wait for potential Chrome startup
            
            # Check if Chrome started
            if is_chrome_running():
                print(f"✅ SUCCESS! Chrome opened by clicking at ({x}, {y})")
                return True
                
        except Exception as e:
            print(f"   Error at location ({x}, {y}): {e}")
    
    # Strategy 3: Try taskbar
    print("\n3. Trying taskbar Chrome icon...")
    
    # Taskbar is usually at bottom, check common Chrome positions
    taskbar_y = screen_height - 40  # 40px from bottom
    for x in range(50, 500, 50):  # Check positions along taskbar
        print(f"   Trying taskbar position ({x}, {taskbar_y})")
        pyautogui.click(x, taskbar_y)
        time.sleep(2)
        
        if is_chrome_running():
            print(f"✅ SUCCESS! Chrome opened from taskbar at ({x}, {taskbar_y})")
            return True
    
    # Strategy 4: Start Menu + Chrome search
    print("\n4. Trying Start Menu search...")
    
    try:
        # Open start menu
        pyautogui.press('win')
        time.sleep(1)
        
        # Type "chrome"
        pyautogui.write('chrome')
        time.sleep(1)
        
        # Press Enter
        pyautogui.press('enter')
        time.sleep(3)
        
        if is_chrome_running():
            print("✅ SUCCESS! Chrome opened via Start Menu search")
            return True
        else:
            # Close start menu
            pyautogui.press('escape')
            
    except Exception as e:
        print(f"   Start menu error: {e}")
    
    return False

def main():
    """Main test function"""
    print("Starting direct Chrome clicking test...")
    
    # Check initial Chrome status
    if is_chrome_running():
        print("⚠ Chrome is already running. Proceeding anyway...")
    else:
        print("✅ Chrome is not running initially")
    
    # Attempt to click Chrome icon
    success = find_and_click_chrome_icon()
    
    # Final status check
    time.sleep(2)  # Give Chrome time to fully start
    final_chrome_status = is_chrome_running()
    
    print(f"\n=== FINAL RESULTS ===")
    print(f"Click attempt success: {success}")
    print(f"Chrome running after test: {final_chrome_status}")
    
    if final_chrome_status:
        print("🎉 OVERALL SUCCESS: Chrome is now running!")
        return True
    else:
        print("❌ OVERALL FAILURE: Chrome is not running")
        return False

if __name__ == "__main__":
    result = main()
    print(f"\nTest Result: {'PASSED' if result else 'FAILED'}")
