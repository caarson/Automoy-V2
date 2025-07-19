#!/usr/bin/env python3
"""
Diagnostic script to check OmniParser functionality and Chrome detection
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_omniparser_chrome_detection():
    """Test OmniParser setup and Chrome detection"""
    
    logger.info("=== OmniParser Chrome Detection Diagnostic ===")
    
    try:
        # Test OmniParser import and initialization
        logger.info("1. Testing OmniParser import...")
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        logger.info("✓ OmniParser manager import successful")
        
        # Initialize OmniParser manager
        logger.info("2. Initializing OmniParser manager...")
        omniparser_manager = OmniParserServerManager()
        
        # Check if server is ready or start it
        if omniparser_manager.is_server_ready():
            logger.info("✓ OmniParser server is already running")
            omniparser = omniparser_manager.get_interface()
        else:
            logger.info("Starting OmniParser server...")
            server_process = omniparser_manager.start_server()
            if server_process:
                if omniparser_manager.wait_for_server(timeout=60):
                    logger.info("✓ OmniParser server started successfully")
                    omniparser = omniparser_manager.get_interface()
                else:
                    logger.error("✗ OmniParser server failed to become ready within timeout")
                    return False
            else:
                logger.error("✗ Failed to start OmniParser server")
                return False
        
        # Test screenshot capture
        logger.info("3. Testing screenshot capture...")
        from core.utils.screenshot_utils import capture_screen_pil
        screenshot = capture_screen_pil()
        if screenshot:
            logger.info(f"✓ Screenshot captured: {screenshot.size}")
        else:
            logger.error("✗ Failed to capture screenshot")
            return False
            
        # Test OmniParser parsing
        logger.info("4. Testing OmniParser screenshot analysis...")
        parsed_result = omniparser.parse_screenshot(screenshot)
        
        if parsed_result:
            elements = parsed_result.get("parsed_content_list", [])
            logger.info(f"✓ OmniParser analysis successful: {len(elements)} elements detected")
            
            # Look for Chrome-related elements
            logger.info("5. Searching for Chrome-related elements...")
            chrome_elements = []
            
            for i, element in enumerate(elements):
                element_text = element.get("content", "").lower()
                element_type = element.get("type", "").lower()
                
                # Check for Chrome indicators
                is_chrome_candidate = (
                    "chrome" in element_text or
                    "google chrome" in element_text or
                    ("browser" in element_text and element_type == "icon") or
                    (element_type == "icon" and element.get("interactivity"))
                )
                
                if is_chrome_candidate:
                    chrome_elements.append((i, element))
                    logger.info(f"   Chrome candidate {i}: '{element_text}' (type: {element_type})")
                    
                    # Show coordinates if available
                    bbox = element.get("bbox_normalized")
                    if bbox:
                        logger.info(f"      Coordinates: {bbox}")
            
            if chrome_elements:
                logger.info(f"✓ Found {len(chrome_elements)} Chrome candidate(s)")
                
                # Test coordinate conversion for first Chrome element
                if chrome_elements[0][1].get("bbox_normalized"):
                    logger.info("6. Testing coordinate conversion...")
                    try:
                        import pyautogui
                        screen_width, screen_height = pyautogui.size()
                        logger.info(f"   Screen size: {screen_width}x{screen_height}")
                        
                        bbox = chrome_elements[0][1]["bbox_normalized"]
                        x1_pixel = int(bbox[0] * screen_width)
                        y1_pixel = int(bbox[1] * screen_height)
                        x2_pixel = int(bbox[2] * screen_width)
                        y2_pixel = int(bbox[3] * screen_height)
                        
                        center_x = int((x1_pixel + x2_pixel) / 2)
                        center_y = int((y1_pixel + y2_pixel) / 2)
                        
                        logger.info(f"   Converted coordinates: ({center_x}, {center_y})")
                        logger.info("✓ Coordinate conversion successful")
                        
                        return True
                        
                    except Exception as coord_error:
                        logger.error(f"✗ Coordinate conversion failed: {coord_error}")
                        return False
            else:
                logger.warning("⚠ No Chrome elements detected in current screen")
                
                # Show all detected elements for debugging
                logger.info("   All detected elements:")
                for i, element in enumerate(elements[:10]):  # Show first 10
                    logger.info(f"   {i}: '{element.get('content', '')}' (type: {element.get('type', '')})")
                
                return False
                
        else:
            logger.error("✗ OmniParser returned no results")
            return False
            
    except Exception as e:
        logger.error(f"✗ Diagnostic failed: {e}", exc_info=True)
        return False

def main():
    """Run the diagnostic"""
    result = asyncio.run(test_omniparser_chrome_detection())
    
    print("\n" + "="*60)
    if result:
        print("✅ DIAGNOSTIC PASSED: OmniParser Chrome detection is working!")
    else:
        print("❌ DIAGNOSTIC FAILED: Issues detected with OmniParser Chrome detection")
    print("="*60)

if __name__ == "__main__":
    main()
