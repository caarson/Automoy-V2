#!/usr/bin/env python3
"""
Manual Chrome detection test with detailed coordinate analysis
"""

import os
import sys
import json
import pyautogui
from datetime import datetime

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def manual_chrome_test():
    """Manual Chrome test with full coordinate debugging"""
    
    try:
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.operating_system.desktop_utils import DesktopUtils
        
        # Get screen dimensions
        screen_width, screen_height = pyautogui.size()
        print(f"Screen dimensions: {screen_width}x{screen_height}")
        
        # Initialize OmniParser
        print("Initializing OmniParser...")
        omniparser_manager = OmniParserServerManager()
        
        if not omniparser_manager.is_server_ready():
            print("Starting OmniParser server...")
            server_process = omniparser_manager.start_server()
            if not omniparser_manager.wait_for_server(timeout=60):
                print("❌ OmniParser server failed to start")
                return False
        
        omniparser = omniparser_manager.get_interface()
        desktop_utils = DesktopUtils()
        
        # Show desktop
        print("Showing desktop...")
        desktop_utils.show_desktop()
        
        import time
        time.sleep(2)
        
        # Take screenshot
        print("Taking screenshot...")
        screenshot_path = f"manual_chrome_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(screenshot_path)
        print(f"Screenshot saved: {screenshot_path}")
        
        # Analyze with OmniParser
        print("Analyzing with OmniParser...")
        results = omniparser.process_screenshot(screenshot_path)
        
        if not results:
            print("❌ No OmniParser results")
            return False
        
        print(f"✅ OmniParser found {len(results)} elements")
        
        # Save results for analysis
        results_file = f"omniparser_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Results saved: {results_file}")
        
        # Find Chrome items
        chrome_items = []
        for i, item in enumerate(results):
            if isinstance(item, dict):
                text = item.get('text', '') if item.get('text') else ''
                if any(keyword in text.lower() for keyword in ['chrome', 'google', 'browser']):
                    chrome_items.append((i, item))
                    print(f"\n📍 Chrome item #{i}:")
                    print(f"   Text: '{text}'")
                    print(f"   Full item: {item}")
        
        if not chrome_items:
            print("❌ No Chrome items found")
            # Show some sample items for debugging
            print("\n📋 Sample items for debugging:")
            for i, item in enumerate(results[:10]):
                if isinstance(item, dict):
                    text = item.get('text', '') if item.get('text') else ''
                    print(f"   Item #{i}: '{text}' - {list(item.keys())}")
            return False
        
        print(f"\n✅ Found {len(chrome_items)} Chrome items")
        
        # Test coordinates for each Chrome item
        for idx, (item_num, chrome_item) in enumerate(chrome_items):
            print(f"\n🎯 Testing Chrome item #{item_num}:")
            
            coords = None
            
            # Try bbox_normalized
            if 'bbox_normalized' in chrome_item:
                bbox = chrome_item['bbox_normalized']
                print(f"   bbox_normalized: {bbox}")
                
                if isinstance(bbox, list) and len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox[:4]
                    center_x = int((x1 + x2) / 2 * screen_width)
                    center_y = int((y1 + y2) / 2 * screen_height)
                    coords = (center_x, center_y)
                    print(f"   Calculated coords: ({center_x}, {center_y})")
            
            # Try bbox
            elif 'bbox' in chrome_item:
                bbox = chrome_item['bbox']
                print(f"   bbox: {bbox}")
                
                if isinstance(bbox, list) and len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox[:4]
                    center_x = int((x1 + x2) / 2)
                    center_y = int((y1 + y2) / 2)
                    coords = (center_x, center_y)
                    print(f"   Calculated coords: ({center_x}, {center_y})")
            
            else:
                print(f"   No recognized coordinate format: {list(chrome_item.keys())}")
                continue
            
            if coords and idx == 0:  # Test first valid coordinates
                x, y = coords
                print(f"\n🖱️ Testing click at ({x}, {y})...")
                
                # Validate coordinates are within screen bounds
                if 0 <= x <= screen_width and 0 <= y <= screen_height:
                    print(f"   Coordinates are within screen bounds")
                    
                    # Perform click
                    pyautogui.click(x, y)
                    print(f"   Click executed at ({x}, {y})")
                    
                    # Wait and check for Chrome
                    print("   Waiting 4 seconds...")
                    time.sleep(4)
                    
                    # Check for Chrome processes
                    import subprocess
                    try:
                        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                                              capture_output=True, text=True)
                        if 'chrome.exe' in result.stdout:
                            print("   ✅ SUCCESS: Chrome process detected!")
                            return True
                        else:
                            print("   ❌ No Chrome process detected")
                    except Exception as e:
                        print(f"   ❌ Error checking processes: {e}")
                else:
                    print(f"   ❌ Coordinates ({x}, {y}) are outside screen bounds")
        
        print("\n❌ No successful Chrome click achieved")
        return False
        
    except Exception as e:
        print(f"❌ Error in manual Chrome test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== Manual Chrome Detection Test ===")
    success = manual_chrome_test()
    print(f"\n🎯 Final Result: {'SUCCESS' if success else 'FAILED'}")
