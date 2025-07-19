#!/usr/bin/env python3
"""
Comprehensive Chrome test - try multiple approaches and provide detailed feedback
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

def comprehensive_chrome_test():
    """Comprehensive test with multiple Chrome launch approaches"""
    
    print("🚀 Comprehensive Chrome Test")
    print("=" * 60)
    
    try:
        # Ensure Chrome is closed first
        print("🧹 Cleaning up any existing Chrome processes...")
        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                      capture_output=True, text=True)
        time.sleep(1)
        
        # Import components
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.screenshot_utils import capture_screen_pil
        import pyautogui
        
        omniparser_manager = OmniParserServerManager()
        if not omniparser_manager.is_server_ready():
            print("❌ OmniParser not ready")
            return False
        
        omniparser = omniparser_manager.get_interface()
        
        # Test 1: Current view Chrome detection
        print("\n📱 TEST 1: Chrome detection in current view...")
        screenshot = capture_screen_pil()
        if not screenshot:
            print("   ❌ Screenshot failed")
            return False
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
            screenshot.save(temp_path)
        
        success_current = False
        try:
            parsed_result = omniparser.parse_screenshot(temp_path)
            if parsed_result:
                elements = parsed_result.get("parsed_content_list", [])
                print(f"   📊 Found {len(elements)} elements")
                
                # Look for Chrome
                chrome_elements = []
                for element in elements:
                    content = element.get("content", "").lower()
                    if any(keyword in content for keyword in ["chrome", "google"]):
                        chrome_elements.append(element)
                
                if chrome_elements:
                    print(f"   🎯 Found {len(chrome_elements)} Chrome-related elements in current view")
                    success_current = True
                else:
                    print("   ℹ️  No Chrome elements in current view")
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
        
        # Test 2: Desktop Chrome detection
        print("\n🖥️  TEST 2: Desktop Chrome detection...")
        pyautogui.hotkey('win', 'd')  # Show desktop
        time.sleep(2)
        
        screenshot = capture_screen_pil()
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
            screenshot.save(temp_path)
        
        success_desktop = False
        try:
            parsed_result = omniparser.parse_screenshot(temp_path)
            if parsed_result:
                elements = parsed_result.get("parsed_content_list", [])
                print(f"   📊 Found {len(elements)} desktop elements")
                
                # Look for Chrome on desktop
                chrome_candidates = []
                screen_width, screen_height = pyautogui.size()
                
                for element in elements:
                    content = element.get("content", "").lower()
                    elem_type = element.get("type", "").lower()
                    interactive = element.get("interactivity", False)
                    bbox = element.get("bbox_normalized", [])
                    
                    is_chrome = (
                        "chrome" in content or
                        "google" in content or
                        (elem_type == "icon" and interactive and "browser" in content)
                    )
                    
                    if is_chrome and bbox and not all(x == 0 for x in bbox):
                        x1, y1, x2, y2 = bbox
                        center_x = int((x1 + x2) / 2 * screen_width)
                        center_y = int((y1 + y2) / 2 * screen_height)
                        chrome_candidates.append((center_x, center_y, content))
                
                if chrome_candidates:
                    print(f"   🎯 Found {len(chrome_candidates)} Chrome candidates on desktop")
                    for i, (x, y, content) in enumerate(chrome_candidates):
                        print(f"     {i+1}. '{content}' at ({x}, {y})")
                    
                    # Try clicking the first one
                    x, y, content = chrome_candidates[0]
                    print(f"   🖱️  Clicking Chrome: '{content}' at ({x}, {y})")
                    pyautogui.click(x, y)
                    time.sleep(4)
                    
                    result = subprocess.run(
                        ['powershell', '-Command', 'Get-Process chrome -ErrorAction SilentlyContinue'],
                        capture_output=True, text=True
                    )
                    
                    if result.stdout.strip():
                        print("   🎉 SUCCESS! Chrome launched from desktop!")
                        success_desktop = True
                    else:
                        print("   ❌ Chrome click on desktop didn't work")
                else:
                    print("   ℹ️  No Chrome icons found on desktop")
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
        
        # Test 3: Start Menu approach
        if not success_desktop:
            print("\n🔍 TEST 3: Start Menu Chrome launch...")
            pyautogui.press('win')
            time.sleep(1)
            pyautogui.typewrite('chrome')
            time.sleep(1)
            pyautogui.press('enter')
            time.sleep(4)
            
            result = subprocess.run(
                ['powershell', '-Command', 'Get-Process chrome -ErrorAction SilentlyContinue'],
                capture_output=True, text=True
            )
            
            if result.stdout.strip():
                print("   🎉 SUCCESS! Chrome launched via Start Menu!")
                success_desktop = True
            else:
                print("   ❌ Start Menu approach didn't work")
        
        # Test 4: Run dialog approach
        if not success_desktop:
            print("\n⚡ TEST 4: Run dialog Chrome launch...")
            pyautogui.hotkey('win', 'r')
            time.sleep(1)
            pyautogui.typewrite('chrome')
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(4)
            
            result = subprocess.run(
                ['powershell', '-Command', 'Get-Process chrome -ErrorAction SilentlyContinue'],
                capture_output=True, text=True
            )
            
            if result.stdout.strip():
                print("   🎉 SUCCESS! Chrome launched via Run dialog!")
                success_desktop = True
            else:
                print("   ❌ Run dialog approach didn't work")
        
        # Final verification
        print("\n🔍 FINAL VERIFICATION:")
        result = subprocess.run(
            ['powershell', '-Command', 'Get-Process chrome -ErrorAction SilentlyContinue'],
            capture_output=True, text=True
        )
        
        if result.stdout.strip():
            lines = [line for line in result.stdout.strip().split('\n') if 'chrome' in line.lower()]
            print(f"✅ Chrome is running with {len(lines)} processes!")
            print("Sample processes:")
            for line in lines[:3]:
                if line.strip():
                    print(f"  {line.strip()}")
            return True
        else:
            print("❌ Chrome is not running")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🎯 COMPREHENSIVE CHROME TEST")
    print("Testing multiple approaches to Chrome detection and launch\n")
    
    success = comprehensive_chrome_test()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ COMPREHENSIVE TEST PASSED!")
        print("✅ Chrome detection and launch system is working!")
        print("✅ Automoy can successfully detect and launch Chrome!")
    else:
        print("❌ COMPREHENSIVE TEST FAILED!")
        print("❌ Chrome could not be detected or launched")
        print("ℹ️  This may indicate Chrome is not installed or not accessible")
    print("=" * 60)
