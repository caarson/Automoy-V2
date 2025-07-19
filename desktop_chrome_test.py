#!/usr/bin/env python3
"""
Desktop Chrome test - minimize windows and test on actual desktop
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

def desktop_chrome_test():
    """Test Chrome detection on actual desktop"""
    
    print("🖥️  Desktop Chrome Test")
    print("=" * 50)
    
    try:
        # Step 1: Minimize all windows to show desktop
        print("1. Minimizing all windows to show desktop...")
        import pyautogui
        pyautogui.hotkey('win', 'd')  # Show desktop
        time.sleep(2)
        print("   ✅ Desktop should now be visible")
        
        # Step 2: Take screenshot of desktop
        print("2. Taking desktop screenshot...")
        from core.utils.screenshot_utils import capture_screen_pil
        screenshot = capture_screen_pil()
        if not screenshot:
            print("   ❌ Screenshot failed")
            return False
        
        # Save desktop screenshot for inspection
        screenshot.save("desktop_screenshot.png")
        print(f"   ✅ Desktop screenshot saved: {screenshot.size}")
        
        # Step 3: Process with OmniParser
        print("3. Processing desktop with OmniParser...")
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        
        omniparser_manager = OmniParserServerManager()
        if not omniparser_manager.is_server_ready():
            print("   ❌ OmniParser not ready")
            return False
        
        omniparser = omniparser_manager.get_interface()
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
            screenshot.save(temp_path)
        
        try:
            parsed_result = omniparser.parse_screenshot(temp_path)
            if not parsed_result:
                print("   ❌ OmniParser failed")
                return False
            
            elements = parsed_result.get("parsed_content_list", [])
            print(f"   ✅ Found {len(elements)} desktop elements")
            
            # Step 4: Search for Chrome on desktop
            print("4. Searching for Chrome on desktop...")
            screen_width, screen_height = pyautogui.size()
            chrome_found = []
            
            for element in elements:
                content = element.get("content", "").lower()
                elem_type = element.get("type", "").lower()
                interactive = element.get("interactivity", False)
                bbox = element.get("bbox_normalized", [])
                
                # Look for Chrome
                is_chrome = (
                    "chrome" in content or
                    "google chrome" in content or
                    "google" in content or
                    (elem_type == "icon" and "browser" in content) or
                    (elem_type == "icon" and interactive and len(content) > 0 and 
                     any(word in content for word in ["chrome", "google", "web", "browser"]))
                )
                
                if is_chrome and bbox and not all(x == 0 for x in bbox):
                    x1, y1, x2, y2 = bbox
                    center_x = int((x1 + x2) / 2 * screen_width)
                    center_y = int((y1 + y2) / 2 * screen_height)
                    
                    chrome_found.append({
                        'text': content,
                        'coordinates': (center_x, center_y),
                        'type': elem_type,
                        'interactive': interactive
                    })
            
            if chrome_found:
                print(f"   🎯 Found {len(chrome_found)} Chrome candidates:")
                for i, candidate in enumerate(chrome_found):
                    print(f"     {i+1}. '{candidate['text']}' at {candidate['coordinates']} (type: {candidate['type']})")
                
                # Step 5: Click Chrome
                target = chrome_found[0]
                coords = target['coordinates']
                print(f"5. Clicking Chrome at {coords}...")
                
                pyautogui.click(coords[0], coords[1])
                print("   ✅ Click performed")
                
                # Step 6: Wait and verify
                print("6. Waiting for Chrome to launch...")
                time.sleep(4)
                
                result = subprocess.run(
                    ['powershell', '-Command', 'Get-Process chrome -ErrorAction SilentlyContinue'],
                    capture_output=True, text=True
                )
                
                if result.stdout.strip():
                    print("   🎉 SUCCESS! Chrome launched from desktop!")
                    lines = [line for line in result.stdout.strip().split('\n') if 'chrome' in line.lower()]
                    print(f"   📊 Chrome processes: {len(lines)}")
                    return True
                else:
                    print("   ❌ Chrome not detected after click")
                    return False
            else:
                print("   ❌ No Chrome found on desktop")
                print("   🔍 Available desktop icons:")
                icons = [e for e in elements if e.get("type", "").lower() == "icon"]
                interactive_icons = [e for e in elements if e.get("interactivity", False) and e.get("type", "").lower() == "icon"]
                
                print(f"     Total icons: {len(icons)}")
                print(f"     Interactive icons: {len(interactive_icons)}")
                
                for i, icon in enumerate(interactive_icons[:10]):
                    content = icon.get("content", "")[:30]
                    print(f"     {i+1}. '{content}'")
                
                # Alternative: Try taskbar Chrome
                print("   🔍 Searching taskbar for Chrome...")
                taskbar_chrome = []
                for element in elements:
                    content = element.get("content", "").lower()
                    if "chrome" in content or "google" in content:
                        taskbar_chrome.append(element)
                
                if taskbar_chrome:
                    print(f"   Found {len(taskbar_chrome)} Chrome elements in taskbar/other areas")
                    # Try clicking the first one
                    element = taskbar_chrome[0]
                    bbox = element.get("bbox_normalized", [])
                    if bbox and not all(x == 0 for x in bbox):
                        x1, y1, x2, y2 = bbox
                        center_x = int((x1 + x2) / 2 * screen_width)
                        center_y = int((y1 + y2) / 2 * screen_height)
                        
                        print(f"   Trying taskbar Chrome at ({center_x}, {center_y})...")
                        pyautogui.click(center_x, center_y)
                        time.sleep(3)
                        
                        result = subprocess.run(
                            ['powershell', '-Command', 'Get-Process chrome -ErrorAction SilentlyContinue'],
                            capture_output=True, text=True
                        )
                        
                        if result.stdout.strip():
                            print("   🎉 SUCCESS! Chrome launched from taskbar!")
                            return True
                
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
    success = desktop_chrome_test()
    print("\n" + "=" * 50)
    if success:
        print("✅ DESKTOP CHROME TEST PASSED!")
        print("✅ Chrome successfully detected and launched!")
    else:
        print("❌ DESKTOP CHROME TEST FAILED!")
        print("❌ Try ensuring Chrome icon is visible on desktop")
    print("=" * 50)
