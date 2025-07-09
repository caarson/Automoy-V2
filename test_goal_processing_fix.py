#!/usr/bin/env python3
"""
Test script to verify goal processing fix.
This script will:
1. Clean up any existing goal request files
2. Wait for the system to initialize 
3. Create a test goal request
4. Monitor the GUI state changes
"""

import json
import os
import time
import sys

# Add project root to path
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)

from core.data_models import GOAL_REQUEST_FILE, read_state, write_state

def cleanup_goal_files():
    """Remove any existing goal request files."""
    files_to_clean = [
        GOAL_REQUEST_FILE,
        os.path.join("debug", "logs", "gui", "goal_request.json")
    ]
    
    for file_path in files_to_clean:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"✓ Removed existing file: {file_path}")
            except Exception as e:
                print(f"✗ Failed to remove {file_path}: {e}")

def wait_for_system_ready(timeout=60):
    """Wait for the system to reach idle state."""
    print("Waiting for system to initialize...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            state = read_state()
            status = state.get("operator_status", "unknown")
            print(f"Current status: {status}")
            
            if status == "idle":
                print("✓ System is ready!")
                return True
            elif status == "error":
                print(f"✗ System error: {state.get('current_step_details', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"Error reading state: {e}")
            
        time.sleep(2)
    
    print(f"✗ Timeout waiting for system to be ready")
    return False

def create_test_goal(goal_text="open calculator"):
    """Create a test goal request file."""
    goal_data = {"goal": goal_text}
    
    try:
        with open(GOAL_REQUEST_FILE, 'w', encoding='utf-8') as f:
            json.dump(goal_data, f)
        print(f"✓ Created goal request: {goal_text}")
        return True
    except Exception as e:
        print(f"✗ Failed to create goal request: {e}")
        return False

def monitor_goal_processing(timeout=30):
    """Monitor the system processing the goal."""
    print("Monitoring goal processing...")
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < timeout:
        try:
            state = read_state()
            status = state.get("operator_status", "unknown")
            details = state.get("current_step_details", "")
            
            if status != last_status:
                print(f"Status changed: {status} - {details}")
                last_status = status
                
            if status in ["completed", "idle"]:
                print("✓ Goal processing completed!")
                return True
            elif status == "error":
                error_msg = state.get("llm_error_message", details)
                print(f"✗ Goal processing failed: {error_msg}")
                return False
                
        except Exception as e:
            print(f"Error reading state: {e}")
            
        time.sleep(1)
    
    print(f"✗ Timeout waiting for goal processing to complete")
    return False

def main():
    print("=== Goal Processing Fix Test ===")
    
    # Step 1: Clean up existing files
    print("\n1. Cleaning up existing goal request files...")
    cleanup_goal_files()
    
    # Step 2: Wait for system to be ready
    print("\n2. Waiting for system initialization...")
    if not wait_for_system_ready():
        print("System failed to initialize properly")
        return False
    
    # Step 3: Create test goal
    print("\n3. Creating test goal...")
    if not create_test_goal():
        print("Failed to create test goal")
        return False
    
    # Step 4: Monitor processing
    print("\n4. Monitoring goal processing...")
    success = monitor_goal_processing()
    
    if success:
        print("\n✓ Goal processing test completed successfully!")
    else:
        print("\n✗ Goal processing test failed!")
    
    return success

if __name__ == "__main__":
    main()
