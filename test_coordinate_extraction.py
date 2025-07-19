#!/usr/bin/env python3
"""
Direct test of Automoy's visual analysis and coordinate clicking
"""
import asyncio
import sys
import os
import time
from pathlib import Path

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

async def test_visual_analysis_coordinates():
    """Test visual analysis coordinate extraction and clicking"""
    print("=== VISUAL ANALYSIS COORDINATE TEST ===")
    
    # Import required modules
    from core.operate import AutomoyOperator
    from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
    
    try:
        # Initialize OmniParser
        print("1. Initializing OmniParser...")
        omniparser_manager = OmniParserServerManager()
        
        if omniparser_manager.is_server_ready():
            print("   ✓ OmniParser server is already running")
            omniparser = omniparser_manager.get_interface()
        else:
            print("   Starting OmniParser server...")
            server_process = omniparser_manager.start_server()
            if server_process and omniparser_manager.wait_for_server(timeout=60):
                print("   ✓ OmniParser server started successfully")
                omniparser = omniparser_manager.get_interface()
            else:
                print("   ❌ Failed to start OmniParser server")
                return False
        
        # Create a minimal operator instance for testing
        print("2. Creating minimal operator for visual analysis...")
        
        pause_event = asyncio.Event()
        pause_event.set()
        
        async def dummy_gui_update(endpoint, payload):
            print(f"   GUI Update: {endpoint} -> {payload}")
        
        async def dummy_gui_window(action):
            return True
        
        operator = AutomoyOperator(
            objective="Test Chrome clicking",
            manage_gui_window_func=dummy_gui_window,
            omniparser=omniparser,
            pause_event=pause_event,
            update_gui_state_func=dummy_gui_update
        )
        
        # Take screenshot and perform visual analysis
        print("3. Capturing screenshot and performing visual analysis...")
        screenshot_path = await operator._capture_screenshot()
        
        if screenshot_path:
            print(f"   ✓ Screenshot captured: {screenshot_path}")
            
            # Perform visual analysis
            processed_screenshot_path, visual_analysis_result = await operator._perform_visual_analysis(
                screenshot_path, "Looking for Chrome icon"
            )
            
            if visual_analysis_result:
                print("   ✓ Visual analysis completed!")
                print("\n--- VISUAL ANALYSIS RESULT ---")
                print(visual_analysis_result)
                print("--- END VISUAL ANALYSIS ---\n")
                
                # Look for Chrome-related elements
                print("4. Searching for Chrome-related elements...")
                chrome_elements = []
                lines = visual_analysis_result.split('\n')
                
                for line in lines:
                    if 'chrome' in line.lower() or 'google' in line.lower():
                        chrome_elements.append(line)
                        print(f"   Found Chrome element: {line}")
                
                if chrome_elements:
                    print(f"   ✓ Found {len(chrome_elements)} Chrome-related elements")
                    
                    # Extract coordinates from first Chrome element
                    for element_line in chrome_elements:
                        if 'ClickCoordinates:' in element_line:
                            coords_part = element_line.split('ClickCoordinates:')[1].strip()
                            if coords_part.startswith('(') and ')' in coords_part:
                                coords_str = coords_part.split(')')[0] + ')'
                                print(f"   🎯 Chrome click coordinates found: {coords_str}")
                                
                                # Test the clicking
                                print("5. Testing coordinate clicking...")
                                
                                # Parse coordinates
                                coords_clean = coords_str.strip('()')
                                x, y = map(int, coords_clean.split(', '))
                                
                                print(f"   Parsed coordinates: x={x}, y={y}")
                                
                                # Create click action and execute
                                click_action = {
                                    "type": "click",
                                    "coordinate": {"x": x, "y": y},
                                    "summary": f"Test click on Chrome at ({x}, {y})"
                                }
                                
                                from core.operate import ActionExecutor
                                executor = ActionExecutor()
                                result = executor.execute(click_action)
                                
                                print(f"   Click result: {result}")
                                
                                # Wait and check if Chrome started
                                print("6. Waiting 3 seconds and checking if Chrome started...")
                                await asyncio.sleep(3)
                                
                                import psutil
                                chrome_running = False
                                for proc in psutil.process_iter(['name']):
                                    if 'chrome' in proc.info['name'].lower():
                                        chrome_running = True
                                        break
                                
                                if chrome_running:
                                    print("   🎉 SUCCESS: Chrome is now running!")
                                    return True
                                else:
                                    print("   ⚠️  Chrome not detected running - coordinates may need adjustment")
                                    return False
                                
                                break
                    else:
                        print("   ❌ No clickable coordinates found for Chrome elements")
                        return False
                else:
                    print("   ❌ No Chrome-related elements found in visual analysis")
                    print("   Available elements:")
                    element_lines = [line for line in lines if line.strip() and 'element_' in line]
                    for line in element_lines[:10]:  # Show first 10 elements
                        print(f"     {line}")
                    return False
            else:
                print("   ❌ Visual analysis failed")
                return False
        else:
            print("   ❌ Screenshot capture failed")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    success = await test_visual_analysis_coordinates()
    if success:
        print("\n🎉 COORDINATE TEST PASSED!")
    else:
        print("\n❌ COORDINATE TEST FAILED!")

if __name__ == "__main__":
    asyncio.run(main())
