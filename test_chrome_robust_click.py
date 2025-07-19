#!/usr/bin/env python3
"""
Robust Automoy Chrome Icon Clicking Test with timeout and fallback
"""

import os
import sys
import asyncio
import time
import psutil
import signal
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

async def test_automoy_robust_chrome_click():
    """Test Chrome clicking with robust error handling and timeouts"""
    print("🎯 ROBUST AUTOMOY CHROME CLICKING TEST")
    print("=" * 60)
    
    # Clean initial state
    initial_chrome = is_chrome_running()
    print(f"📋 Initial Chrome status: {'Running' if initial_chrome else 'Not running'}")
    
    if initial_chrome:
        print("⚠️ Cleaning Chrome processes...")
        kill_chrome()
        time.sleep(2)
    
    try:
        print("🔧 Initializing core components...")
        
        # Import with timeout protection
        timeout_seconds = 30
        
        async def import_with_timeout():
            from core.operate import ActionExecutor
            from core.utils.screenshot_utils import capture_screen_pil
            return ActionExecutor, capture_screen_pil
        
        try:
            ActionExecutor, capture_screen_pil = await asyncio.wait_for(
                import_with_timeout(), timeout=timeout_seconds
            )
            print("✅ Core imports successful")
        except asyncio.TimeoutError:
            print(f"❌ Import timeout after {timeout_seconds}s")
            return False
        except Exception as e:
            print(f"❌ Import error: {e}")
            return False
        
        # Initialize action executor
        print("🎯 Initializing action executor...")
        action_executor = ActionExecutor()
        print("✅ Action executor ready")
        
        # Try OmniParser with timeout
        omniparser = None
        print("🔍 Attempting OmniParser initialization (with timeout)...")
        
        async def init_omniparser():
            from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
            manager = OmniParserServerManager()
            
            if not manager.is_server_ready():
                print("   Starting OmniParser server...")
                server_process = manager.start_server()
                if server_process and manager.wait_for_server(timeout=20):
                    return manager.get_interface()
            else:
                return manager.get_interface()
            return None
        
        try:
            omniparser = await asyncio.wait_for(init_omniparser(), timeout=30)
            if omniparser:
                print("✅ OmniParser initialized successfully")
            else:
                print("⚠️ OmniParser failed to initialize")
        except asyncio.TimeoutError:
            print("⚠️ OmniParser initialization timeout - continuing with fallback")
            omniparser = None
        except Exception as e:
            print(f"⚠️ OmniParser error: {e} - continuing with fallback")
            omniparser = None
        
        # Take screenshot for analysis
        print("📸 Capturing desktop screenshot...")
        screenshot_pil = capture_screen_pil()
        if not screenshot_pil:
            print("❌ Failed to capture screenshot")
            return False
        
        screenshot_path = Path("debug/screenshots") / "robust_chrome_test.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot_pil.save(str(screenshot_path))
        print(f"✅ Screenshot saved: {screenshot_path}")
        
        # Try visual analysis if OmniParser is available
        click_coordinates = None
        
        if omniparser:
            print("🔍 Analyzing screenshot with OmniParser...")
            try:
                async def analyze_screenshot():
                    return omniparser.parse_screenshot(str(screenshot_path))
                
                parsed_result = await asyncio.wait_for(analyze_screenshot(), timeout=20)
                
                if parsed_result and "parsed_content_list" in parsed_result:
                    elements = parsed_result["parsed_content_list"]
                    print(f"📋 Found {len(elements)} UI elements")
                    
                    # Look for Chrome-related elements
                    for i, element in enumerate(elements):
                        element_text = element.get("content", "").lower()
                        
                        if any(term in element_text for term in ["chrome", "browser", "google"]):
                            print(f"🎯 Found Chrome element: {element_text}")
                            
                            if "bbox_normalized" in element:
                                bbox = element["bbox_normalized"]
                                x = int((bbox[0] + bbox[2]) / 2 * screenshot_pil.width)
                                y = int((bbox[1] + bbox[3]) / 2 * screenshot_pil.height)
                                click_coordinates = (x, y)
                                print(f"📍 Chrome icon coordinates: ({x}, {y})")
                                break
                    
                    if not click_coordinates:
                        print("🔍 No Chrome icon detected in visual analysis")
                        
            except asyncio.TimeoutError:
                print("⚠️ Visual analysis timeout")
            except Exception as e:
                print(f"⚠️ Visual analysis error: {e}")
        
        # Execute click action
        if click_coordinates:
            print(f"🖱️ Clicking Chrome icon at detected coordinates: {click_coordinates}")
            action = {
                "type": "click",
                "coordinate": {"x": click_coordinates[0], "y": click_coordinates[1]},
                "summary": f"Click Chrome icon at {click_coordinates}"
            }
            result = action_executor.execute(action)
            print(f"✅ Click result: {result}")
            
        else:
            print("🎯 Using fallback clicking strategy...")
            # Try common Chrome icon positions
            fallback_positions = [
                (100, 740),   # Left taskbar
                (150, 740),   # Second position  
                (200, 740),   # Third position
                (250, 740),   # Fourth position
                (60, 740),    # Far left
                (300, 740),   # Fifth position
            ]
            
            for i, (x, y) in enumerate(fallback_positions, 1):
                print(f"   🖱️ Trying fallback position {i}: ({x}, {y})")
                action = {
                    "type": "click",
                    "coordinate": {"x": x, "y": y}, 
                    "summary": f"Fallback click at ({x}, {y})"
                }
                result = action_executor.execute(action)
                print(f"      Result: {result}")
                
                # Check if Chrome started
                time.sleep(2)
                if is_chrome_running():
                    print(f"🎉 SUCCESS! Chrome opened from fallback position {i}")
                    return True
        
        # Wait for Chrome to start
        print("\n⏳ Waiting for Chrome to start...")
        
        # Monitor for up to 10 seconds
        for i in range(10):
            time.sleep(1)
            if is_chrome_running():
                print(f"🎉 SUCCESS! Chrome started after {i+1} seconds")
                return True
            print(f"   Checking... ({i+1}/10)")
        
        print("❌ Chrome did not start within timeout")
        return False
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Set signal handler for clean exit
    def signal_handler(signum, frame):
        print("\n🛑 Test interrupted")
        exit(1)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run test
    success = asyncio.run(test_automoy_robust_chrome_click())
    
    print("\n" + "=" * 60)
    
    # Final verification
    final_status = is_chrome_running()
    print(f"🔍 Final Chrome status: {'✅ RUNNING' if final_status else '❌ NOT RUNNING'}")
    print(f"🏁 TEST RESULT: {'✅ PASS' if success and final_status else '❌ FAIL'}")
    
    if success and final_status:
        print("🎊 Chrome successfully opened by clicking its icon!")
        # Keep Chrome running for verification
        print("📝 Chrome will remain open for verification")
    else:
        print("💥 Test failed - Chrome was not opened by icon clicking")
        print("🔧 This indicates an issue with icon detection or clicking")
    
    exit(0 if success else 1)
