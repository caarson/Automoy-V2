#!/usr/bin/env python3
"""
Test Chrome detection with proper OmniParser interface
"""

import os
import sys
import tempfile
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_chrome_detection_fixed():
    """Test Chrome detection with file path fix"""
    
    print("=== Chrome Detection Test (Fixed Version) ===")
    
    try:
        # Import required modules
        print("1. Setting up OmniParser...")
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.screenshot_utils import capture_screen_pil
        import pyautogui
        
        # Initialize OmniParser
        omniparser_manager = OmniParserServerManager()
        
        if omniparser_manager.is_server_ready():
            print("✓ OmniParser server is ready")
            omniparser = omniparser_manager.get_interface()
        else:
            print("Starting OmniParser server...")
            server_process = omniparser_manager.start_server()
            if server_process and omniparser_manager.wait_for_server(timeout=60):
                print("✓ OmniParser server started")
                omniparser = omniparser_manager.get_interface()
            else:
                print("✗ Failed to start OmniParser server")
                return False
        
        # Capture screenshot
        print("2. Capturing screenshot...")
        screenshot = capture_screen_pil()
        if not screenshot:
            print("✗ Failed to capture screenshot")
            return False
        print(f"✓ Screenshot captured: {screenshot.size}")
        
        # Save to temporary file (OmniParser expects file path)
        print("3. Saving screenshot for OmniParser...")
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
            screenshot.save(temp_path)
            print(f"✓ Screenshot saved to: {temp_path}")
        
        try:
            # Parse with OmniParser
            print("4. Parsing with OmniParser...")
            parsed_result = omniparser.parse_screenshot(temp_path)
            
            if parsed_result and "parsed_content_list" in parsed_result:
                elements = parsed_result.get("parsed_content_list", [])
                print(f"✓ OmniParser found {len(elements)} UI elements")
                
                # Search for Chrome
                print("5. Searching for Chrome icons...")
                screen_width, screen_height = pyautogui.size()
                chrome_found = []
                
                for i, element in enumerate(elements):
                    element_text = element.get("content", "").lower()
                    element_type = element.get("type", "").lower()
                    bbox = element.get("bbox_normalized", [])
                    interactive = element.get("interactivity", False)
                    
                    # Chrome detection
                    is_chrome_candidate = (
                        "chrome" in element_text or
                        "google chrome" in element_text or
                        "google" in element_text or
                        ("browser" in element_text) or
                        (element_type == "icon" and interactive)
                    )
                    
                    if is_chrome_candidate:
                        print(f"   ★ Chrome candidate: '{element_text}' (type: {element_type}, interactive: {interactive})")
                        
                        if bbox and not all(x == 0 for x in bbox):
                            x1 = int(bbox[0] * screen_width)
                            y1 = int(bbox[1] * screen_height)
                            x2 = int(bbox[2] * screen_width)
                            y2 = int(bbox[3] * screen_height)
                            center_x = int((x1 + x2) / 2)
                            center_y = int((y1 + y2) / 2)
                            
                            chrome_found.append({
                                'text': element_text,
                                'coords': (center_x, center_y),
                                'bbox': bbox
                            })
                            print(f"     ✓ Valid coordinates: ({center_x}, {center_y})")
                        else:
                            print(f"     ⚠ No valid coordinates")
                
                if chrome_found:
                    print(f"\n✅ SUCCESS: Found {len(chrome_found)} Chrome icons with valid coordinates!")
                    for i, chrome in enumerate(chrome_found):
                        print(f"   Option {i+1}: '{chrome['text']}' at {chrome['coords']}")
                    
                    # Test clicking the first one
                    if len(chrome_found) > 0:
                        coords = chrome_found[0]['coords']
                        print(f"\n6. Testing click at {coords}...")
                        
                        # Perform click
                        pyautogui.click(coords[0], coords[1])
                        print("✓ Click performed!")
                        
                        # Wait and check if Chrome launched
                        import time
                        import subprocess
                        time.sleep(3)
                        
                        result = subprocess.run(['powershell', 'Get-Process', '-Name', 'chrome', '-ErrorAction', 'SilentlyContinue'], 
                                              capture_output=True, text=True)
                        if result.stdout.strip():
                            print("🎉 CHROME LAUNCHED SUCCESSFULLY!")
                            return True
                        else:
                            print("⚠ Chrome process not detected")
                            return False
                    
                else:
                    print("❌ No Chrome icons found with valid coordinates")
                    return False
                    
            else:
                print("✗ OmniParser returned no elements")
                return False
                
        finally:
            # Cleanup
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_chrome_detection_fixed()
    print("\n" + "="*70)
    if success:
        print("✅ CHROME DETECTION TEST PASSED - Chrome was launched!")
    else:
        print("❌ CHROME DETECTION TEST FAILED")
    print("="*70)
