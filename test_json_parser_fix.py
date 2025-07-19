#!/usr/bin/env python3
"""
Test the JSON parser fixes for the specific error encountered.
"""

import json
import re
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.lm.lm_interface import LLMInterface

def test_problematic_json():
    """Test the specific JSON that was failing."""
    
    # This is the exact problematic JSON from the task output
    problematic_json = '{"type": "key", "key": "win", "summary": "Press Windows key to open Start menu\\", \\"confidence": 80}'
    
    print("Testing problematic JSON:")
    print(f"Original: {problematic_json}")
    
    # Test our fixed parsing logic
    llm_interface = LLMInterface()
    
    try:
        result = llm_interface.process_response(problematic_json, "action_generation", is_json=True)
        print(f"✅ Successfully parsed: {result}")
        return True
    except Exception as e:
        print(f"❌ Still failing: {e}")
        return False

def test_additional_cases():
    """Test additional JSON parsing cases."""
    
    test_cases = [
        # Case 1: Normal valid JSON
        '{"type": "key", "key": "win", "summary": "Normal action", "confidence": 80}',
        
        # Case 2: Unescaped quotes in summary
        '{"type": "key", "key": "win", "summary": "Press the "Windows" key", "confidence": 80}',
        
        # Case 3: Multiple JSON objects in response
        '{"type": "key", "key": "win", "summary": "First action", "confidence": 80}\n{"type": "type", "text": "chrome", "summary": "Second action", "confidence": 85}',
        
        # Case 4: JSON with trailing backslash
        '{"type": "key", "key": "win", "summary": "Action with backslash\\", "confidence": 80}',
    ]
    
    llm_interface = LLMInterface()
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest case {i}:")
        print(f"Input: {test_case}")
        
        try:
            result = llm_interface.process_response(test_case, "action_generation", is_json=True)
            print(f"✅ Result: {result}")
        except Exception as e:
            print(f"❌ Error: {e}")

def test_json_extraction():
    """Test the JSON extraction from LM responses."""
    
    # Simulate the actual LM response that was causing issues
    lm_response = '''<think>
Okay, let's tackle this. The user wants to generate precise actions for opening the Start menu, typing 'chrome', and pressing Enter.

First step is pressing the Windows key. The visual analysis data doesn't have elements, so I need to rely on the step description. The first action should be a key press of 'win'. The confidence might be around 80 since it's a standard key.

Next, typing 'chrome' in the search bar. Since there's no visual data, but the step mentions the Start menu search bar, maybe the coordinates are known from previous analysis. Wait, the user provided Visual Analysis Data as empty, so maybe the type action is straightforward. The confidence here could be 85 as it's a common operation.

Third step is pressing Enter to launch Chrome. Again, without specific coordinates, but the action is a key press of 'enter'. Confidence might be similar to the first step, around 80.
</think>

{"type": "key", "key": "win", "summary": "Press Windows key to open Start menu", "confidence": 80}
{"type": "type", "text": "chrome", "summary": "Type chrome in search box", "confidence": 85}
{"type": "key", "key": "enter", "summary": "Press Enter to launch Chrome browser", "confidence": 80}'''
    
    print("Testing JSON extraction from LM response:")
    print(f"Response length: {len(lm_response)} chars")
    
    # Test with LLMInterface which should handle the extraction
    llm_interface = LLMInterface()
    
    try:
        # Process the full response 
        extracted = llm_interface.process_response(lm_response, "action_generation", is_json=True)
        print(f"✅ Extracted and parsed: {extracted}")
        
    except Exception as e:
        print(f"❌ Processing failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=== Testing JSON Parser Fixes ===\n")
    
    success = test_problematic_json()
    
    print("\n" + "="*50)
    test_additional_cases()
    
    print("\n" + "="*50)
    test_json_extraction()
    
    if success:
        print("\n✅ Main problematic JSON case is now fixed!")
    else:
        print("\n❌ Main problematic JSON case still needs work.")
