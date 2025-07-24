#!/usr/bin/env python3
"""
Test script to capture a desktop screenshot and analyze it with OmniParser
"""

import os
import sys
import json
from datetime import datetime

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_desktop_screenshot_analysis():
    """Test OmniParser by taking a screenshot and analyzing it"""
    print("=== Desktop Screenshot Analysis Test ===")
    print(f"Timestamp: {datetime.now()}")
    
    try:
        # Import desktop utilities for screenshot
        from core.utils.operating_system.desktop_utils import DesktopUtils
        desktop_utils = DesktopUtils()
        print("✓ Desktop utilities imported successfully")
        
        # Take screenshot
        print("\n1. Taking desktop screenshot...")
        screenshot_path = desktop_utils.capture_screenshot()
        if screenshot_path and os.path.exists(screenshot_path):
            print(f"✓ Screenshot captured: {screenshot_path}")
            file_size = os.path.getsize(screenshot_path)
            print(f"  File size: {file_size} bytes")
        else:
            print("✗ Failed to capture screenshot")
            return False
            
    except Exception as e:
        print(f"✗ Error with desktop utils: {e}")
        return False
    
    try:
        # Import and test OmniParser
        print("\n2. Initializing OmniParser...")
        from core.utils.omniparser.omniparser_interface import OmniParserInterface
        omniparser = OmniParserInterface()
        print("✓ OmniParser interface created")
        
        # Check server status
        if omniparser.is_server_ready():
            print("✓ OmniParser server is ready")
        else:
            print("✗ OmniParser server is not ready")
            return False
            
    except Exception as e:
        print(f"✗ Error initializing OmniParser: {e}")
        return False
    
    try:
        # Analyze the screenshot
        print("\n3. Analyzing screenshot with OmniParser...")
        result = omniparser.parse_image(screenshot_path)
        
        if result:
            print("✓ OmniParser analysis completed!")
            print(f"  Result type: {type(result)}")
            
            # Print structured analysis
            if isinstance(result, dict):
                print("\n--- Analysis Results ---")
                for key, value in result.items():
                    if key == 'parsed_content_list' and isinstance(value, list):
                        print(f"{key}: Found {len(value)} elements")
                        for i, element in enumerate(value[:5]):  # Show first 5 elements
                            if isinstance(element, dict):
                                element_type = element.get('type', 'unknown')
                                element_text = element.get('text', 'no text')
                                element_bbox = element.get('bbox', 'no bbox')
                                print(f"  Element {i+1}: {element_type} - '{element_text}' at {element_bbox}")
                        if len(value) > 5:
                            print(f"  ... and {len(value) - 5} more elements")
                    else:
                        print(f"{key}: {value}")
            else:
                print(f"Raw result: {result}")
                
            # Save detailed results to file
            results_file = "desktop_analysis_results.json"
            try:
                with open(results_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, default=str)
                print(f"\n✓ Detailed results saved to: {results_file}")
            except Exception as save_error:
                print(f"⚠ Could not save results to file: {save_error}")
                
        else:
            print("✗ OmniParser returned no results")
            return False
            
    except Exception as e:
        print(f"✗ Error during OmniParser analysis: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n=== Test Complete ===")
    print("✓ Desktop screenshot analysis successful!")
    return True

if __name__ == "__main__":
    try:
        success = test_desktop_screenshot_analysis()
        if success:
            print("\n🎉 All tests passed! OmniParser can successfully analyze desktop screenshots.")
        else:
            print("\n❌ Test failed. Check the error messages above.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
