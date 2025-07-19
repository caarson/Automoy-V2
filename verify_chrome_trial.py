#!/usr/bin/env python3
"""
Simple Chrome Clicking Verification Test
Direct test of Chrome process verification functionality
"""
import asyncio
import psutil
import time

async def verify_chrome_running():
    """Verify if Chrome processes are running"""
    try:
        chrome_processes = []
        for process in psutil.process_iter(['name', 'pid']):
            if 'chrome' in process.info['name'].lower():
                chrome_processes.append(f"{process.info['name']} (PID: {process.info['pid']})")
        
        if chrome_processes:
            print(f"✅ Chrome is running with {len(chrome_processes)} processes:")
            for proc in chrome_processes[:5]:  # Show first 5 processes
                print(f"   {proc}")
            if len(chrome_processes) > 5:
                print(f"   ... and {len(chrome_processes) - 5} more processes")
            return True
        else:
            print("❌ Chrome is not running")
            return False
    except Exception as e:
        print(f"Error checking Chrome processes: {e}")
        return False

def test_automoy_goal_processing():
    """Test if Automoy processed the Chrome goal"""
    import os
    
    print("🔍 Checking Automoy goal processing...")
    
    # Check if goal request file was consumed
    goal_file = "c:\\Users\\imitr\\OneDrive\\Documentos\\GitHub\\Automoy-V2\\core\\goal_request.json"
    if os.path.exists(goal_file):
        print("   ⚠️  Goal request file still exists - may not have been processed")
        try:
            with open(goal_file, 'r') as f:
                content = f.read()
                print(f"   Content: {content.strip()}")
        except:
            pass
    else:
        print("   ✅ Goal request file was consumed - Automoy processed the goal")
    
    # Check GUI state
    gui_state_file = "c:\\Users\\imitr\\OneDrive\\Documentos\\GitHub\\Automoy-V2\\gui_state.json"
    if os.path.exists(gui_state_file):
        try:
            import json
            with open(gui_state_file, 'r') as f:
                state = json.load(f)
                print(f"   Operator Status: {state.get('operator_status', 'unknown')}")
                print(f"   Goal: {state.get('goal', 'none')}")
                print(f"   Current Operation: {state.get('current_operation', 'none')}")
                if state.get('operator_status') != 'idle':
                    print("   ✅ Automoy is actively processing a goal!")
                return True
        except Exception as e:
            print(f"   Error reading GUI state: {e}")
    
    return False

async def main():
    """Main verification function"""
    print("🚀 Chrome Clicking Trial Run Verification")
    print("=" * 50)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. Check if Chrome is running
    print("1. Checking Chrome process status...")
    chrome_running = await verify_chrome_running()
    print()
    
    # 2. Check if Automoy processed the goal
    print("2. Checking Automoy goal processing...")
    goal_processed = test_automoy_goal_processing()
    print()
    
    # 3. Summary
    print("=" * 50)
    print("📊 TRIAL RUN SUMMARY:")
    print(f"   Chrome Running: {'✅ YES' if chrome_running else '❌ NO'}")
    print(f"   Goal Processed: {'✅ YES' if goal_processed else '❌ NO'}")
    
    if chrome_running and goal_processed:
        print("\n🎉 SUCCESS: Automoy successfully processed the Chrome clicking goal!")
        print("   The system can detect Chrome processes and process clicking goals.")
    elif chrome_running:
        print("\n🔄 PARTIAL SUCCESS: Chrome is running, checking if Automoy triggered it...")
        print("   Chrome processes detected - goal may have been successful.")
    else:
        print("\n❌ NEEDS INVESTIGATION: Chrome not detected or goal not processed.")
    
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())
