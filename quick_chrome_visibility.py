#!/usr/bin/env python3
"""
Quick Chrome visibility test
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def quick_chrome_test():
    """Quick test to see if Chrome icon is visible"""
    
    print("=== Quick Chrome Visibility Test ===")
    
    try:
        from core.utils.screenshot_utils import capture_screen_pil
        import pyautogui
        
        # Capture screenshot
        print("1. Capturing screenshot...")
        screenshot = capture_screen_pil()
        if screenshot:
            print(f"✓ Screenshot captured: {screenshot.size}")
            
            # Save screenshot for manual inspection
            screenshot.save("current_desktop.png")
            print("✓ Screenshot saved as 'current_desktop.png'")
        else:
            print("✗ Failed to capture screenshot")
            return False
            
        # Get screen info
        screen_width, screen_height = pyautogui.size()
        print(f"Screen size: {screen_width}x{screen_height}")
        
        print("\n✓ Basic screenshot test completed!")
        print("Please check 'current_desktop.png' to see if Chrome icon is visible")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    quick_chrome_test()
