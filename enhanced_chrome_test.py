#!/usr/bin/env python3
"""
Enhanced Chrome clicking test using OmniParser
"""

import os
import sys
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_omniparser_chrome_detection():
    """Enhanced test for Chrome detection with OmniParser"""
    
    logger.info("=== Enhanced Chrome Detection Test ===")
    
    try:
        # Import required modules
        logger.info("1. Importing modules...")
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.screenshot_utils import capture_screen_pil
        import pyautogui
        import subprocess
        import time
        
        # Initialize OmniParser
        logger.info("2. Setting up OmniParser...")
        omniparser_manager = OmniParserServerManager()
        
        if omniparser_manager.is_server_ready():
            logger.info("✓ OmniParser server is ready")
            omniparser = omniparser_manager.get_interface()
        else:
            logger.error("✗ OmniParser server is not ready")
            return False
            
        # Capture screenshot
        logger.info("3. Capturing screenshot...")
        screenshot = capture_screen_pil()
        if not screenshot:
            logger.error("✗ Failed to capture screenshot")
            return False
        logger.info(f"✓ Screenshot captured: {screenshot.size}")
        
        # Parse with OmniParser
        logger.info("4. Parsing screenshot with OmniParser...")
        parsed_result = omniparser.parse_screenshot(screenshot)
        
        if not parsed_result:
            logger.error("✗ OmniParser returned None")
            return False
            
        if "parsed_content_list" not in parsed_result:
            logger.error("✗ OmniParser result missing 'parsed_content_list'")
            logger.info(f"Available keys: {list(parsed_result.keys())}")
            return False
            
        elements = parsed_result.get("parsed_content_list", [])
        logger.info(f"✓ Found {len(elements)} UI elements")
        
        # Get screen dimensions
        screen_width, screen_height = pyautogui.size()
        logger.info(f"Screen size: {screen_width}x{screen_height}")
        
        # Search for Chrome and log ALL elements for debugging
        logger.info("5. Analyzing all detected elements...")
        chrome_elements = []
        
        for i, element in enumerate(elements):
            element_text = element.get("content", "").lower()
            element_type = element.get("type", "").lower()
            bbox = element.get("bbox_normalized", [])
            interactivity = element.get("interactivity", False)
            
            # Log every element for comprehensive debugging
            logger.info(f"   Element {i}: text='{element_text}', type='{element_type}', interactive={interactivity}")
            if bbox:
                logger.info(f"      bbox_normalized: {bbox}")
            
            # Check for Chrome indicators with broader criteria
            is_chrome_candidate = (
                "chrome" in element_text or
                "google chrome" in element_text or
                "google" in element_text or
                ("browser" in element_text) or
                (element_type == "icon" and interactivity) or
                (element_type == "button" and "chrome" in element_text)
            )
            
            if is_chrome_candidate:
                logger.info(f"   ➤ Chrome candidate: '{element_text}' (reason: matches criteria)")
                
                if bbox and not all(x == 0 for x in bbox):
                    chrome_elements.append((i, element))
                    logger.info(f"   ✓ Valid Chrome candidate with coordinates")
                else:
                    logger.info(f"   ⚠ Chrome candidate but no valid coordinates")
        
        if not chrome_elements:
            logger.warning("⚠ No valid Chrome elements found with coordinates")
            logger.info("Showing all interactive elements:")
            for i, element in enumerate(elements):
                if element.get("interactivity", False):
                    logger.info(f"   Interactive {i}: '{element.get('content', '')}' (type: {element.get('type', '')})")
            return False
            
        # Click the first valid Chrome element found
        logger.info(f"6. Found {len(chrome_elements)} Chrome candidates, clicking first one...")
        chrome_element = chrome_elements[0][1]
        bbox = chrome_element["bbox_normalized"]
        
        # Convert to pixel coordinates
        x1_pixel = int(bbox[0] * screen_width)
        y1_pixel = int(bbox[1] * screen_height)
        x2_pixel = int(bbox[2] * screen_width)
        y2_pixel = int(bbox[3] * screen_height)
        
        center_x = int((x1_pixel + x2_pixel) / 2)
        center_y = int((y1_pixel + y2_pixel) / 2)
        
        logger.info(f"   Element: '{chrome_element.get('content', '')}'")
        logger.info(f"   Bbox: {bbox}")
        logger.info(f"   Pixel coords: ({x1_pixel}, {y1_pixel}) to ({x2_pixel}, {y2_pixel})")
        logger.info(f"   Click target: ({center_x}, {center_y})")
        
        # Perform the click
        logger.info("   Executing click...")
        pyautogui.click(center_x, center_y)
        logger.info("✓ Click performed!")
        
        # Wait and check if Chrome launched
        logger.info("7. Checking if Chrome launched...")
        time.sleep(3)
        
        try:
            result = subprocess.run(['powershell', 'Get-Process', '-Name', 'chrome', '-ErrorAction', 'SilentlyContinue'], 
                                  capture_output=True, text=True)
            if result.stdout.strip():
                logger.info("✅ SUCCESS: Chrome process is running!")
                return True
            else:
                logger.warning("⚠ Chrome process not detected - checking for any browser processes...")
                
                # Check for any browser-related processes
                browser_processes = ['chrome', 'firefox', 'edge', 'brave', 'opera']
                for browser in browser_processes:
                    result = subprocess.run(['powershell', 'Get-Process', '-Name', browser, '-ErrorAction', 'SilentlyContinue'], 
                                          capture_output=True, text=True)
                    if result.stdout.strip():
                        logger.info(f"   Found {browser} process running")
                
                return False
                
        except Exception as check_error:
            logger.error(f"Error checking process: {check_error}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Test failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_omniparser_chrome_detection()
    print("\n" + "="*80)
    if success:
        print("✅ ENHANCED CHROME DETECTION TEST PASSED!")
    else:
        print("❌ ENHANCED CHROME DETECTION TEST FAILED!")
    print("="*80)
