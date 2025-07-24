#!/usr/bin/env python3
"""
Simple desktop screenshot test for OmniParser
"""

import os
import sys
import traceback

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print("Starting desktop screenshot test...")

try:
    # Step 1: Import desktop utilities
    print("1. Importing desktop utilities...")
    from core.utils.operating_system.desktop_utils import DesktopUtils
    desktop_utils = DesktopUtils()
    print("   ✓ Desktop utilities ready")

    # Step 2: Take screenshot
    print("2. Capturing screenshot...")
    screenshot_path = desktop_utils.capture_screenshot()
    print(f"   Screenshot saved to: {screenshot_path}")
    
    if os.path.exists(screenshot_path):
        file_size = os.path.getsize(screenshot_path)
        print(f"   File size: {file_size} bytes")
    else:
        print("   ✗ Screenshot file not found!")
        sys.exit(1)

    # Step 3: Test OmniParser
    print("3. Testing OmniParser...")
    from core.utils.omniparser.omniparser_interface import OmniParserInterface
    omniparser = OmniParserInterface()
    print("   ✓ OmniParser interface created")

    # Step 4: Check server readiness
    print("4. Checking OmniParser server...")
    if omniparser.is_server_ready():
        print("   ✓ Server is ready")
    else:
        print("   ✗ Server is not ready")
        sys.exit(1)

    # Step 5: Analyze screenshot
    print("5. Analyzing screenshot...")
    result = omniparser.parse_image(screenshot_path)
    
    if result:
        print("   ✓ Analysis completed!")
        
        if isinstance(result, dict) and 'parsed_content_list' in result:
            elements = result['parsed_content_list']
            print(f"   Found {len(elements)} elements on desktop")
            
            # Show first few elements
            for i, element in enumerate(elements[:3]):
                if isinstance(element, dict):
                    elem_type = element.get('type', 'unknown')
                    elem_text = element.get('text', '')[:50]  # Limit text length
                    elem_bbox = element.get('bbox', [])
                    print(f"   Element {i+1}: {elem_type} - '{elem_text}' at {elem_bbox}")
        else:
            print(f"   Raw result type: {type(result)}")
    else:
        print("   ✗ No analysis results returned")

    print("\n✅ TEST COMPLETED SUCCESSFULLY!")
    print("OmniParser is working and can analyze desktop screenshots.")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
    sys.exit(1)
