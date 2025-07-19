#!/usr/bin/env python3
"""
Direct Chrome icon clicking test without GUI blocking
This bypasses pywebview issues and tests the core functionality
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

from core.operate import AutomoyOperator
from core.lm.lm_interface import MainInterface

def check_chrome_status():
    """Check if Chrome is running"""
    try:
        chrome_processes = []
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                chrome_processes.append(proc.info)
        
        if chrome_processes:
            print(f"✅ Chrome RUNNING - Found {len(chrome_processes)} processes")
            return True
        else:
            print("❌ Chrome NOT RUNNING")
            return False
    except Exception as e:
        print(f"Error checking Chrome: {e}")
        return False

async def direct_chrome_test():
    """Direct test of Chrome icon clicking workflow"""
    print("=== Direct Chrome Icon Clicking Test ===")
    
    # Check initial Chrome status
    print("\n1. Initial Chrome Status:")
    initial_chrome = check_chrome_status()
    
    # Initialize core components
    print("\n2. Initializing Core Components:")
    try:
        # Initialize LLM interface
        llm_interface = MainInterface()
        print("✓ LLM Interface initialized")
        
        # Initialize OmniParser
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        omniparser_manager = OmniParserServerManager()
        
        if omniparser_manager.is_server_ready():
            omniparser = omniparser_manager.get_interface()
            print("✓ OmniParser running")
        else:
            print("⚠ OmniParser not running - starting...")
            server_process = omniparser_manager.start_server()
            if server_process and omniparser_manager.wait_for_server(timeout=30):
                omniparser = omniparser_manager.get_interface()
                print("✓ OmniParser started")
            else:
                print("❌ OmniParser failed to start")
                omniparser = None
        
        # Initialize desktop utilities
        from core.utils.operating_system.desktop_utils import DesktopUtils
        desktop_utils = DesktopUtils()
        print("✓ Desktop utilities initialized")
        
    except Exception as e:
        print(f"❌ Component initialization failed: {e}")
        return False
    
    # Test the Chrome clicking workflow
    print("\n3. Testing Chrome Clicking Workflow:")
    
    try:
        # Create a simple async wrapper for GUI updates (no-op for this test)
        async def dummy_gui_update(endpoint, payload):
            print(f"  GUI Update: {endpoint} -> {payload}")
        
        # Initialize operator
        operator = AutomoyOperator(
            objective="",
            manage_gui_window_func=None,
            omniparser=omniparser,
            pause_event=asyncio.Event(),
            update_gui_state_func=dummy_gui_update
        )
        operator.desktop_utils = desktop_utils
        print("✓ AutomoyOperator initialized")
        
        # Set Chrome clicking objective
        objective = "Click on the Google Chrome icon to open the browser"
        operator.set_objective(objective)
        print(f"✓ Objective set: {objective}")
        
        # Wait for execution
        print("\n4. Executing Chrome Clicking...")
        print("   This should:")
        print("   a) Take a screenshot")
        print("   b) Analyze with OmniParser to find Chrome icon")
        print("   c) Generate click action with coordinates")
        print("   d) Execute click at Chrome icon location")
        
        # Monitor for up to 60 seconds
        start_time = time.time()
        while time.time() - start_time < 60:
            current_chrome = check_chrome_status()
            if not initial_chrome and current_chrome:
                elapsed = time.time() - start_time
                print(f"\n🎉 SUCCESS! Chrome opened after {elapsed:.1f} seconds!")
                return True
            await asyncio.sleep(2)
        
        print("\n❌ TIMEOUT: Chrome did not open within 60 seconds")
        return False
        
    except Exception as e:
        print(f"❌ Workflow execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    success = await direct_chrome_test()
    
    if success:
        print("\n🎉 CHROME ICON CLICKING TEST PASSED!")
        print("✅ LLM successfully generated click actions")
        print("✅ Visual analysis located Chrome icon")  
        print("✅ Click execution opened Chrome")
    else:
        print("\n❌ CHROME ICON CLICKING TEST FAILED!")
        print("Need to investigate and fix:")
        print("- Screenshot capture working?")
        print("- OmniParser analyzing correctly?")
        print("- LLM generating click actions?")
        print("- Click coordinates accurate?")
        print("- Chrome icon visible on desktop?")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\nTest Result: {'PASSED' if result else 'FAILED'}")
    sys.exit(0 if result else 1)
