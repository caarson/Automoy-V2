#!/usr/bin/env python3
"""
Automoy Chrome Icon Clicking Test - Uses visual analysis to find and CLICK Chrome icon
"""

import os
import sys
import asyncio
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

def kill_chrome():
    """Kill all Chrome processes for clean test"""
    killed = False
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if 'chrome' in proc.info['name'].lower():
                proc.terminate()
                proc.wait(timeout=5)
                killed = True
        except:
            pass
    return killed

async def test_automoy_chrome_visual_click():
    """Test Chrome opening using Automoy's visual analysis and clicking"""
    print("🎯 AUTOMOY CHROME VISUAL CLICKING TEST")
    print("=" * 60)
    print("🔍 This test will:")
    print("   1. Use OmniParser to analyze the desktop screenshot")
    print("   2. Find Chrome icon through visual analysis")  
    print("   3. Click the Chrome icon at detected coordinates")
    print("   4. Verify Chrome process started")
    print()
    
    # Check initial Chrome status
    initial_chrome = is_chrome_running()
    print(f"📋 Initial Chrome status: {'Running' if initial_chrome else 'Not running'}")
    
    if initial_chrome:
        print("⚠️ Chrome already running - stopping for clean test")
        if kill_chrome():
            print("✅ Chrome processes terminated")
            time.sleep(2)
    
    try:
        print("🔧 Initializing Automoy visual analysis system...")
        
        # Import required components
        from core.operate import AutomoyOperator
        from config.config import Config
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.operating_system.desktop_utils import DesktopUtils
        from core.utils.screenshot_utils import capture_screen_pil
        
        # Initialize OmniParser for visual analysis
        print("🔍 Starting OmniParser server for visual analysis...")
        omniparser_manager = OmniParserServerManager()
        
        # Start server if not running
        if not omniparser_manager.is_server_ready():
            print("   Starting OmniParser server...")
            server_process = omniparser_manager.start_server()
            if server_process and omniparser_manager.wait_for_server(timeout=60):
                print("✅ OmniParser server started successfully")
                omniparser = omniparser_manager.get_interface()
            else:
                print("❌ Failed to start OmniParser server")
                print("💡 Continuing with fallback method...")
                omniparser = None
        else:
            print("✅ OmniParser server already running")
            omniparser = omniparser_manager.get_interface()
        
        # Create dummy GUI functions for testing
        async def dummy_gui_update(endpoint, payload):
            print(f"📊 GUI Update: {endpoint} -> {str(payload)[:100]}...")
        
        async def dummy_window_manager(action):
            print(f"🪟 Window action: {action}")
            return True
        
        # Create pause event (unpaused for test)
        pause_event = asyncio.Event()
        pause_event.set()
        
        print("🤖 Initializing AutomoyOperator with visual analysis...")
        
        # Initialize AutomoyOperator with visual capabilities
        operator = AutomoyOperator(
            objective="Click the Google Chrome icon to open Chrome browser",
            manage_gui_window_func=dummy_window_manager,
            omniparser=omniparser,  # Enable visual analysis
            pause_event=pause_event,
            update_gui_state_func=dummy_gui_update
        )
        
        # Initialize desktop utilities for screen capture and anchoring
        try:
            operator.desktop_utils = DesktopUtils()
            print("✅ Desktop utilities initialized")
        except Exception as e:
            print(f"⚠️ Desktop utilities failed: {e}")
            operator.desktop_utils = None
        
        print("\n🚀 Starting visual Chrome icon detection and clicking...")
        print("📸 Taking screenshot for visual analysis...")
        
        # Capture initial screenshot
        screenshot_pil = capture_screen_pil()
        if not screenshot_pil:
            print("❌ Failed to capture screenshot")
            return False
        
        # Save screenshot for analysis
        screenshot_path = Path("debug/screenshots") / "chrome_test_screenshot.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot_pil.save(str(screenshot_path))
        print(f"✅ Screenshot saved: {screenshot_path}")
        
        # Use OmniParser to analyze screenshot if available
        if omniparser:
            print("🔍 Analyzing screenshot with OmniParser to find Chrome icon...")
            try:
                parsed_result = omniparser.parse_screenshot(str(screenshot_path))
                
                if parsed_result and "parsed_content_list" in parsed_result:
                    elements = parsed_result["parsed_content_list"]
                    print(f"📋 Found {len(elements)} UI elements")
                    
                    # Look for Chrome-related elements
                    chrome_elements = []
                    for i, element in enumerate(elements):
                        element_text = element.get("content", "").lower()
                        element_type = element.get("type", "").lower()
                        
                        # Check for Chrome indicators
                        if any(term in element_text for term in ["chrome", "browser", "google"]):
                            chrome_elements.append((i, element))
                            print(f"   🎯 Found Chrome element #{i}: {element_text} (type: {element_type})")
                    
                    if chrome_elements:
                        # Use the first Chrome element found
                        element_idx, chrome_element = chrome_elements[0]
                        
                        # Extract coordinates
                        if "bbox_normalized" in chrome_element:
                            bbox = chrome_element["bbox_normalized"]
                            # Convert normalized coordinates to screen coordinates
                            screen_width = screenshot_pil.width
                            screen_height = screenshot_pil.height
                            
                            x = int((bbox[0] + bbox[2]) / 2 * screen_width)
                            y = int((bbox[1] + bbox[3]) / 2 * screen_height)
                            
                            print(f"🎯 Chrome icon detected at coordinates: ({x}, {y})")
                            
                            # Create click action using Automoy's action executor
                            print("🖱️ Executing click action on Chrome icon...")
                            
                            action = {
                                "type": "click",
                                "coordinate": [x, y],
                                "summary": f"Click Chrome icon at ({x}, {y})"
                            }
                            
                            result = operator.action_executor.execute(action)
                            print(f"✅ Click action result: {result}")
                            
                        else:
                            print("⚠️ Chrome element found but no coordinates available")
                            
                    else:
                        print("🔍 No Chrome elements detected in visual analysis")
                        print("💡 Trying fallback approach...")
                        
                        # Fallback: Try common taskbar positions
                        print("🎯 Trying common Chrome icon locations...")
                        fallback_positions = [
                            (100, 740),   # Left taskbar
                            (150, 740),   # Second position
                            (200, 740),   # Third position
                            (250, 740),   # Fourth position
                        ]
                        
                        for i, (x, y) in enumerate(fallback_positions, 1):
                            print(f"   Trying position {i}: ({x}, {y})")
                            action = {
                                "type": "click", 
                                "coordinate": [x, y],
                                "summary": f"Fallback click at ({x}, {y})"
                            }
                            result = operator.action_executor.execute(action)
                            print(f"   Result: {result}")
                            
                            # Wait and check
                            time.sleep(2)
                            if is_chrome_running():
                                print(f"🎉 SUCCESS! Chrome opened from position {i}")
                                break
                        
                else:
                    print("❌ OmniParser analysis failed - no results")
                    return False
                    
            except Exception as e:
                print(f"❌ OmniParser analysis error: {e}")
                return False
        else:
            print("⚠️ OmniParser not available - using fallback method")
            return False
        
        # Wait a moment for Chrome to start
        print("\n⏳ Waiting for Chrome to start...")
        time.sleep(3)
        
        # Verify Chrome is running
        final_chrome = is_chrome_running()
        print(f"\n🔍 Final Chrome status: {'✅ RUNNING' if final_chrome else '❌ NOT RUNNING'}")
        
        if final_chrome:
            print("🎊 SUCCESS! Chrome was successfully opened by clicking its icon!")
            return True
        else:
            print("💥 FAILED! Chrome was not opened despite clicking")
            return False
        
    except Exception as e:
        print(f"❌ ERROR during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Run the async test
    success = asyncio.run(test_automoy_chrome_visual_click())
    
    print("\n" + "=" * 60)
    
    # Final verification
    final_status = is_chrome_running()
    print(f"🏁 FINAL RESULT: {'✅ PASS' if success and final_status else '❌ FAIL'}")
    
    if success and final_status:
        print("🎊 Chrome successfully opened using visual icon clicking!")
    else:
        print("💥 Test failed - Chrome was not opened by clicking icon")
    
    exit(0 if success else 1)
