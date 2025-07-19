#!/usr/bin/env python3
"""
Test Chrome detection with VSCode minimized
"""

import os
import sys
import pyautogui
import time
from datetime import datetime

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_chrome_with_vscode_minimized():
    """Test Chrome detection now that VSCode is minimized"""
    
    print("=== CHROME TEST - VSCODE MINIMIZED ===")
    
    try:
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.operating_system.desktop_utils import DesktopUtils
        
        # Show desktop to ensure we're at anchor point
        print("🏠 Returning to desktop anchor point...")
        desktop_utils = DesktopUtils()
        desktop_utils.show_desktop()
        time.sleep(2)  # Wait for desktop to settle
        
        # Take screenshot with clear desktop
        print("📸 Taking screenshot with VSCode minimized...")
        screenshot_path = f"vscode_minimized_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(screenshot_path)
        print(f"Screenshot saved: {screenshot_path}")
        
        # Get screen dimensions
        screen_width, screen_height = pyautogui.size()
        print(f"Screen: {screen_width}x{screen_height}")
        
        # Initialize OmniParser
        print("🔍 Initializing OmniParser...")
        omniparser_manager = OmniParserServerManager()
        
        if not omniparser_manager.is_server_ready():
            print("Starting OmniParser server...")
            server_process = omniparser_manager.start_server()
            if not omniparser_manager.wait_for_server(timeout=30):
                print("❌ OmniParser failed to start")
                return False
        
        omniparser = omniparser_manager.get_interface()
        
        # Analyze with OmniParser
        print("🔍 Analyzing desktop with OmniParser...")
        results = omniparser.process_screenshot(screenshot_path)
        
        if not results:
            print("❌ No OmniParser results")
            return False
        
        print(f"✅ OmniParser found {len(results)} elements")
        
        # Look for Chrome with more keywords
        chrome_found = False
        chrome_candidates = []
        
        keywords = ['chrome', 'google', 'browser', 'google chrome']
        
        for i, item in enumerate(results):
            if isinstance(item, dict):
                text = item.get('text', '') if item.get('text') else ''
                for keyword in keywords:
                    if keyword in text.lower():
                        chrome_candidates.append((i, item, keyword))
                        chrome_found = True
                        print(f"🎯 CHROME FOUND! Item #{i}: '{text}' (matched: {keyword})")
                        
                        # Extract coordinates
                        if 'bbox_normalized' in item:
                            bbox = item['bbox_normalized']
                            if isinstance(bbox, list) and len(bbox) >= 4:
                                x1, y1, x2, y2 = bbox[:4]
                                center_x = int((x1 + x2) / 2 * screen_width)
                                center_y = int((y1 + y2) / 2 * screen_height)
                                print(f"   📍 Coordinates: ({center_x}, {center_y})")
                                
                                # Test click immediately
                                print(f"🖱️ TESTING CLICK at ({center_x}, {center_y})...")
                                pyautogui.click(center_x, center_y)
                                
                                # Check for Chrome
                                print("⏳ Checking for Chrome launch...")
                                time.sleep(3)
                                
                                import subprocess
                                result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                                                      capture_output=True, text=True)
                                if 'chrome.exe' in result.stdout:
                                    print("🎉 SUCCESS! Chrome launched!")
                                    return True
                                else:
                                    print("❌ Chrome not launched yet")
                        break
        
        if not chrome_found:
            print("❌ No Chrome detected in OmniParser results")
            print("📋 Showing first 10 detected elements for debugging:")
            for i, item in enumerate(results[:10]):
                if isinstance(item, dict):
                    text = item.get('text', '') if item.get('text') else ''
                    print(f"   #{i}: '{text}'")
        
        return chrome_found
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_chrome_with_vscode_minimized()
    print(f"\n🎯 RESULT: {'SUCCESS' if success else 'FAILED'}")
