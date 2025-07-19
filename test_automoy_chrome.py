#!/usr/bin/env python3
"""
Direct test of Automoy Chrome clicking functionality
This bypasses the goal file system and directly tests the Chrome detection
"""

import os
import sys
import time
import subprocess
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_automoy_chrome_clicking():
    """Test the actual Automoy Chrome clicking workflow"""
    
    print("🎯 Testing Automoy Chrome Clicking Workflow")
    print("=" * 60)
    
    try:
        # Step 1: Ensure Chrome is closed
        print("1. Ensuring Chrome is closed...")
        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                      capture_output=True, text=True)
        time.sleep(1)
        
        result = subprocess.run(
            ['powershell', '-Command', 'Get-Process chrome -ErrorAction SilentlyContinue'],
            capture_output=True, text=True
        )
        if result.stdout.strip():
            print("   ⚠️  Some Chrome processes still running")
        else:
            print("   ✅ Chrome is completely closed")
        
        # Step 2: Import Automoy components
        print("2. Importing Automoy components...")
        from core.operate import AutomoyOperator
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.screenshot_utils import capture_screen_pil
        print("   ✅ Components imported successfully")
        
        # Step 3: Initialize OmniParser
        print("3. Initializing OmniParser...")
        omniparser_manager = OmniParserServerManager()
        if not omniparser_manager.is_server_ready():
            print("   🔄 Starting OmniParser server...")
            server_process = omniparser_manager.start_server()
            if not omniparser_manager.wait_for_server(timeout=30):
                print("   ❌ Failed to start OmniParser")
                return False
        print("   ✅ OmniParser ready")
        
        # Step 4: Initialize Automoy Operator
        print("4. Initializing Automoy Operator...")
        
        # Mock functions needed by the operator
        def mock_manage_gui_window():
            pass
        
        def mock_update_gui_state(state):
            print(f"   📱 GUI State: {state.get('current_operation', 'Unknown')}")
        
        # Initialize operator
        operator = AutomoyOperator()
        operator.set_dependencies(
            omniparser=omniparser_manager.get_interface(),
            manage_gui_window_func=mock_manage_gui_window,
            _update_gui_state_func=mock_update_gui_state,
            desktop_utils=None  # We'll handle this in the test
        )
        print("   ✅ Automoy Operator initialized")
        
        # Step 5: Test Chrome detection and clicking
        print("5. Testing Chrome detection and clicking...")
        
        # Create a simple goal for Chrome opening
        goal = "Open Google Chrome by clicking the Chrome icon"
        print(f"   🎯 Goal: '{goal}'")
        
        # Test the objective formulation
        print("   🤔 Formulating objective...")
        objective_result = operator.formulate_objective(goal)
        
        if objective_result and "objective" in objective_result:
            objective = objective_result["objective"]
            print(f"   ✅ Objective formulated: '{objective}'")
            
            # Test step generation
            print("   📝 Generating steps...")
            steps_result = operator.generate_steps(objective)
            
            if steps_result and "steps" in steps_result:
                steps = steps_result["steps"]
                print(f"   ✅ Generated {len(steps)} steps:")
                for i, step in enumerate(steps, 1):
                    print(f"     {i}. {step}")
                
                # Test the first step (which should involve Chrome detection)
                print("   🔍 Executing first step...")
                first_step = steps[0]
                
                # Capture screenshot for the step
                screenshot = capture_screen_pil()
                if not screenshot:
                    print("   ❌ Failed to capture screenshot")
                    return False
                
                # Get action for the step
                action_result = operator._get_action_for_current_step(
                    current_step=first_step,
                    objective=objective,
                    screenshot=screenshot,
                    step_index=0,
                    steps=steps
                )
                
                if action_result:
                    print(f"   ✅ Action determined: {action_result.get('action_type', 'Unknown')}")
                    print(f"     Description: {action_result.get('description', 'No description')}")
                    
                    # If it's a click action, check coordinates
                    if action_result.get('action_type') == 'click':
                        coords = action_result.get('coordinates')
                        if coords:
                            print(f"     🎯 Click coordinates: {coords}")
                            
                            # Perform the click
                            import pyautogui
                            pyautogui.click(coords[0], coords[1])
                            print(f"   ✅ Click performed at {coords}")
                            
                            # Wait and check if Chrome opened
                            print("   ⏳ Waiting for Chrome to launch...")
                            time.sleep(4)
                            
                            result = subprocess.run(
                                ['powershell', '-Command', 'Get-Process chrome -ErrorAction SilentlyContinue'],
                                capture_output=True, text=True
                            )
                            
                            if result.stdout.strip():
                                print("   🎉 SUCCESS! Chrome launched successfully!")
                                print("   Chrome processes detected:")
                                for line in result.stdout.strip().split('\n')[:5]:  # Show first 5 processes
                                    if line.strip():
                                        print(f"     {line}")
                                
                                # Count processes
                                count_result = subprocess.run(
                                    ['powershell', '-Command', '(Get-Process chrome -ErrorAction SilentlyContinue).Count'],
                                    capture_output=True, text=True
                                )
                                if count_result.stdout.strip():
                                    print(f"   📊 Total Chrome processes: {count_result.stdout.strip()}")
                                
                                return True
                            else:
                                print("   ❌ Chrome did not launch")
                                return False
                        else:
                            print("   ❌ No click coordinates provided")
                            return False
                    else:
                        print(f"   ⚠️  Expected click action, got: {action_result.get('action_type')}")
                        return False
                else:
                    print("   ❌ No action determined")
                    return False
            else:
                print("   ❌ Failed to generate steps")
                return False
        else:
            print("   ❌ Failed to formulate objective")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting direct Automoy Chrome clicking test...")
    print("This will test the complete workflow: Screenshot → OmniParser → Click → Verify\n")
    
    success = test_automoy_chrome_clicking()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ AUTOMOY CHROME TEST PASSED!")
        print("✅ Chrome was successfully detected and launched by Automoy")
        print("✅ OmniParser → Click → Verify workflow works correctly")
    else:
        print("❌ AUTOMOY CHROME TEST FAILED!")
        print("❌ Chrome was not launched by the Automoy system")
    print("=" * 60)
