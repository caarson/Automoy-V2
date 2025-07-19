#!/usr/bin/env python3
"""
Test the handle_llm_response function directly.
"""

import json
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.lm.lm_interface import handle_llm_response

def test_handle_llm_response():
    """Test handle_llm_response directly."""
    
    # The exact problematic JSON from the task output
    raw_response_text = r'{"type": "key", "key": "win", "summary": "Press Windows key to open Start menu\", \"confidence": 80}'
    
    print(f"Testing handle_llm_response with: {raw_response_text}")
    
    try:
        result = handle_llm_response(
            raw_response_text=raw_response_text,
            context_description="action_generation",
            is_json=True,
            llm_interface=None,
            objective=None,
            current_step_description=None,
            visual_analysis_output=None
        )
        
        print(f"Result: {result}")
        
        if isinstance(result, dict) and "error" not in result:
            print("✅ SUCCESS: handle_llm_response worked!")
            return True
        else:
            print(f"❌ FAILED: Got error or unexpected result")
            return False
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_handle_llm_response()
    if success:
        print("\n✅ handle_llm_response is working!")
    else:
        print("\n❌ handle_llm_response needs fixing.")
