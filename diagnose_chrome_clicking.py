#!/usr/bin/env python3
"""
Diagnose Chrome clicking issues step by step
"""

import os
import sys
import asyncio
import time
import json

# Add project root to Python path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

async def diagnose_chrome_clicking():
    """Diagnose each step of the Chrome clicking process"""
    print("=== Chrome Clicking Diagnosis ===")
    
    # Step 1: Test screenshot capture
    print("\n1. Testing Screenshot Capture:")
    try:
        from core.utils.screenshot_utils import capture_screen_pil
        screenshot = capture_screen_pil()
        if screenshot:
            print("✅ Screenshot capture working")
            # Save screenshot for inspection
            screenshot.save("debug_screenshot.png")
            print("✅ Screenshot saved as debug_screenshot.png")
        else:
            print("❌ Screenshot capture failed")
            return False
    except Exception as e:
        print(f"❌ Screenshot error: {e}")
        return False
    
    # Step 2: Test OmniParser
    print("\n2. Testing OmniParser:")
    try:
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        manager = OmniParserServerManager()
        
        if manager.is_server_ready():
            print("✅ OmniParser server is running")
            
            # Test visual analysis
            omniparser = manager.get_interface()
            if omniparser:
                print("✅ OmniParser interface obtained")
                
                # Test with our screenshot
                result = await omniparser.analyze_image(screenshot)
                if result:
                    print("✅ OmniParser analysis completed")
                    print(f"   Analysis result length: {len(str(result))}")
                    
                    # Check if Chrome is mentioned in results
                    result_str = str(result).lower()
                    if 'chrome' in result_str:
                        print("✅ Chrome detected in visual analysis")
                    else:
                        print("⚠ Chrome not detected in visual analysis")
                        print("   This could mean:")
                        print("   - Chrome icon not visible on desktop")
                        print("   - Chrome icon in taskbar/start menu only")
                        print("   - OmniParser needs better prompting")
                else:
                    print("❌ OmniParser analysis failed")
                    return False
            else:
                print("❌ Could not get OmniParser interface")
                return False
        else:
            print("❌ OmniParser server not running")
            return False
    except Exception as e:
        print(f"❌ OmniParser error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 3: Test LLM step generation
    print("\n3. Testing LLM Step Generation:")
    try:
        from core.lm.lm_interface import MainInterface
        llm = MainInterface()
        print("✅ LLM interface initialized")
        
        # Test objective formulation
        objective_text, error = await llm.formulate_objective(
            goal="Click on the Google Chrome icon to open the browser",
            session_id="test"
        )
        
        if error:
            print(f"❌ Objective formulation failed: {error}")
            return False
        elif objective_text:
            print("✅ Objective formulated successfully")
            print(f"   Objective: {objective_text}")
        else:
            print("❌ Empty objective returned")
            return False
            
    except Exception as e:
        print(f"❌ LLM error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 4: Test action execution capabilities
    print("\n4. Testing Action Execution:")
    try:
        from core.utils.operating_system.desktop_utils import DesktopUtils
        desktop = DesktopUtils()
        print("✅ Desktop utilities initialized")
        
        # Test if we can execute a simple action (Windows key)
        print("   Testing Windows key press...")
        import pyautogui
        pyautogui.press('win')
        await asyncio.sleep(1)
        pyautogui.press('escape')  # Close start menu if opened
        print("✅ Action execution working")
        
    except Exception as e:
        print(f"❌ Action execution error: {e}")
        return False
    
    print("\n5. Summary:")
    print("✅ All components are functional")
    print("🔍 Next steps to fix Chrome clicking:")
    print("   1. Ensure Chrome icon is visible on desktop")
    print("   2. Improve visual analysis prompting for Chrome detection")
    print("   3. Generate proper click coordinates")
    print("   4. Execute click at correct location")
    
    return True

async def main():
    """Main diagnostic function"""
    success = await diagnose_chrome_clicking()
    
    if success:
        print("\n✅ DIAGNOSIS COMPLETE - Components working")
        print("Issue likely in integration or Chrome icon visibility")
    else:
        print("\n❌ DIAGNOSIS FAILED - Found component issues")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\nDiagnosis Result: {'PASSED' if result else 'FAILED'}")
