#!/usr/bin/env python3
"""
Simple Chrome clicking test using Automoy's action executor
"""

import os
import sys
import time
import psutil
from pathlib import Path

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

def test_chrome_simple_click():
    """Test Chrome opening by clicking common icon locations"""
    print("🧪 SIMPLE CHROME CLICKING TEST")
    print("=" * 50)
    
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
        # Import Automoy action executor
        print("🔧 Initializing action executor...")
        from core.operate import ActionExecutor
        
        action_executor = ActionExecutor()
        print("✅ Action executor ready")
        
        # Try multiple common Chrome icon locations
        chrome_locations = [
            # Taskbar locations (common Chrome positions)
            {"x": 100, "y": 740},  # Far left taskbar
            {"x": 150, "y": 740},  # Second position
            {"x": 200, "y": 740},  # Third position
            {"x": 250, "y": 740},  # Fourth position
            
            # Desktop locations (common Chrome positions)
            {"x": 100, "y": 100},  # Top-left desktop
            {"x": 100, "y": 200},  # Second row desktop
            {"x": 200, "y": 100},  # Second column desktop
            
            # Start menu (Windows key + search)
            {"key": "win"},  # Open start menu first
        ]
        
        print("🖱️ Trying different Chrome icon locations...")
        
        for i, location in enumerate(chrome_locations, 1):
            print(f"\n📍 Attempt {i}: ", end="")
            
            if "key" in location:
                # Special case: Open start menu
                print("Opening Start menu...")
                action = {
                    "type": "key",
                    "key": "win",
                    "summary": "Open Start menu"
                }
                result = action_executor.execute(action)
                print(f"   Result: {result}")
                time.sleep(1)
                
                # Type chrome to search
                print("   Typing 'chrome' to search...")
                action = {
                    "type": "type",
                    "text": "chrome",
                    "summary": "Type chrome in search"
                }
                result = action_executor.execute(action)
                print(f"   Result: {result}")
                time.sleep(1)
                
                # Press Enter
                print("   Pressing Enter to launch...")
                action = {
                    "type": "key",
                    "key": "Return",
                    "summary": "Press Enter to launch Chrome"
                }
                result = action_executor.execute(action)
                print(f"   Result: {result}")
                
            else:
                # Click at specific coordinates
                print(f"Clicking at ({location['x']}, {location['y']})")
                action = {
                    "type": "click",
                    "coordinate": [location['x'], location['y']],
                    "summary": f"Click at Chrome icon location ({location['x']}, {location['y']})"
                }
                result = action_executor.execute(action)
                print(f"   Result: {result}")
            
            # Wait and check if Chrome opened
            time.sleep(3)
            if is_chrome_running():
                print("🎉 SUCCESS! Chrome is now running!")
                print(f"✅ Chrome opened after attempt {i}")
                return True
            else:
                print("   Chrome not detected - trying next location...")
        
        print("\n❌ FAILED: Chrome did not open with any method")
        return False
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_chrome_simple_click()
    
    # Final verification
    print("\n" + "=" * 50)
    final_chrome = is_chrome_running()
    print(f"🔍 Final Chrome status: {'✅ RUNNING' if final_chrome else '❌ NOT RUNNING'}")
    
    if success and final_chrome:
        print("🎊 TEST PASSED: Chrome successfully opened!")
    else:
        print("💥 TEST FAILED: Chrome was not opened")
    
    exit(0 if success else 1)
