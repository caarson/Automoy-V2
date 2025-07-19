#!/usr/bin/env python3
"""
Quick Chrome icon verification test
"""

import pyautogui
import json
from datetime import datetime

def quick_chrome_verification():
    """Quick test to verify Chrome icon detection"""
    
    print("=== Quick Chrome Icon Verification ===")
    
    try:
        # Get screen info
        screen_width, screen_height = pyautogui.size()
        print(f"Screen: {screen_width}x{screen_height}")
        
        # Take screenshot
        screenshot_path = f"quick_chrome_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(screenshot_path)
        print(f"Screenshot saved: {screenshot_path}")
        
        # Check if we can import OmniParser
        try:
            import sys
            import os
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
                
            from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
            
            omniparser_manager = OmniParserServerManager()
            
            if omniparser_manager.is_server_ready():
                print("✅ OmniParser server is ready")
                omniparser = omniparser_manager.get_interface()
                
                # Process screenshot
                results = omniparser.process_screenshot(screenshot_path)
                if results:
                    print(f"✅ OmniParser returned {len(results)} elements")
                    
                    # Count Chrome-related items
                    chrome_count = 0
                    for item in results:
                        if isinstance(item, dict):
                            text = item.get('text', '') if item.get('text') else ''
                            if any(keyword in text.lower() for keyword in ['chrome', 'google']):
                                chrome_count += 1
                    
                    print(f"📍 Found {chrome_count} Chrome-related items")
                    
                    if chrome_count > 0:
                        print("✅ Chrome detection appears to be working")
                        return True
                    else:
                        print("❌ No Chrome items detected")
                        return False
                else:
                    print("❌ OmniParser returned no results")
                    return False
            else:
                print("❌ OmniParser server not ready")
                return False
                
        except Exception as e:
            print(f"❌ OmniParser error: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Error in verification: {e}")
        return False

if __name__ == "__main__":
    success = quick_chrome_verification()
    print(f"\n🎯 Verification Result: {'PASSED' if success else 'FAILED'}")
