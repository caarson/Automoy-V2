#!/usr/bin/env python3
"""
Force screenshot and Chrome detection
"""

import os
import sys
import json
from datetime import datetime

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Force import and execution
try:
    import pyautogui
    
    # Take screenshot immediately
    print("Taking immediate screenshot...")
    screenshot_path = f"URGENT_desktop_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    screenshot = pyautogui.screenshot()
    screenshot.save(screenshot_path)
    
    screen_width, screen_height = pyautogui.size()
    print(f"Screenshot saved: {screenshot_path}")
    print(f"Screen size: {screen_width}x{screen_height}")
    
    # Try OmniParser
    try:
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        
        omniparser_manager = OmniParserServerManager()
        if omniparser_manager.is_server_ready():
            omniparser = omniparser_manager.get_interface()
            
            print("Running OmniParser analysis...")
            results = omniparser.process_screenshot(screenshot_path)
            
            if results:
                print(f"OmniParser found {len(results)} elements")
                
                # Save results
                results_file = f"URGENT_omniparser_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(results_file, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                print(f"Results saved: {results_file}")
                
                # Look for Chrome
                chrome_found = False
                for i, item in enumerate(results):
                    if isinstance(item, dict):
                        text = item.get('text', '') if item.get('text') else ''
                        if any(keyword in text.lower() for keyword in ['chrome', 'google']):
                            print(f"CHROME FOUND: Item #{i} - '{text}'")
                            print(f"Full item: {item}")
                            chrome_found = True
                
                if not chrome_found:
                    print("No Chrome items detected in results")
                    # Show first few items for debugging
                    for i, item in enumerate(results[:5]):
                        if isinstance(item, dict):
                            text = item.get('text', '') if item.get('text') else ''
                            print(f"Sample item #{i}: '{text}'")
            else:
                print("No results from OmniParser")
        else:
            print("OmniParser server not ready")
    except Exception as e:
        print(f"OmniParser error: {e}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("Force screenshot test complete")
