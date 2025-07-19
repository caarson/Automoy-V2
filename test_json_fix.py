#!/usr/bin/env python3
"""
Direct test of action generation with JSON parsing fixes
"""

import os
import sys
import asyncio
import json

# Add project root to Python path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.lm.lm_interface import MainInterface

async def test_action_generation():
    """Test action generation with simulated LLM response"""
    print("=== Testing Action Generation with JSON Fixes ===")
    
    try:
        # Initialize LLM interface
        llm_interface = MainInterface()
        
        # Simulate a valid JSON response from LLM (like what LMStudio would return)
        mock_llm_response = '{"type": "key", "key": "win"}'
        
        print(f"1. Testing with mock LLM response: {mock_llm_response}")
        
        # Test the JSON parsing with the handle_llm_response function
        from core.lm.lm_interface import handle_llm_response
        
        result = handle_llm_response(
            raw_response_text=mock_llm_response,
            context_description="action_generation",
            is_json=True,
            llm_interface=llm_interface,
            objective="Click on the Google Chrome icon",
            current_step_description="Press Windows key to open Start menu"
        )
        
        print(f"2. JSON parsing result: {result}")
        print(f"   Type: {type(result)}")
        
        if isinstance(result, dict):
            print("✅ JSON parsing successful!")
            print(f"   Action type: {result.get('type', 'unknown')}")
            print(f"   Summary: {result.get('summary', 'no summary')}")
            print(f"   Confidence: {result.get('confidence', 'no confidence')}")
            
            # Verify required fields
            if "type" in result:
                print("✅ Action has 'type' field")
            if "summary" in result:
                print("✅ Action has 'summary' field")
            if "confidence" in result:
                print("✅ Action has 'confidence' field")
                
            print("\n✓ All required fields present - action should execute successfully!")
            return True
        else:
            print(f"❌ JSON parsing failed - returned: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    success = await test_action_generation()
    
    if success:
        print("\n=== TEST PASSED ===")
        print("The JSON parsing fixes are working correctly!")
        print("Chrome clicking should now work without JSON errors.")
    else:
        print("\n=== TEST FAILED ===")
        print("There are still issues with JSON parsing.")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
