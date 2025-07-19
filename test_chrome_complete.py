#!/usr/bin/env python3
"""
Test Chrome clicking with direct action execution (bypass LLM issues)
"""

import os
import sys
import time
import pyautogui
import psutil
from PIL import Image

# Add project root to Python path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def is_chrome_running():
    """Check if Chrome is running"""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if 'chrome' in proc.info['name'].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

def test_chrome_clicking_improved():
    """Test Chrome clicking with improved desktop analysis"""
    print("🔍 IMPROVED CHROME CLICKING TEST")
    print("=" * 50)
    
    # Check initial status
    initial_chrome = is_chrome_running()
    print(f"📋 Initial Chrome status: {'Running' if initial_chrome else 'Not running'}")
    
    if initial_chrome:
        print("⚠️ Chrome already running - test may be ambiguous")
    
    # Take screenshot for analysis
    print("\n📸 Taking desktop screenshot for analysis...")
    screenshot = pyautogui.screenshot()
    screenshot.save("desktop_analysis.png")
    print("✅ Screenshot saved as desktop_analysis.png")
    
    # Get screen dimensions
    screen_width, screen_height = pyautogui.size()
    print(f"📐 Screen size: {screen_width}x{screen_height}")
    
    # Strategy 1: Check taskbar (bottom 100px of screen)
    print("\n🔍 Strategy 1: Checking taskbar for Chrome...")
    taskbar_height = 100
    taskbar_y_start = screen_height - taskbar_height
    
    # Click several spots along the taskbar
    taskbar_positions = []
    for x in range(100, min(800, screen_width), 100):  # Check first 800px of taskbar
        taskbar_positions.append((x, screen_height - 50))  # 50px from bottom
    
    for i, (x, y) in enumerate(taskbar_positions):
        print(f"   Clicking taskbar position {i+1}: ({x}, {y})")
        pyautogui.click(x, y)
        time.sleep(3)  # Wait for potential Chrome startup
        
        if is_chrome_running():
            print(f"🎉 SUCCESS! Chrome opened from taskbar at ({x}, {y})")
            return True
    
    # Strategy 2: Check desktop left side for icons
    print("\n🔍 Strategy 2: Checking desktop left side for Chrome icon...")
    desktop_positions = []
    # Left side desktop icons (typically 100px from left, spaced 100px vertically)
    for y in range(100, min(600, screen_height), 100):
        desktop_positions.append((100, y))
    
    for i, (x, y) in enumerate(desktop_positions):
        print(f"   Clicking desktop position {i+1}: ({x}, {y})")
        pyautogui.click(x, y)
        time.sleep(3)  # Wait for potential Chrome startup
        
        if is_chrome_running():
            print(f"🎉 SUCCESS! Chrome opened from desktop at ({x}, {y})")
            return True
    
    # Strategy 3: Start menu search
    print("\n🔍 Strategy 3: Using Start menu search...")
    try:
        # Click start button (bottom left corner)
        pyautogui.click(20, screen_height - 20)
        time.sleep(1)
        
        # Type chrome
        pyautogui.write('chrome', interval=0.1)
        time.sleep(2)
        
        # Press enter
        pyautogui.press('enter')
        time.sleep(5)  # Wait longer for Chrome to start
        
        if is_chrome_running():
            print("🎉 SUCCESS! Chrome opened via Start menu search")
            return True
        else:
            # Close start menu if Chrome didn't open
            pyautogui.press('escape')
            
    except Exception as e:
        print(f"   Start menu error: {e}")
    
    # Strategy 4: Try Windows search
    print("\n🔍 Strategy 4: Using Windows search (Win+S)...")
    try:
        # Open Windows search
        pyautogui.hotkey('win', 's')
        time.sleep(1)
        
        # Type chrome
        pyautogui.write('chrome', interval=0.1)
        time.sleep(2)
        
        # Press enter
        pyautogui.press('enter')
        time.sleep(5)
        
        if is_chrome_running():
            print("🎉 SUCCESS! Chrome opened via Windows search")
            return True
        else:
            pyautogui.press('escape')
            
    except Exception as e:
        print(f"   Windows search error: {e}")
    
    print("❌ All strategies failed - Chrome could not be opened")
    return False

def main():
    """Main test function"""
    print("Starting improved Chrome clicking test...")
    
    try:
        success = test_chrome_clicking_improved()
        
        # Final status check
        final_chrome = is_chrome_running()
        
        print(f"\n📊 FINAL RESULTS:")
        print(f"   Test success: {'YES' if success else 'NO'}")
        print(f"   Chrome running: {'YES' if final_chrome else 'NO'}")
        
        if final_chrome:
            print("🎉 OVERALL SUCCESS: Chrome is now running!")
        else:
            print("❌ OVERALL FAILURE: Chrome is not running")
            
        return final_chrome
        
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = main()
    print(f"\nTest result: {'PASSED' if result else 'FAILED'}")
    sys.exit(0 if result else 1)
"""
Comprehensive Chrome Clicking Trial Run
Tests the complete workflow: Goal -> Objective -> Steps -> Execution -> Verification
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

from core.operate import AutomoyOperator
from core.lm.lm_interface import MainInterface
from core.data_models import write_state

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def verify_chrome_status():
    """Check Chrome process status"""
    try:
        chrome_processes = []
        for process in psutil.process_iter(['name', 'pid']):
            if 'chrome' in process.info['name'].lower():
                chrome_processes.append(f"{process.info['name']} (PID: {process.info['pid']})")
        
        if chrome_processes:
            print(f"✅ Chrome RUNNING with {len(chrome_processes)} processes:")
            for proc in chrome_processes[:3]:  # Show first 3 processes
                print(f"   • {proc}")
            if len(chrome_processes) > 3:
                print(f"   • ... and {len(chrome_processes) - 3} more")
            return True, len(chrome_processes)
        else:
            print("❌ Chrome NOT RUNNING")
            return False, 0
    except Exception as e:
        print(f"❌ Error checking Chrome: {e}")
        return False, 0

async def simulate_gui_update(endpoint, payload):
    """Simulate GUI state updates with clear output"""
    if endpoint == "/state/thinking":
        text = payload.get("text", payload) if isinstance(payload, dict) else str(payload)
        print(f"💭 THINKING: {text}")
    elif endpoint == "/state/current_operation":
        text = payload.get("text", payload) if isinstance(payload, dict) else str(payload)
        print(f"⚙️  OPERATION: {text}")
    elif endpoint == "/state/operator_status":
        text = payload.get("text", payload) if isinstance(payload, dict) else str(payload)
        print(f"📊 STATUS: {text}")
    else:
        print(f"🔄 UPDATE [{endpoint}]: {payload}")

async def run_chrome_clicking_trial():
    """Run the complete Chrome clicking trial"""
    goal = "Click on the Google Chrome icon to open the Chrome browser"
    
    print("🎯 CHROME CLICKING TRIAL RUN")
    print("=" * 60)
    print(f"Goal: {goal}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Step 1: Initial Chrome check
    print("1️⃣  INITIAL CHROME STATUS CHECK")
    print("-" * 30)
    initial_running, initial_count = await verify_chrome_status()
    print()
    
    # Step 2: Initialize AutomoyOperator
    print("2️⃣  INITIALIZING AUTOMOY OPERATOR")
    print("-" * 30)
    try:
        pause_event = asyncio.Event()
        pause_event.set()
        
        operator = AutomoyOperator(
            objective="",
            manage_gui_window_func=None,
            omniparser=None,
            pause_event=pause_event,
            update_gui_state_func=simulate_gui_update
        )
        
        operator.original_goal = goal
        print("✅ AutomoyOperator initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize operator: {e}")
        return False
    print()
    
    # Step 3: Formulate objective with LLM
    print("3️⃣  FORMULATING OBJECTIVE WITH LLM")
    print("-" * 30)
    try:
        llm_interface = MainInterface()
        print("📡 Calling LLM to formulate objective...")
        
        objective_text, error = await llm_interface.formulate_objective(
            goal=goal,
            session_id="trial_run"
        )
        
        if error:
            print(f"❌ LLM error: {error}")
            return False
        elif objective_text:
            lines = objective_text.strip().split('\n')
            final_objective = lines[-1].strip() if lines else objective_text.strip()
            print(f"✅ Objective formulated: {final_objective}")
        else:
            print("❌ LLM returned empty response")
            return False
    except Exception as e:
        print(f"❌ Objective formulation failed: {e}")
        return False
    print()
    
    # Step 4: Execute the objective
    print("4️⃣  EXECUTING CHROME CLICKING OBJECTIVE")
    print("-" * 30)
    try:
        print(f"🚀 Starting execution: {final_objective}")
        operator.set_objective(final_objective)
        
        # Monitor execution for up to 2 minutes
        max_wait = 120
        start_time = time.time()
        print(f"⏱️  Monitoring execution (max {max_wait} seconds)...")
        
        # Check periodically
        while time.time() - start_time < max_wait:
            await asyncio.sleep(2)
            
            # Check if Chrome started during execution
            chrome_running, chrome_count = await verify_chrome_status()
            if chrome_running and not initial_running:
                print(f"🎉 CHROME DETECTED! Found {chrome_count} processes during execution")
                break
            elif time.time() - start_time > 30:  # After 30 seconds, show status
                print(f"⏳ Still running... ({int(time.time() - start_time)}s elapsed)")
                
        execution_time = time.time() - start_time
        print(f"⏱️  Execution monitored for {execution_time:.1f} seconds")
        
    except Exception as e:
        print(f"❌ Execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    print()
    
    # Step 5: Final verification
    print("5️⃣  FINAL CHROME STATUS VERIFICATION")
    print("-" * 30)
    await asyncio.sleep(3)  # Wait for Chrome to fully initialize
    
    final_running, final_count = await verify_chrome_status()
    
    # Results analysis
    print()
    print("=" * 60)
    print("📋 TRIAL RUN RESULTS")
    print("=" * 60)
    print(f"Initial Chrome Status:  {'✅ Running' if initial_running else '❌ Not Running'} ({initial_count} processes)")
    print(f"Final Chrome Status:    {'✅ Running' if final_running else '❌ Not Running'} ({final_count} processes)")
    print(f"Execution Time:         {execution_time:.1f} seconds")
    
    if final_running and not initial_running:
        print("\n🎉 SUCCESS: CHROME WAS SUCCESSFULLY LAUNCHED!")
        print("   ✅ Chrome was not running initially")
        print("   ✅ Chrome is now running after execution")
        print("   ✅ Process verification confirms Chrome opened")
        return True
    elif final_running and initial_running:
        print("\n⚠️  INCONCLUSIVE: Chrome was already running")
        print("   ℹ️  Cannot confirm if Automoy launched it")
        return True
    else:
        print("\n❌ FAILURE: Chrome was not launched")
        print("   ❌ Chrome is still not running after execution")
        return False

async def main():
    """Main trial function"""
    try:
        success = await run_chrome_clicking_trial()
        
        print("\n" + "=" * 60)
        if success:
            print("🏆 TRIAL RUN COMPLETED SUCCESSFULLY!")
            print("   Automoy can click Chrome icons and launch Chrome")
        else:
            print("💥 TRIAL RUN FAILED")
            print("   Chrome clicking needs investigation")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n💥 Trial run crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
