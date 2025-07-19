#!/usr/bin/env python3
"""
Direct Automoy Chrome test - bypass goal file polling
"""

import os
import sys
import asyncio
import time
import psutil

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

async def test_direct_automoy_chrome():
    """Test Chrome opening by directly using Automoy components"""
    print("🧪 DIRECT AUTOMOY CHROME CLICKING TEST")
    print("=" * 60)
    
    # Check initial Chrome status
    initial_chrome = is_chrome_running()
    print(f"📋 Initial Chrome status: {'Running' if initial_chrome else 'Not running'}")
    
    if initial_chrome:
        print("⚠️ Chrome already running - stopping for clean test")
        # Kill existing Chrome processes
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'chrome' in proc.info['name'].lower():
                    proc.terminate()
                    proc.wait(timeout=5)
            except:
                pass
        time.sleep(2)
    
    try:
        # Import Automoy components
        print("🔧 Initializing Automoy components...")
        
        from core.operate import AutomoyOperator
        from core.config import Config
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        
        # Initialize OmniParser
        print("🔍 Starting OmniParser for visual analysis...")
        omniparser_manager = OmniParserServerManager()
        
        if not omniparser_manager.is_server_ready():
            server_process = omniparser_manager.start_server()
            if server_process and omniparser_manager.wait_for_server(timeout=60):
                print("✅ OmniParser server started successfully")
                omniparser = omniparser_manager.get_interface()
            else:
                print("❌ Failed to start OmniParser server")
                omniparser = None
        else:
            print("✅ OmniParser server already running")
            omniparser = omniparser_manager.get_interface()
        
        # Create a simple GUI state update function
        async def dummy_gui_update(endpoint, payload):
            print(f"GUI Update: {endpoint} -> {payload}")
        
        # Create a simple window management function
        async def dummy_window_manager(action):
            print(f"Window action: {action}")
            return True
        
        # Create pause event
        pause_event = asyncio.Event()
        pause_event.set()  # Start unpaused
        
        # Initialize AutomoyOperator
        print("🤖 Initializing AutomoyOperator...")
        operator = AutomoyOperator(
            objective="Open Google Chrome by clicking its icon",
            manage_gui_window_func=dummy_window_manager,
            omniparser=omniparser,
            pause_event=pause_event,
            update_gui_state_func=dummy_gui_update
        )
        
        # Initialize desktop utilities
        try:
            from core.utils.operating_system.desktop_utils import DesktopUtils
            operator.desktop_utils = DesktopUtils()
            print("✅ Desktop utilities initialized")
        except Exception as e:
            print(f"⚠️ Desktop utilities failed: {e}")
            operator.desktop_utils = None
        
        print("🚀 Starting Chrome opening operation...")
        print("📸 This will:")
        print("   1. Take a screenshot of the desktop")
        print("   2. Use OmniParser to analyze and find Chrome icon")
        print("   3. Use LLM to plan the clicking action")
        print("   4. Execute the click at the correct coordinates")
        print("   5. Verify Chrome opened")
        
        # Set the objective and start operation
        operator.set_objective("Open Google Chrome by clicking its icon")
        
        # Wait for operation to complete or timeout
        print("⏳ Waiting for operation to complete...")
        
        # Monitor for Chrome opening for up to 120 seconds
        start_time = time.time()
        timeout = 120
        
        while time.time() - start_time < timeout:
            if is_chrome_running():
                print("🎉 SUCCESS! Chrome is now running!")
                print(f"✅ Test completed in {time.time() - start_time:.1f} seconds")
                return True
            await asyncio.sleep(2)
        
        print("⏰ Timeout reached - Chrome did not open")
        return False
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    try:
        result = await test_direct_automoy_chrome()
        
        final_chrome = is_chrome_running()
        
        print(f"\n📊 FINAL RESULTS:")
        print(f"   Test result: {'SUCCESS' if result else 'FAILED'}")
        print(f"   Chrome running: {'YES' if final_chrome else 'NO'}")
        
        if final_chrome:
            print("🎉 OVERALL SUCCESS: Chrome was opened by Automoy!")
        else:
            print("❌ OVERALL FAILURE: Chrome was not opened")
            
        return result
        
    except Exception as e:
        print(f"❌ Main test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\nExiting with result: {'PASSED' if result else 'FAILED'}")
    sys.exit(0 if result else 1)
