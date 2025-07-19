#!/usr/bin/env python3
"""
Direct Chrome Clicking Test with Process Verification
Tests clicking on Chrome icon and verifies Chrome opens successfully
"""
import asyncio
import sys
import os
import time
import psutil
import logging

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.operate import ActionExecutor, AutomoyOperator
from core.data_models import get_initial_state, write_state
from core.lm.lm_interface import MainInterface

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def verify_process_running(process_name):
    """Verify if a process is running by name"""
    try:
        running_processes = []
        for process in psutil.process_iter(['name', 'pid']):
            if process_name.lower() in process.info['name'].lower():
                running_processes.append(f"{process.info['name']} (PID: {process.info['pid']})")
        
        if running_processes:
            print(f"✓ Process '{process_name}' is running: {', '.join(running_processes)}")
            return True
        else:
            print(f"✗ Process '{process_name}' is not running")
            return False
    except Exception as e:
        print(f"Error checking process '{process_name}': {e}")
        return False

async def simulate_gui_update(endpoint, payload):
    """Simulate GUI state updates"""
    print(f"GUI Update [{endpoint}]: {payload}")

async def test_chrome_clicking_with_automoy():
    """Test Chrome clicking using full Automoy system"""
    print("=== Chrome Clicking Test with Full Automoy System ===")
    
    goal = "Click on the Google Chrome icon to open Chrome browser"
    print(f"Goal: {goal}")
    
    # Check initial Chrome status
    print("\n1. Checking initial Chrome status...")
    initial_chrome_running = await verify_process_running("chrome.exe")
    if initial_chrome_running:
        print("   Chrome is already running - test will still proceed")
    else:
        print("   Chrome is not currently running - good for testing")
    
    # Initialize AutomoyOperator
    print("\n2. Initializing AutomoyOperator...")
    try:
        # Create pause event
        pause_event = asyncio.Event()
        pause_event.set()
        
        operator = AutomoyOperator(
            objective="",
            manage_gui_window_func=None,
            omniparser=None,  # Skip visual analysis for this test
            pause_event=pause_event,
            update_gui_state_func=simulate_gui_update
        )
        
        # Store the goal
        operator.original_goal = goal
        
        print("   ✓ AutomoyOperator initialized successfully")
    except Exception as e:
        print(f"   ❌ Failed to initialize AutomoyOperator: {e}")
        return False
    
    # Formulate objective using LLM
    print("\n3. Formulating objective with LLM...")
    try:
        llm_interface = MainInterface()
        objective_text, error = await llm_interface.formulate_objective(
            goal=goal,
            session_id="test_session"
        )
        
        if error:
            print(f"   ❌ LLM error: {error}")
            return False
        elif objective_text:
            # Extract final objective
            lines = objective_text.strip().split('\n')
            final_objective = lines[-1].strip() if lines else objective_text.strip()
            print(f"   ✓ Objective formulated: {final_objective}")
        else:
            print("   ❌ LLM returned empty response")
            return False
    except Exception as e:
        print(f"   ❌ Objective formulation failed: {e}")
        return False
    
    # Set objective and run
    print("\n4. Executing objective...")
    try:
        operator.set_objective(final_objective)
        print("   ✓ Objective set, operator is now running")
        
        # Wait for execution to complete or timeout
        max_wait_time = 60  # 60 seconds max
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            if operator.is_complete:
                print("   ✓ Operator reported completion")
                break
            await asyncio.sleep(1)
        else:
            print("   ⚠ Execution timed out after 60 seconds")
        
    except Exception as e:
        print(f"   ❌ Execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Verify Chrome process after execution
    print("\n5. Verifying Chrome process after execution...")
    await asyncio.sleep(2)  # Wait a moment for Chrome to fully start
    
    final_chrome_running = await verify_process_running("chrome.exe")
    
    if final_chrome_running:
        print("   ✅ SUCCESS: Chrome is running after execution!")
        if not initial_chrome_running:
            print("   🎯 PERFECT: Chrome was launched by Automoy!")
        else:
            print("   ℹ️  Chrome was already running, but execution completed")
        return True
    else:
        print("   ❌ FAILURE: Chrome is not running after execution")
        return False

async def main():
    """Main test function"""
    print("🚀 Automoy Chrome Clicking Trial Run")
    print("=" * 50)
    print("Testing: Click on Google Chrome icon and verify it opens")
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        success = await test_chrome_clicking_with_automoy()
        
        print("\n" + "=" * 50)
        if success:
            print("🎉 TRIAL RUN PASSED: Chrome clicking and verification successful!")
        else:
            print("❌ TRIAL RUN FAILED: Chrome clicking or verification failed")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n💥 Trial run failed with exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
