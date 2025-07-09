#!/usr/bin/env python3
"""
Test script to submit a goal via the GUI web interface and monitor the response.
"""

import requests
import json
import time

def test_gui_goal_submission():
    base_url = "http://localhost:8001"
    
    print("Testing GUI goal submission...")
    
    # Test health
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"✓ GUI health check: {response.status_code}")
    except Exception as e:
        print(f"✗ GUI health check failed: {e}")
        return False
    
    # Submit a goal
    goal_data = {"goal": "Open Calculator"}
    
    print(f"Submitting goal: {goal_data['goal']}")
    try:
        response = requests.post(f"{base_url}/set_goal", 
                               json=goal_data, 
                               headers={'Content-Type': 'application/json'},
                               timeout=10)
        
        print(f"Goal submission response: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Goal submitted successfully: {result}")
            
            # Monitor the state for changes
            print("\nMonitoring state changes...")
            for i in range(30):
                try:
                    with open("gui_state.json", 'r') as f:
                        state = json.load(f)
                    
                    status = state.get("operator_status", "unknown")
                    objective = state.get("objective", "")
                    details = state.get("current_step_details", "")
                    
                    print(f"[{i+1:2d}s] Status: {status}")
                    if objective and objective not in ["System starting up...", "System initialized and ready for goals."]:
                        print(f"      Objective: {objective}")
                    if details:
                        print(f"      Details: {details}")
                    
                    if status in ["thinking", "running"]:
                        print(f"✓ Goal processing started!")
                        return True
                        
                except Exception as e:
                    print(f"Error reading state: {e}")
                
                time.sleep(1)
            
            print("✗ Goal processing did not start")
            return False
        else:
            print(f"✗ Goal submission failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ Error submitting goal: {e}")
        return False

if __name__ == "__main__":
    test_gui_goal_submission()
