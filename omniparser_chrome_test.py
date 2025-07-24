#!/usr/bin/env python3
"""
OmniParser Chrome Detection Test - After Fresh Reinstall
This will:
1. Go to desktop (minimize windows)
2. Take a screenshot
3. Process with OmniParser
4. Look for Google Chrome
5. Report coordinates if found
"""

import logging
import sys
import os
import time

# Add the project directory to sys.path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_omniparser_chrome_detection():
    """Complete test for Chrome detection using fresh OmniParser install."""
    try:
        logger.info("=== OMNIPARSER CHROME DETECTION TEST ===")
        
        # Step 1: Go to desktop
        logger.info("1. Going to desktop...")
        import pyautogui
        pyautogui.FAILSAFE = False
        
        # Use Win+D to show desktop
        pyautogui.hotkey('win', 'd')
        time.sleep(3)  # Wait for desktop to be fully shown
        logger.info("✓ Desktop shown")
        
        # Step 2: Take screenshot
        logger.info("2. Taking desktop screenshot...")
        from core.utils.screenshot_utils import capture_screen_pil
        
        screenshot_filename = "chrome_detection_test.png"
        screenshot = capture_screen_pil(screenshot_filename)
        
        if not screenshot:
            logger.error("✗ Failed to capture screenshot")
            return False
            
        logger.info(f"✓ Screenshot captured: {screenshot.size} - saved as {screenshot_filename}")
        
        # Step 3: Initialize OmniParser
        logger.info("3. Initializing OmniParser...")
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        
        omniparser_manager = OmniParserServerManager()
        
        # Check if server is running
        if omniparser_manager.is_server_ready():
            logger.info("✓ OmniParser server is already running")
            omniparser = omniparser_manager.get_interface()
        else:
            logger.info("Starting OmniParser server...")
            # Use explicit conda path
            interface = omniparser_manager.get_interface()
            conda_path = "C:/Users/imitr/anaconda3/Scripts/conda.exe"
            
            if interface.launch_server(conda_path=conda_path, conda_env="automoy_env"):
                logger.info("✓ OmniParser server started")
                omniparser_manager.server_process = interface.server_process
                
                if omniparser_manager.wait_for_server(timeout=60):
                    logger.info("✓ OmniParser server is ready")
                    omniparser = interface
                else:
                    logger.error("✗ OmniParser server failed to become ready")
                    return False
            else:
                logger.error("✗ Failed to start OmniParser server")
                return False
        
        # Step 4: Process screenshot with OmniParser
        logger.info("4. Processing screenshot with OmniParser...")
        parsed_result = omniparser.parse_screenshot(screenshot)
        
        if not parsed_result:
            logger.error("✗ OmniParser returned no results")
            return False
        
        logger.info("✓ OmniParser processing completed")
        
        # Step 5: Analyze results structure
        logger.info("5. Analyzing OmniParser results...")
        logger.info(f"Result type: {type(parsed_result)}")
        
        if isinstance(parsed_result, dict):
            logger.info(f"Result keys: {list(parsed_result.keys())}")
            
            # Look for parsed content
            if "parsed_content_list" in parsed_result:
                elements = parsed_result["parsed_content_list"]
                logger.info(f"✓ Found {len(elements)} UI elements")
                
                # Step 6: Search for Chrome specifically
                logger.info("6. Searching for Google Chrome...")
                chrome_candidates = []
                
                for i, element in enumerate(elements):
                    text = element.get("text", "").strip()
                    elem_type = element.get("type", "unknown")
                    interactable = element.get("interactable", False)
                    
                    # Check for Chrome-related terms
                    chrome_terms = ["chrome", "google", "browser"]
                    text_lower = text.lower()
                    type_lower = elem_type.lower()
                    
                    is_chrome = any(term in text_lower for term in chrome_terms) or \
                               any(term in type_lower for term in chrome_terms)
                    
                    if is_chrome:
                        chrome_candidates.append((i, element))
                        logger.info(f"*** CHROME CANDIDATE #{len(chrome_candidates)} ***")
                        logger.info(f"  Element Index: {i}")
                        logger.info(f"  Text: '{text}'")
                        logger.info(f"  Type: {elem_type}")
                        logger.info(f"  Interactable: {interactable}")
                        
                        # Look for coordinates/bounding box
                        coordinates = None
                        for coord_key in ["box", "bbox", "coordinates", "position"]:
                            if coord_key in element:
                                coordinates = element[coord_key]
                                logger.info(f"  Coordinates ({coord_key}): {coordinates}")
                                break
                        
                        if coordinates and isinstance(coordinates, (list, tuple)) and len(coordinates) >= 4:
                            x1, y1, x2, y2 = coordinates[:4]
                            center_x = int((x1 + x2) / 2)
                            center_y = int((y1 + y2) / 2)
                            logger.info(f"  🎯 CLICK COORDINATES: ({center_x}, {center_y})")
                            logger.info(f"  Bounding box: x1={x1}, y1={y1}, x2={x2}, y2={y2}")
                        
                        logger.info(f"  Full element data: {element}")
                        logger.info("")
                
                # Step 7: Report findings
                if chrome_candidates:
                    logger.info(f"🎉 SUCCESS: Found {len(chrome_candidates)} Chrome candidate(s)!")
                    
                    # Show summary of all candidates with coordinates
                    logger.info("=== CHROME DETECTION SUMMARY ===")
                    for idx, (element_idx, element) in enumerate(chrome_candidates, 1):
                        text = element.get("text", "").strip()
                        logger.info(f"Chrome Candidate #{idx}:")
                        logger.info(f"  Text: '{text}'")
                        
                        coordinates = None
                        for coord_key in ["box", "bbox", "coordinates", "position"]:
                            if coord_key in element:
                                coordinates = element[coord_key]
                                break
                        
                        if coordinates and isinstance(coordinates, (list, tuple)) and len(coordinates) >= 4:
                            x1, y1, x2, y2 = coordinates[:4]
                            center_x = int((x1 + x2) / 2)
                            center_y = int((y1 + y2) / 2)
                            logger.info(f"  ✅ CLICKABLE AT: ({center_x}, {center_y})")
                        else:
                            logger.info(f"  ❌ No valid coordinates found")
                        logger.info("")
                    
                    return True
                else:
                    logger.warning("❌ No Chrome candidates found")
                    
                    # Show sample of other detected elements for debugging
                    logger.info("=== SAMPLE OF OTHER DETECTED ELEMENTS ===")
                    for i, element in enumerate(elements[:10]):  # Show first 10
                        text = element.get("text", "").strip()
                        elem_type = element.get("type", "unknown")
                        if text:
                            logger.info(f"  {i+1}. '{text}' (type: {elem_type})")
                    
                    if len(elements) > 10:
                        logger.info(f"  ... and {len(elements) - 10} more elements")
                    
                    return False
            else:
                logger.error("✗ No 'parsed_content_list' found in OmniParser results")
                logger.info(f"Available keys: {list(parsed_result.keys())}")
                return False
        else:
            logger.error(f"✗ Unexpected result type: {type(parsed_result)}")
            return False
        
    except Exception as e:
        logger.error(f"✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("🔍 OMNIPARSER CHROME DETECTION TEST (FRESH INSTALL)")
    logger.info("=" * 80)
    
    success = test_omniparser_chrome_detection()
    
    logger.info("=" * 80)
    if success:
        logger.info("✅ CHROME DETECTION TEST PASSED!")
        logger.info("Chrome icon was detected with coordinates!")
    else:
        logger.info("❌ CHROME DETECTION TEST FAILED!")
        logger.info("Chrome icon was not found or coordinates unavailable.")
    logger.info("=" * 80)
