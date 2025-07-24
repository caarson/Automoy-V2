#!/usr/bin/env python3

"""
Simple OmniParser test to see what's happening.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

print("=== OmniParser Status Check ===")

# Test 1: Check if we can import the interface
try:
    from core.utils.omniparser.omniparser_interface import OmniParserInterface
    print("✓ OmniParserInterface imported successfully")
except Exception as e:
    print(f"❌ Failed to import OmniParserInterface: {e}")
    sys.exit(1)

# Test 2: Create interface instance
try:
    interface = OmniParserInterface()
    print("✓ Interface instance created")
except Exception as e:
    print(f"❌ Failed to create interface: {e}")
    sys.exit(1)

# Test 3: Check server status
print("\nChecking server status...")
try:
    is_ready = interface._check_server_ready()
    print(f"Server ready: {is_ready}")
    
    if is_ready:
        print("✓ Server is responding to probes!")
        
        # Try a simple screenshot test
        print("\nTesting screenshot parsing...")
        try:
            from core.utils.operating_system.desktop_utils import DesktopUtils
            desktop = DesktopUtils()
            
            # Take a quick screenshot
            screenshot_path = "quick_test.png"
            if desktop.take_screenshot(screenshot_path):
                print(f"✓ Screenshot taken: {screenshot_path}")
                
                # Try to parse it
                result = interface.parse_screenshot(screenshot_path)
                if result:
                    elements = result.get('parsed_content_list', [])
                    print(f"✓ Parse successful! Found {len(elements)} elements")
                    
                    # Show elements that might be Chrome-related
                    chrome_elements = []
                    for element in elements:
                        text = element.get('text', '').lower()
                        if 'chrome' in text or 'google' in text:
                            chrome_elements.append(element)
                    
                    if chrome_elements:
                        print(f"Found {len(chrome_elements)} Chrome-related elements:")
                        for elem in chrome_elements[:3]:
                            print(f"  - {elem.get('text', 'No text')} at {elem.get('bbox', 'No bbox')}")
                    else:
                        print("No Chrome-related elements found")
                        # Show first few elements anyway
                        print("First few elements found:")
                        for i, elem in enumerate(elements[:3]):
                            print(f"  {i+1}. {elem.get('text', 'No text')} at {elem.get('bbox', 'No bbox')}")
                else:
                    print("❌ Parse returned no results")
                    
                # Cleanup
                try:
                    os.remove(screenshot_path)
                except:
                    pass
                    
            else:
                print("❌ Failed to take screenshot")
                
        except Exception as e:
            print(f"❌ Screenshot test failed: {e}")
    else:
        print("❌ Server is not responding")
        print("\nThis means:")
        print("  1. Server may not be started")
        print("  2. Server started but crashed during model loading")
        print("  3. Server is hanging during initialization")
        print("  4. Network/port issues")
        
except Exception as e:
    print(f"❌ Server status check failed: {e}")

print("\n=== Status Check Complete ===")
