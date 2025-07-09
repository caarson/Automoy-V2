#!/usr/bin/env python3

"""
Test script to demonstrate the improved Calculator fallback logic
This shows how the enhanced LLM interface now handles Calculator-specific operations
"""

import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from core.lm.lm_interface import LLMInterface

def test_calculator_fallback():
    """Test the improved Calculator fallback logic"""
    
    print("=== Testing Calculator Fallback Logic ===\n")
    
    # Create LLM interface instance
    llm = LLMInterface()
    
    # Test scenarios for Calculator operations
    test_cases = [
        {
            "objective": "Launch the Calculator application",
            "step_description": "Minimize all open windows to show desktop",
            "llm_response": "I can see the desktop with various icons...",  # Simulated bad LLM response
            "expected_action": "key sequence (Win+D)"
        },
        {
            "objective": "Launch the Calculator application", 
            "step_description": "Access the Start menu by pressing Windows key",
            "llm_response": "The desktop is now visible...",  # Simulated bad LLM response
            "expected_action": "key press (Windows key)"
        },
        {
            "objective": "Launch the Calculator application",
            "step_description": "Type 'Calculator' in the Start menu search bar",
            "llm_response": "I need to search for Calculator...",  # Simulated bad LLM response
            "expected_action": "type text (Calculator)"
        },
        {
            "objective": "Launch the Calculator application",
            "step_description": "Press Enter to launch Calculator from search results", 
            "llm_response": "Calculator should be selected...",  # Simulated bad LLM response
            "expected_action": "key press (Enter)"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test {i}: {test_case['step_description']}")
        print(f"Objective: {test_case['objective']}")
        print(f"LLM Response: {test_case['llm_response']}")
        
        # Simulate the fallback logic
        result = llm._parse_json_response(
            test_case['llm_response'],
            context_description="action_generation",
            objective=test_case['objective'],
            current_step_description=test_case['step_description']
        )
        
        print(f"Fallback Action Generated: {result}")
        print(f"Expected: {test_case['expected_action']}")
        
        # Check if fallback worked
        if isinstance(result, dict) and result.get('action_type'):
            print("✅ SUCCESS: Fallback action generated successfully")
            
            # Show the specific action details
            action_type = result.get('action_type')
            if action_type == 'key':
                print(f"   → Will press key: {result.get('key')}")
            elif action_type == 'type':
                print(f"   → Will type text: {result.get('text')}")
            elif action_type == 'click':
                coords = result.get('coordinate', {})
                print(f"   → Will click at: ({coords.get('x')}, {coords.get('y')})")
        else:
            print("❌ FAILED: No valid fallback action generated")
        
        print("-" * 60)

if __name__ == "__main__":
    test_calculator_fallback()
