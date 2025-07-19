#!/usr/bin/env python3
"""
Simple test for the JSON parser fix.
"""

import json
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.lm.lm_interface import LLMInterface

def test_simple_json_fix():
    """Test our specific JSON fix."""
    
    # The exact problematic JSON from the task output
    problematic_json = r'{"type": "key", "key": "win", "summary": "Press Windows key to open Start menu\", \"confidence": 80}'
    
    print(f"Testing problematic JSON: {problematic_json}")
    
    try:
        llm_interface = LLMInterface()
        result = llm_interface.process_response(problematic_json, "action_generation", is_json=True)
        
        if isinstance(result, dict) and "error" not in result:
            print("✅ SUCCESS: JSON parsed correctly!")
            print(f"Result: {result}")
            return True
        else:
            print(f"❌ FAILED: Got error result: {result}")
            return False
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False

if __name__ == "__main__":
    success = test_simple_json_fix()
    if success:
        print("\n✅ JSON parser fix is working!")
    else:
        print("\n❌ JSON parser fix needs more work.")
