#!/usr/bin/env python3
"""
Debug OmniParser output to understand why bbox_normalized is missing
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))

from core.utils.omniparser.omniparser_interface import OmniParserInterface
import json

def test_omniparser_output():
    """Test what OmniParser actually returns"""
    print("=== DEBUGGING OMNIPARSER OUTPUT ===")
    
    try:
        # Initialize OmniParser
        print("1. Initializing OmniParser...")
        omni = OmniParserInterface()
        
        print("2. Starting OmniParser server...")
        omni.start_server()
        
        print("3. Running visual analysis...")
        result = omni.parse_ui_screenshot()
        
        print("4. Analyzing result structure...")
        if result:
            print(f"Result keys: {list(result.keys())}")
            
            if "parsed_content_list" in result:
                elements = result["parsed_content_list"]
                print(f"Found {len(elements)} elements")
                
                if elements:
                    first_element = elements[0]
                    print(f"\nFirst element structure:")
                    print(f"Type: {type(first_element)}")
                    if isinstance(first_element, dict):
                        print(f"Keys: {list(first_element.keys())}")
                        for key, value in first_element.items():
                            print(f"  {key}: {value}")
                    else:
                        print(f"Content: {first_element}")
                    
                    # Check for bbox fields
                    if isinstance(first_element, dict):
                        bbox_fields = [k for k in first_element.keys() if 'bbox' in k.lower()]
                        print(f"\nBounding box fields found: {bbox_fields}")
                        
                        for field in bbox_fields:
                            print(f"{field}: {first_element[field]}")
            else:
                print("No 'parsed_content_list' in result")
        else:
            print("OmniParser returned empty result")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_omniparser_output()
