#!/usr/bin/env python3
"""
Direct test by bypassing LLM and directly setting objective to test coordinate clicking
"""
import json
import os
import time

def bypass_llm_and_test_coordinates():
    """Bypass LLM formulation and directly test coordinate clicking"""
    print("=== BYPASSING LLM TO TEST COORDINATES ===")
    
    # Update GUI state to simulate successful objective formulation
    gui_state = {
        "operator_status": "running",
        "goal": "Test Chrome clicking with visual coordinates", 
        "objective": "Locate and click the Google Chrome icon on the desktop or taskbar to launch the browser application",
        "current_step_details": "Objective formulated (bypassed LLM). Starting dynamic operation loop...",
        "current_operation": "Initializing operation sequence",
        "thinking": "Ready to execute: Locate and click the Google Chrome icon on the desktop or taskbar to launch the browser application",
        "llm_error_message": None
    }
    
    # Write the updated state
    gui_state_path = "gui_state.json"
    with open(gui_state_path, 'w', encoding='utf-8') as f:
        json.dump(gui_state, f, indent=2)
    
    print(f"✓ Updated GUI state: {gui_state_path}")
    print(f"✓ Set objective: {gui_state['objective']}")
    print("✓ Operator status set to 'running'")
    print("\nNow the system should:")
    print("1. Take a screenshot")
    print("2. Perform OmniParser visual analysis") 
    print("3. Extract REAL coordinates from visual analysis")
    print("4. Click on Chrome icon using those coordinates")
    print("5. Verify Chrome process starts")
    
    return True

if __name__ == "__main__":
    success = bypass_llm_and_test_coordinates()
    if success:
        print("\n🎯 LLM bypassed successfully! Monitor Automoy logs for coordinate extraction...")
    else:
        print("\n❌ Failed to bypass LLM")
