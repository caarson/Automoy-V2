#!/usr/bin/env python3
"""
Immediate Chrome click test - desktop should be clear now
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

def immediate_chrome_test():
    """Immediate Chrome test with desktop clear"""
    
    try:
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        
        print("🖥️ Desktop should be clear - starting immediate Chrome test...")
        
        # Get screen dimensions
        screen_width, screen_height = pyautogui.size()
        print(f"Screen: {screen_width}x{screen_height}")
        
        # Initialize OmniParser
        omniparser_manager = OmniParserServerManager()
        
        if not omniparser_manager.is_server_ready():
            print("Starting OmniParser...")
            server_process = omniparser_manager.start_server()
            if not omniparser_manager.wait_for_server(timeout=30):
                print("❌ OmniParser failed to start")
                return False
        
        omniparser = omniparser_manager.get_interface()
        
        # Take immediate screenshot
        print("📸 Taking screenshot of current desktop...")
        screenshot_path = f"immediate_chrome_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(screenshot_path)
        print(f"Screenshot saved: {screenshot_path}")
        
        # Quick analysis
        print("🔍 Analyzing with OmniParser...")
        results = omniparser.process_screenshot(screenshot_path)
        
        if not results:
            print("❌ No OmniParser results")
            return False
        
        print(f"✅ Found {len(results)} elements")
        
        # Find Chrome quickly
        chrome_coords = None
        for i, item in enumerate(results):
            if isinstance(item, dict):
                text = item.get('text', '') if item.get('text') else ''
                if any(keyword in text.lower() for keyword in ['chrome', 'google']):
                    print(f"🎯 Found Chrome: '{text}'")
                    
                    # Get coordinates
                    if 'bbox_normalized' in item:
                        bbox = item['bbox_normalized']
                        if isinstance(bbox, list) and len(bbox) >= 4:
                            x1, y1, x2, y2 = bbox[:4]
                            center_x = int((x1 + x2) / 2 * screen_width)
                            center_y = int((y1 + y2) / 2 * screen_height)
                            chrome_coords = (center_x, center_y)
                            print(f"📍 Coords: ({center_x}, {center_y})")
                            break
                    
                    elif 'bbox' in item:
                        bbox = item['bbox']
                        if isinstance(bbox, list) and len(bbox) >= 4:
                            x1, y1, x2, y2 = bbox[:4]
                            center_x = int((x1 + x2) / 2)
                            center_y = int((y1 + y2) / 2)
                            chrome_coords = (center_x, center_y)
                            print(f"📍 Coords: ({center_x}, {center_y})")
                            break
        
        if chrome_coords:
            x, y = chrome_coords
            print(f"🖱️ CLICKING at ({x}, {y})...")
            
            # Validate coordinates
            if 0 <= x <= screen_width and 0 <= y <= screen_height:
                pyautogui.click(x, y)
                print("✅ Click executed!")
                
                # Wait and check
                print("⏳ Waiting 4 seconds for Chrome to start...")
                time.sleep(4)
                
                # Check for Chrome process
                import subprocess
                result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                                      capture_output=True, text=True)
                if 'chrome.exe' in result.stdout:
                    print("🎉 SUCCESS: Chrome is running!")
                    return True
                else:
                    print("❌ Chrome not detected in processes")
                    return False
            else:
                print(f"❌ Coordinates ({x}, {y}) out of bounds")
                return False
        else:
            print("❌ No Chrome coordinates found")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== IMMEDIATE CHROME TEST - DESKTOP CLEAR ===")
    success = immediate_chrome_test()
    print(f"\n🎯 RESULT: {'SUCCESS - CHROME LAUNCHED' if success else 'FAILED - NO CHROME'}")
