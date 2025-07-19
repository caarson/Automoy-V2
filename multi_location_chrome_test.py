#!/usr/bin/env python3
"""
Chrome clicking test - multiple screen locations
"""

import os
import sys
import time
import subprocess
import tempfile
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_chrome_clicking():
    """Test Chrome clicking in multiple locations"""
    
    print("🎯 Chrome Clicking Test - Multiple Locations")
    print("=" * 60)
    
    try:
        # Close Chrome first
        print("🧹 Ensuring Chrome is closed...")
        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                      capture_output=True, text=True)
        time.sleep(1)
        
        # Import components
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.screenshot_utils import capture_screen_pil
        import pyautogui
        
        omniparser_manager = OmniParserServerManager()
        omniparser = omniparser_manager.get_interface()
        
        # Test different screen locations
        locations = [
            ("current", lambda: None),  # Current view
            ("desktop", lambda: [pyautogui.hotkey('win', 'd'), time.sleep(3)]),  # Desktop
            ("taskbar", lambda: [pyautogui.press('escape'), time.sleep(1)])  # Taskbar
        ]
        
        for location_name, setup_func in locations:
            print(f"\n📍 Testing {location_name.upper()} view...")
            
            # Setup the view
            if setup_func:
                setup_func()
            
            # Take screenshot
            screenshot = capture_screen_pil()
            if not screenshot:
                print(f"   ❌ Screenshot failed for {location_name}")
                continue
            
            screenshot.save(f"{location_name}_screenshot.png")
            print(f"   📸 {location_name} screenshot saved")
            
            # Process with OmniParser
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_path = temp_file.name
                screenshot.save(temp_path)
            
            try:
                parsed_result = omniparser.parse_screenshot(temp_path)
                if not parsed_result:
                    print(f"   ❌ OmniParser failed for {location_name}")
                    continue
                
                elements = parsed_result.get("parsed_content_list", [])
                print(f"   📊 Found {len(elements)} elements in {location_name}")
                
                # Look for Chrome with enhanced detection
                screen_width, screen_height = pyautogui.size()
                chrome_found = []
                
                for element in elements:
                    content = element.get("content", "").lower()
                    elem_type = element.get("type", "").lower() 
                    interactive = element.get("interactivity", False)
                    bbox = element.get("bbox_normalized", [])
                    
                    # Enhanced Chrome detection
                    is_chrome = (
                        "chrome" in content or
                        "google chrome" in content or
                        ("google" in content and interactive) or
                        ("browser" in content and interactive) or
                        (elem_type == "icon" and interactive and len(content) > 0)
                    )
                    
                    if is_chrome and bbox and not all(x == 0 for x in bbox):
                        x1, y1, x2, y2 = bbox
                        center_x = int((x1 + x2) / 2 * screen_width)
                        center_y = int((y1 + y2) / 2 * screen_height)
                        
                        chrome_found.append({
                            'text': content,
                            'coords': (center_x, center_y),
                            'type': elem_type
                        })
                
                if chrome_found:
                    print(f"   🎯 Found {len(chrome_found)} Chrome targets in {location_name}:")
                    for i, target in enumerate(chrome_found):
                        print(f"     {i+1}. '{target['text']}' at {target['coords']} ({target['type']})")
                    
                    # Click the first target
                    target = chrome_found[0]
                    coords = target['coords']
                    print(f"   🖱️  CLICKING: '{target['text']}' at {coords}")
                    
                    pyautogui.click(coords[0], coords[1])
                    print("   ✅ Mouse click performed!")
                    
                    # Wait and verify
                    print("   ⏳ Checking if Chrome launched...")
                    time.sleep(4)
                    
                    result = subprocess.run(
                        ['powershell', '-Command', 'Get-Process chrome -ErrorAction SilentlyContinue'],
                        capture_output=True, text=True
                    )
                    
                    if result.stdout.strip():
                        print(f"   🎉 SUCCESS! Chrome launched from {location_name}!")
                        chrome_count = len([line for line in result.stdout.strip().split('\n') if 'chrome' in line.lower()])
                        print(f"   📊 Chrome processes running: {chrome_count}")
                        return True
                    else:
                        print(f"   ❌ Chrome didn't launch from {location_name}")
                else:
                    print(f"   ❌ No Chrome targets found in {location_name}")
                    # Show available interactive elements
                    interactive = [e for e in elements if e.get("interactivity", False)]
                    print(f"     Available interactive elements: {len(interactive)}")
                    for i, elem in enumerate(interactive[:5]):
                        content = elem.get("content", "")[:25]
                        elem_type = elem.get("type", "")
                        print(f"       {i+1}. '{content}' ({elem_type})")
                    
            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass
        
        return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_chrome_clicking()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ CHROME CLICKING SUCCESSFUL!")
        print("✅ Chrome was found and clicked (no keyboard shortcuts)")
    else:
        print("❌ CHROME CLICKING FAILED!")
        print("❌ Could not find or click Chrome icon")
    print("=" * 60)
