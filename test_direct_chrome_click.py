#!/usr/bin/env python3
"""
Direct Chrome Icon Clicking Test - Minimal dependencies
"""

import os
import sys
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

def test_direct_chrome_click():
    """Test Chrome clicking with direct pyautogui"""
    print("🎯 DIRECT CHROME ICON CLICKING TEST")
    print("=" * 50)
    
    # Clean state
    if is_chrome_running():
        print("⚠️ Chrome running - stopping for clean test")
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'chrome' in proc.info['name'].lower():
                    proc.terminate()
                    proc.wait(timeout=5)
            except:
                pass
        time.sleep(2)
    
    print("📋 Initial state: Chrome not running")
    
    try:
        # Import pyautogui directly
        print("🔧 Importing pyautogui...")
        import pyautogui
        pyautogui.FAILSAFE = False
        print("✅ pyautogui ready")
        
        # Try clicking common Chrome icon positions in taskbar
        print("🖱️ Attempting to click Chrome icon positions...")
        
        chrome_positions = [
            (100, 740),   # Position 1
            (150, 740),   # Position 2
            (200, 740),   # Position 3
            (250, 740),   # Position 4
            (60, 740),    # Far left
            (300, 740),   # Position 5
            (350, 740),   # Position 6
        ]
        
        for i, (x, y) in enumerate(chrome_positions, 1):
            print(f"   🎯 Clicking position {i}: ({x}, {y})")
            
            # Perform the click
            pyautogui.click(x, y)
            print(f"      ✅ Click executed at ({x}, {y})")
            
            # Wait for Chrome to start
            time.sleep(3)
            
            # Check if Chrome is now running
            if is_chrome_running():
                print(f"🎉 SUCCESS! Chrome opened from position {i}")
                print(f"✅ Chrome process detected and running")
                return True
            else:
                print(f"      ❌ Chrome not detected after clicking position {i}")
        
        print("💥 FAILED: Chrome did not open from any position")
        return False
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_direct_chrome_click()
    
    print("\n" + "=" * 50)
    
    # Final verification
    final_status = is_chrome_running()
    print(f"🔍 Final Chrome status: {'✅ RUNNING' if final_status else '❌ NOT RUNNING'}")
    print(f"🏁 TEST RESULT: {'✅ PASS' if success and final_status else '❌ FAIL'}")
    
    if success and final_status:
        print("🎊 Chrome successfully opened by clicking taskbar icon!")
        print("📝 Leaving Chrome open for verification")
    else:
        print("💥 Test failed - Chrome icon clicking unsuccessful")
        print("🔧 Possible issues:")
        print("   - Chrome icon not in expected taskbar positions")
        print("   - Need to adjust click coordinates")
        print("   - Chrome may be pinned elsewhere")
    
    exit(0 if success else 1)
