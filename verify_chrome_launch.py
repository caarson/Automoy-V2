#!/usr/bin/env python3
"""
Direct Chrome launch test with terminal verification
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

def click_chrome_and_verify():
    """Click Chrome using OmniParser and verify via terminal"""
    
    print("🚀 Chrome Launch Test with Terminal Verification")
    print("=" * 60)
    
    try:
        # Step 1: Initialize OmniParser
        print("📡 Step 1: Initializing OmniParser...")
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.screenshot_utils import capture_screen_pil
        import pyautogui
        
        omniparser_manager = OmniParserServerManager()
        if omniparser_manager.is_server_ready():
            print("   ✅ OmniParser server is ready")
            omniparser = omniparser_manager.get_interface()
        else:
            print("   🔄 Starting OmniParser server...")
            server_process = omniparser_manager.start_server()
            if server_process and omniparser_manager.wait_for_server(timeout=60):
                print("   ✅ OmniParser server started successfully")
                omniparser = omniparser_manager.get_interface()
            else:
                print("   ❌ Failed to start OmniParser server")
                return False
        
        # Step 2: Capture and analyze screenshot
        print("\n📸 Step 2: Capturing screenshot for analysis...")
        screenshot = capture_screen_pil()
        if not screenshot:
            print("   ❌ Failed to capture screenshot")
            return False
        print(f"   ✅ Screenshot captured: {screenshot.size}")
        
        # Step 3: Process with OmniParser (using temporary file)
        print("\n🔍 Step 3: Analyzing screenshot with OmniParser...")
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
            screenshot.save(temp_path)
        
        try:
            parsed_result = omniparser.parse_screenshot(temp_path)
            if not parsed_result or "parsed_content_list" not in parsed_result:
                print("   ❌ OmniParser failed to parse screenshot")
                return False
            
            elements = parsed_result.get("parsed_content_list", [])
            print(f"   ✅ OmniParser detected {len(elements)} UI elements")
            
            # Step 4: Search for Chrome icon
            print("\n🔎 Step 4: Searching for Chrome icon...")
            screen_width, screen_height = pyautogui.size()
            chrome_targets = []
            
            for i, element in enumerate(elements):
                element_text = element.get("content", "").lower()
                element_type = element.get("type", "").lower()
                bbox = element.get("bbox_normalized", [])
                interactive = element.get("interactivity", False)
                
                # Enhanced Chrome detection
                is_chrome = (
                    "chrome" in element_text or
                    "google chrome" in element_text or
                    "google" in element_text or
                    ("browser" in element_text) or
                    (element_type == "icon" and interactive and "google" in element_text)
                )
                
                if is_chrome and bbox and not all(x == 0 for x in bbox):
                    x1, y1, x2, y2 = bbox
                    center_x = int((x1 + x2) / 2 * screen_width)
                    center_y = int((y1 + y2) / 2 * screen_height)
                    
                    chrome_targets.append({
                        'text': element_text,
                        'coords': (center_x, center_y),
                        'type': element_type
                    })
                    print(f"   🎯 Chrome found: '{element_text}' at ({center_x}, {center_y})")
            
            if not chrome_targets:
                print("   ❌ No Chrome icons found with valid coordinates")
                # Show some elements for debugging
                print("   Available interactive elements:")
                for i, element in enumerate(elements[:10]):
                    if element.get("interactivity", False):
                        print(f"     {i}: '{element.get('content', '')}' (type: {element.get('type', '')})")
                return False
            
            # Step 5: Click Chrome icon
            print(f"\n🖱️  Step 5: Clicking Chrome icon...")
            target = chrome_targets[0]  # Use first Chrome target found
            coords = target['coords']
            print(f"   Target: '{target['text']}' at {coords}")
            
            # Perform the click
            pyautogui.click(coords[0], coords[1])
            print(f"   ✅ Click performed at {coords}")
            
            # Step 6: Wait and verify via terminal
            print(f"\n⏳ Step 6: Waiting for Chrome to launch...")
            time.sleep(4)  # Give Chrome time to start
            
            # Step 7: Terminal verification
            print(f"\n🔍 Step 7: Verifying Chrome launch via terminal...")
            result = subprocess.run(
                ['powershell', '-Command', 'Get-Process -Name chrome -ErrorAction SilentlyContinue | Format-Table -AutoSize'],
                capture_output=True, 
                text=True
            )
            
            if result.stdout.strip():
                print("   🎉 SUCCESS! Chrome is running!")
                print("   Terminal output:")
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        print(f"     {line}")
                
                # Additional verification - count Chrome processes
                count_result = subprocess.run(
                    ['powershell', '-Command', '(Get-Process -Name chrome -ErrorAction SilentlyContinue).Count'],
                    capture_output=True,
                    text=True
                )
                if count_result.stdout.strip():
                    count = count_result.stdout.strip()
                    print(f"   📊 Chrome process count: {count}")
                
                return True
            else:
                print("   ❌ Chrome process not detected")
                print("   Checking for any browser processes...")
                
                # Check for other browsers
                browsers = ['chrome', 'firefox', 'edge', 'brave']
                for browser in browsers:
                    browser_result = subprocess.run(
                        ['powershell', '-Command', f'Get-Process -Name {browser} -ErrorAction SilentlyContinue'],
                        capture_output=True,
                        text=True
                    )
                    if browser_result.stdout.strip():
                        print(f"     Found {browser} running")
                
                return False
                
        finally:
            # Cleanup temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting Chrome launch test...")
    print("This will attempt to find and click the Chrome icon using OmniParser")
    print("Then verify the launch via terminal commands\n")
    
    success = click_chrome_and_verify()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ CHROME LAUNCH TEST PASSED!")
        print("Chrome was successfully launched and verified via terminal")
    else:
        print("❌ CHROME LAUNCH TEST FAILED!")
        print("Chrome was not launched or not detected")
    print("=" * 60)
