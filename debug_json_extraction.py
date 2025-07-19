#!/usr/bin/env python3
"""
Debug the JSON extraction process step by step.
"""

import json
import re
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def debug_json_extraction():
    """Debug the JSON extraction step by step."""
    
    # The exact problematic JSON from the task output
    problematic_json = r'{"type": "key", "key": "win", "summary": "Press Windows key to open Start menu\", \"confidence": 80}'
    
    print(f"Original JSON: {problematic_json}")
    print(f"Length: {len(problematic_json)}")
    
    # Test the regex pattern that should find JSON objects
    json_obj_match = re.search(r'\{.*\}', problematic_json, re.DOTALL)
    if json_obj_match:
        print(f"✅ Regex found JSON: {json_obj_match.group(0)}")
        extracted_json = json_obj_match.group(0).strip()
        
        # Try to parse directly
        try:
            parsed = json.loads(extracted_json)
            print(f"✅ Direct parse successful: {parsed}")
        except json.JSONDecodeError as e:
            print(f"❌ Direct parse failed: {e}")
            print(f"Error at character {e.pos}: '{extracted_json[max(0, e.pos-5):e.pos+5]}'")
            
            # Apply our fixing logic
            print("\nApplying fixes...")
            
            fixed_json = extracted_json
            
            # Apply our specific fixes
            fixed_json = re.sub(r'\\"\s*,\s*\\"([^"]+)":', r'", "\1":', fixed_json)
            fixed_json = re.sub(r'([^\\])\\"\s*,', r'\1",', fixed_json)
            fixed_json = re.sub(r'([^\\])\\"\s*}', r'\1"}', fixed_json)
            
            print(f"After fixes: {fixed_json}")
            
            try:
                parsed_fixed = json.loads(fixed_json)
                print(f"✅ Fixed parse successful: {parsed_fixed}")
                return True
            except json.JSONDecodeError as e2:
                print(f"❌ Fixed parse still failed: {e2}")
                print(f"Error at character {e2.pos}: '{fixed_json[max(0, e2.pos-5):e2.pos+5]}'")
                return False
    else:
        print("❌ Regex did not find JSON object")
        return False

if __name__ == "__main__":
    success = debug_json_extraction()
    if success:
        print("\n✅ JSON extraction and fixing works!")
    else:
        print("\n❌ JSON extraction and fixing needs more work.")
