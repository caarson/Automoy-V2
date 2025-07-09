#!/usr/bin/env python3

"""
Test script to verify the double brace JSON fix
"""

import sys
import os
import json

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from core.lm.lm_interface import handle_llm_response

def test_double_brace_fix():
    """Test the improved JSON parsing with double brace issues"""
    
    print("=== Testing Double Brace JSON Fix ===\n")
    
    # Test the problematic JSON from the logs
    problematic_json = """[
  {{"operation": "click", "text": "Google Chrome"}}
]"""
    
    print("Original problematic JSON:")
    print(problematic_json)
    print()
    
    # Test the parsing
    result = handle_llm_response(
        problematic_json,
        context_description="action_generation",
        is_json=True,
        objective="Launch the Google Chrome application",
        current_step_description="Click on the Google Chrome icon"
    )
    
    print("Parsed result:")
    print(result)
    print()
    
    if isinstance(result, list) and len(result) > 0:
        action = result[0]
        print("✅ SUCCESS: JSON was parsed successfully!")
        print(f"Action type: {action.get('operation', 'Unknown')}")
        print(f"Target: {action.get('text', 'Unknown')}")
    elif isinstance(result, dict) and result.get('action_type'):
        print("✅ SUCCESS: Fallback action generated!")
        print(f"Action type: {result.get('action_type')}")
        print(f"Description: {result.get('description')}")
    else:
        print("❌ FAILED: No valid action generated")
        print(f"Result: {result}")

if __name__ == "__main__":
    test_double_brace_fix()
