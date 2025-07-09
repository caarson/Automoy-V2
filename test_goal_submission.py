#!/usr/bin/env python3
"""
Test script to submit a goal and verify the system processes it correctly.
"""

import json
import time
import os

def submit_test_goal():
    goal_file = "goal_request.json"
    
    print("Submitting test goal...")
    
    # Create goal request
    goal_data = {
        "goal": "Open notepad and type 'Hello World'",
        "timestamp": time.time()
    }
    
    # Write goal to file
    with open(goal_file, 'w') as f:
        json.dump(goal_data, f)
    
    print(f"✓ Goal submitted: {goal_data['goal']}")
    
    # Monitor the state file for changes
    print("\nMonitoring GUI state for processing...")
    
    for i in range(30):  # Monitor for 30 seconds
        try:
            if os.path.exists("gui_state.json"):
                with open("gui_state.json", 'r') as f:
                    state = json.load(f)
                
                status = state.get("operator_status", "unknown")
                details = state.get("current_step_details", "")
                objective = state.get("objective", "")
                
                print(f"[{i+1:2d}s] Status: {status} | Details: {details}")
                
                if objective and objective != "System initialized and ready for goals.":
                    print(f"      Objective: {objective}")
                
                # Check if processing started
                if status in ["thinking", "running", "analyzing", "planning", "executing"]:
                    print(f"✓ Goal processing started! Status: {status}")
                    
                    # Continue monitoring for a bit longer
                    for j in range(20):
                        time.sleep(1)
                        try:
                            with open("gui_state.json", 'r') as f:
                                state = json.load(f)
                            
                            status = state.get("operator_status", "unknown")
                            details = state.get("current_step_details", "")
                            print(f"[{i+j+2:2d}s] Status: {status} | Details: {details}")
                            
                            if status in ["completed", "error"]:
                                print(f"✓ Processing finished with status: {status}")
                                return True
                                
                        except (FileNotFoundError, json.JSONDecodeError) as e:
                            print(f"Error reading state: {e}")
                    
                    return True
                
                # Check if goal was processed but failed
                if status == "error":
                    error_msg = state.get("llm_error_message", "")
                    print(f"✗ Goal processing failed: {error_msg}")
                    return False
                    
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error reading state: {e}")
        
        time.sleep(1)
    
    print("✗ Timeout waiting for goal processing to start")
    return False

if __name__ == "__main__":
    submit_test_goal()
