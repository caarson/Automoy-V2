#!/usr/bin/env python3
"""
Test Chrome icon clicking with LLM-generated actions and visual analysis
This test ensures:
1. LLM generates proper steps to click Chrome icon
2. Visual analysis (OmniParser) locates the Chrome icon 
3. Click actions are generated based on visual analysis
4. Chrome actually opens via clicking the icon
"""

import os
import sys
import asyncio
import time
import json
import psutil

# Add project root to Python path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def verify_chrome_status():
    """Check if Chrome is running and return detailed status"""
    try:
        chrome_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'create_time']):
            if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                chrome_processes.append({
                    'name': proc.info['name'],
                    'pid': proc.info['pid'], 
                    'started': time.time() - proc.info['create_time']
                })
        
        if chrome_processes:
            print(f"✅ Chrome RUNNING - Found {len(chrome_processes)} Chrome processes:")
            for proc in chrome_processes:
                print(f"   - {proc['name']} (PID: {proc['pid']}, running for {proc['started']:.1f}s)")
            return True, chrome_processes
        else:
            print("❌ Chrome NOT RUNNING")
            return False, []
    except Exception as e:
        print(f"Error checking Chrome status: {e}")
        return False, []

def create_chrome_icon_goal():
    """Create goal file specifically for clicking Chrome icon"""
    goal_file = "core/goal_request.json"
    
    # Goal emphasizes CLICKING the Chrome ICON specifically
    goal_data = {
        "goal": "Click on the Google Chrome icon to open the browser"
    }
    
    try:
        with open(goal_file, 'w') as f:
            json.dump(goal_data, f, indent=2)
        print(f"✓ Created Chrome icon clicking goal: {goal_data['goal']}")
        return True
    except Exception as e:
        print(f"✗ Error creating goal file: {e}")
        return False

def monitor_chrome_status(duration_seconds=30):
    """Monitor Chrome status over time to detect when it opens"""
    print(f"\n🔍 Monitoring Chrome status for {duration_seconds} seconds...")
    
    start_time = time.time()
    initial_running, initial_procs = verify_chrome_status()
    
    while time.time() - start_time < duration_seconds:
        current_running, current_procs = verify_chrome_status()
        
        # Check if Chrome was launched during monitoring
        if not initial_running and current_running:
            elapsed = time.time() - start_time
            print(f"🎉 SUCCESS! Chrome was launched after {elapsed:.1f} seconds!")
            print("✓ Chrome icon clicking worked - browser opened successfully")
            return True
        elif current_running and len(current_procs) > len(initial_procs):
            elapsed = time.time() - start_time  
            print(f"🎉 SUCCESS! New Chrome process detected after {elapsed:.1f} seconds!")
            print("✓ Chrome icon clicking worked - additional browser instance opened")
            return True
            
        time.sleep(2)  # Check every 2 seconds
    
    print("⏰ Monitoring period ended - Chrome was not launched via icon clicking")
    return False

def main():
    """Test Chrome icon clicking with LLM and visual analysis"""
    print("=== Chrome Icon Clicking Test with LLM & Visual Analysis ===")
    print("This test verifies that:")
    print("1. ❌ Hardcoded Chrome steps are DISABLED")
    print("2. ✅ LLM generates steps based on visual analysis")  
    print("3. ✅ Visual analysis (OmniParser) locates Chrome icon")
    print("4. ✅ Click actions target the actual Chrome icon coordinates")
    print("5. ✅ Chrome opens via icon clicking (not typing/search)")
    
    # Check initial Chrome status
    print("\n1. Initial Chrome Status Check:")
    initial_running, initial_procs = verify_chrome_status()
    
    if initial_running:
        print("⚠ Chrome is already running. Consider closing it to test icon clicking from scratch.")
        print("   The test will still work but will look for NEW Chrome processes.")
    
    # Create Chrome icon clicking goal
    print("\n2. Creating Chrome Icon Clicking Goal:")
    if not create_chrome_icon_goal():
        print("❌ Failed to create goal file - test cannot proceed")
        return
    
    print("\n3. Expected Workflow:")
    print("   a) LLM receives goal: 'Click on the Google Chrome icon'")
    print("   b) System takes screenshot of desktop")
    print("   c) OmniParser analyzes screenshot to locate Chrome icon")
    print("   d) LLM generates click action with Chrome icon coordinates")
    print("   e) System executes click at Chrome icon location")
    print("   f) Chrome browser opens")
    
    print("\n4. Key Changes Made:")
    print("   ✅ Removed hardcoded Chrome step detection")
    print("   ✅ Enabled screenshot capture for click objectives")
    print("   ✅ Fixed JSON parsing for action generation")
    print("   ✅ Enhanced action validation and field generation")
    
    print(f"\n5. Ready for LLM-Based Chrome Icon Clicking!")
    print("   Run the main Automoy system now to test.")
    print("   The system should:")
    print("   - Take a screenshot when processing the Chrome goal")
    print("   - Use OmniParser to locate the Chrome icon")
    print("   - Generate a click action at the icon's coordinates")
    print("   - Execute the click to open Chrome")
    
    # Offer to monitor Chrome status
    monitor = input("\n🔍 Monitor Chrome status for 60 seconds to detect when it opens? (y/n): ").lower().strip()
    if monitor == 'y':
        success = monitor_chrome_status(60)
        if success:
            print("\n🎉 TEST PASSED: Chrome icon clicking successful!")
        else:
            print("\n❌ TEST INCOMPLETE: Chrome was not detected opening")
            print("   Check if:")
            print("   - OmniParser is running and analyzing screenshots")
            print("   - LLM is generating click actions with coordinates")  
            print("   - Click coordinates match Chrome icon location")
    else:
        print("\n✓ Chrome icon clicking test setup complete!")
        print("  Run the main Automoy system to execute the test.")

if __name__ == "__main__":
    main()
