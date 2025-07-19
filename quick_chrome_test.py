#!/usr/bin/env python3
"""
Quick Chrome launch test
"""

import os
import sys
import tempfile
import time
import subprocess
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def quick_chrome_test():
    print("🚀 Quick Chrome Test")
    print("=" * 40)
    
    try:
        # Step 1: Check if Chrome is already running
        print("1. Checking current Chrome status...")
        result = subprocess.run(
            ['powershell', '-Command', 'Get-Process -Name chrome -ErrorAction SilentlyContinue'],
            capture_output=True, 
            text=True
        )
        
        if result.stdout.strip():
            print("   ⚠️  Chrome is already running")
            print("   Killing existing Chrome processes...")
            subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                         capture_output=True, text=True)
            time.sleep(2)
        else:
            print("   ✅ No Chrome processes found")
        
        # Step 2: Import required modules
        print("2. Importing required modules...")
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.screenshot_utils import capture_screen_pil
        import pyautogui
        print("   ✅ All modules imported successfully")
        
        # Step 3: Initialize OmniParser
        print("3. Initializing OmniParser...")
        omniparser_manager = OmniParserServerManager()
        if not omniparser_manager.is_server_ready():
            print("   🔄 Starting OmniParser server...")
            server_process = omniparser_manager.start_server()
            if not omniparser_manager.wait_for_server(timeout=30):
                print("   ❌ Failed to start OmniParser")
                return False
        
        omniparser = omniparser_manager.get_interface()
        print("   ✅ OmniParser ready")
        
        # Step 4: Capture screenshot
        print("4. Capturing screenshot...")
        screenshot = capture_screen_pil()
        if not screenshot:
            print("   ❌ Failed to capture screenshot")
            return False
        print(f"   ✅ Screenshot captured: {screenshot.size}")
        
        # Step 5: Find Chrome
        print("5. Searching for Chrome...")
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
            screenshot.save(temp_path)
        
        try:
            parsed_result = omniparser.parse_screenshot(temp_path)
            if not parsed_result:
                print("   ❌ OmniParser returned no results")
                return False
            
            elements = parsed_result.get("parsed_content_list", [])
            print(f"   📋 Found {len(elements)} UI elements")
            
            # Find Chrome
            screen_width, screen_height = pyautogui.size()
            chrome_found = None
            
            for element in elements:
                text = element.get("content", "").lower()
                if "chrome" in text and element.get("interactivity", False):
                    bbox = element.get("bbox_normalized", [])
                    if bbox and not all(x == 0 for x in bbox):
                        x1, y1, x2, y2 = bbox
                        center_x = int((x1 + x2) / 2 * screen_width)
                        center_y = int((y1 + y2) / 2 * screen_height)
                        chrome_found = (center_x, center_y, text)
                        break
            
            if not chrome_found:
                print("   ❌ Chrome icon not found")
                # Show some elements for debugging
                print("   Available elements:")
                for i, element in enumerate(elements[:5]):
                    print(f"     {element.get('content', '')[:50]} (interactive: {element.get('interactivity', False)})")
                return False
            
            x, y, text = chrome_found
            print(f"   🎯 Chrome found: '{text}' at ({x}, {y})")
            
            # Step 6: Click Chrome
            print("6. Clicking Chrome...")
            pyautogui.click(x, y)
            print(f"   ✅ Clicked at ({x}, {y})")
            
            # Step 7: Wait and check
            print("7. Waiting for Chrome to start...")
            for i in range(5):
                time.sleep(1)
                result = subprocess.run(
                    ['powershell', '-Command', 'Get-Process -Name chrome -ErrorAction SilentlyContinue'],
                    capture_output=True,
                    text=True
                )
                if result.stdout.strip():
                    print(f"   🎉 SUCCESS! Chrome launched after {i+1} seconds")
                    print("   Chrome processes:")
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            print(f"     {line}")
                    return True
                print(f"   ⏳ Waiting... ({i+1}/5)")
            
            print("   ❌ Chrome did not start within 5 seconds")
            return False
            
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = quick_chrome_test()
    print("\n" + "=" * 40)
    if success:
        print("✅ CHROME TEST PASSED!")
    else:
        print("❌ CHROME TEST FAILED!")
    print("=" * 40)
