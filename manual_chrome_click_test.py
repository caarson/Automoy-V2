#!/usr/bin/env python3
"""
Manual Chrome click test to verify clicking works
"""

import pyautogui
import subprocess
import time
import os

def manual_chrome_click_test():
    """Manual test to find and click Chrome"""
    
    print("=== Manual Chrome Click Test ===")
    
    # Check current screen
    print("1. Getting screen info...")
    screen_width, screen_height = pyautogui.size()
    print(f"Screen size: {screen_width}x{screen_height}")
    
    # Take a screenshot to see desktop
    print("2. Taking screenshot...")
    screenshot = pyautogui.screenshot()
    screenshot.save("desktop_analysis.png")
    print("✓ Desktop screenshot saved as 'desktop_analysis.png'")
    
    # Common Chrome icon locations to try
    potential_locations = [
        # Taskbar locations (bottom of screen)
        (100, screen_height - 50),   # Far left taskbar
        (150, screen_height - 50),   # Left taskbar
        (200, screen_height - 50),   # Left-center taskbar
        (250, screen_height - 50),   # Center-left taskbar
        
        # Desktop locations (common spots)
        (50, 100),    # Top-left desktop
        (50, 150),    # Left desktop
        (100, 100),   # Top-left area
        (100, 150),   # Left area
        
        # Start menu button area
        (50, screen_height - 50),    # Start button
    ]
    
    print("3. Trying common Chrome icon locations...")
    
    for i, (x, y) in enumerate(potential_locations):
        print(f"   Trying location {i+1}: ({x}, {y})")
        
        # Click the location
        try:
            pyautogui.click(x, y)
            print(f"   ✓ Clicked ({x}, {y})")
            
            # Wait a moment
            time.sleep(2)
            
            # Check if Chrome launched
            try:
                result = subprocess.run(['powershell', 'Get-Process', '-Name', 'chrome', '-ErrorAction', 'SilentlyContinue'], 
                                      capture_output=True, text=True)
                if result.stdout.strip():
                    print(f"   🎉 SUCCESS! Chrome launched from click at ({x}, {y})")
                    return True
                else:
                    print(f"   ⚠ No Chrome process detected after click at ({x}, {y})")
                    
            except Exception as check_error:
                print(f"   ⚠ Error checking Chrome process: {check_error}")
                
        except Exception as click_error:
            print(f"   ✗ Error clicking ({x}, {y}): {click_error}")
    
    print("\n4. Trying alternative approach - Windows Start Menu...")
    
    # Try pressing Windows key and typing chrome
    try:
        print("   Pressing Windows key...")
        pyautogui.press('winleft')
        time.sleep(1)
        
        print("   Typing 'chrome'...")
        pyautogui.write('chrome')
        time.sleep(1)
        
        print("   Pressing Enter...")
        pyautogui.press('enter')
        time.sleep(3)
        
        # Check if Chrome launched
        result = subprocess.run(['powershell', 'Get-Process', '-Name', 'chrome', '-ErrorAction', 'SilentlyContinue'], 
                              capture_output=True, text=True)
        if result.stdout.strip():
            print("   🎉 SUCCESS! Chrome launched via Start Menu")
            return True
        else:
            print("   ⚠ Chrome not detected after Start Menu attempt")
            
    except Exception as start_error:
        print(f"   ✗ Start Menu approach failed: {start_error}")
    
    return False

if __name__ == "__main__":
    print("🚀 Starting manual Chrome click test...")
    print("⚠️  This will click various locations on your screen!")
    print("Press Ctrl+C within 5 seconds to cancel...")
    
    try:
        time.sleep(5)
        success = manual_chrome_click_test()
        
        print("\n" + "="*60)
        if success:
            print("✅ MANUAL CHROME CLICK TEST PASSED!")
            print("Chrome was successfully launched")
        else:
            print("❌ MANUAL CHROME CLICK TEST FAILED!")
            print("Could not launch Chrome with any method")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n❌ Test cancelled by user")
