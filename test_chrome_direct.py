#!/usr/bin/env python3
"""
Direct Chrome Testing with Process Verification
"""
import asyncio
import sys
import os
import time
import psutil

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.operate import ActionExecutor

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

async def execute_chrome_steps():
    """Execute the hardcoded Chrome steps and verify process"""
    print("=== Starting Chrome Launch Test ===")
    
    action_executor = ActionExecutor()
    
    # Step 1: Press Windows key
    print("\nStep 1: Press Windows key to open Start menu")
    action1 = {"action_type": "key", "target": "win"}
    result1 = action_executor.execute(action1)
    print(f"Step 1 result: {result1}")
    await asyncio.sleep(1)
    
    # Step 2: Type 'chrome'
    print("\nStep 2: Type 'chrome' to search")
    action2 = {"action_type": "type", "target": "chrome"}
    result2 = action_executor.execute(action2)
    print(f"Step 2 result: {result2}")
    await asyncio.sleep(1)
    
    # Step 3: Press Enter
    print("\nStep 3: Press Enter to launch Chrome")
    action3 = {"action_type": "key", "target": "enter"}
    result3 = action_executor.execute(action3)
    print(f"Step 3 result: {result3}")
    
    # Wait for Chrome to start
    print("\nWaiting 3 seconds for Chrome to start...")
    await asyncio.sleep(3)
    
    # Verify Chrome is running
    print("\n=== Process Verification ===")
    chrome_running = await verify_process_running("chrome.exe")
    
    if chrome_running:
        print("✅ SUCCESS: Chrome launched successfully and is running!")
        return True
    else:
        print("❌ FAILURE: Chrome process not detected after launch sequence")
        return False

async def main():
    """Main test function"""
    print("Chrome Launch Test with Process Verification")
    print("=" * 50)
    
    # Check if Chrome is already running
    print("Initial process check:")
    already_running = await verify_process_running("chrome.exe")
    if already_running:
        print("Chrome is already running. Test will still proceed.")
    
    print(f"\nStarting test at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        success = await execute_chrome_steps()
        if success:
            print("\n🎉 Chrome launch test PASSED!")
        else:
            print("\n❌ Chrome launch test FAILED!")
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
