#!/usr/bin/env python3
"""
Test Chrome goal creation to trigger coordinate bypass system
"""

import json
import time

def set_chrome_goal():
    """Set a Chrome-related goal to trigger the coordinate bypass"""
    
    goal_data = {
        "goal": "Open Google Chrome browser",
        "operator_status": "goal_received", 
        "current_step_details": "Chrome goal received - testing coordinate bypass system",
        "thinking": "Processing Chrome goal..."
    }
    
    # Write the goal to gui_state.json
    try:
        with open("gui_state.json", "w", encoding='utf-8') as f:
            json.dump(goal_data, f, indent=2, ensure_ascii=False)
        
        print("✅ Chrome goal set successfully!")
        print(f"Goal: {goal_data['goal']}")
        print("Goal written to gui_state.json")
        
        # Wait a moment and check if the system responds
        time.sleep(2)
        
        # Check the updated state
        try:
            with open("gui_state.json", "r", encoding='utf-8') as f:
                updated_state = json.load(f)
            print(f"\nUpdated status: {updated_state.get('operator_status', 'unknown')}")
            print(f"Updated thinking: {updated_state.get('thinking', 'none')}")
        except Exception as e:
            print(f"Could not read updated state: {e}")
            
    except Exception as e:
        print(f"❌ Failed to set Chrome goal: {e}")

if __name__ == "__main__":
    print("Setting Chrome goal to test coordinate bypass...")
    set_chrome_goal()
