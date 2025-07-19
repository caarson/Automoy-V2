#!/usr/bin/env python3
"""
Debug Chrome coordinate extraction - test the OmniParser coordinate detection directly
"""

import os
import sys
import json
import logging
from datetime import datetime

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_chrome_coordinate_extraction():
    """Test Chrome coordinate extraction with detailed debugging"""
    
    try:
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.operating_system.desktop_utils import DesktopUtils
        
        # Initialize components
        logger.info("Initializing OmniParser...")
        omniparser_manager = OmniParserServerManager()
        
        if not omniparser_manager.is_server_ready():
            logger.info("Starting OmniParser server...")
            server_process = omniparser_manager.start_server()
            if not omniparser_manager.wait_for_server(timeout=60):
                logger.error("OmniParser server failed to start")
                return False
        
        omniparser = omniparser_manager.get_interface()
        desktop_utils = DesktopUtils()
        
        # Take screenshot
        logger.info("Taking desktop screenshot...")
        screenshot_path = f"debug_chrome_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        desktop_utils.take_screenshot(screenshot_path)
        logger.info(f"Screenshot saved to: {screenshot_path}")
        
        # Get OmniParser results
        logger.info("Analyzing screenshot with OmniParser...")
        results = omniparser.process_screenshot(screenshot_path)
        
        if not results:
            logger.error("No results from OmniParser")
            return False
            
        logger.info(f"OmniParser returned {len(results)} total elements")
        
        # Debug: Save all results to file
        debug_file = f"debug_omniparser_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(debug_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"All OmniParser results saved to: {debug_file}")
        
        # Find Chrome candidates
        chrome_candidates = []
        chrome_keywords = ['chrome', 'google chrome', 'browser']
        
        for item in results:
            if isinstance(item, dict):
                text = item.get('text', '').lower() if item.get('text') else ''
                if any(keyword in text for keyword in chrome_keywords):
                    chrome_candidates.append(item)
                    logger.info(f"Found Chrome candidate: {item}")
        
        logger.info(f"Found {len(chrome_candidates)} Chrome candidates")
        
        if not chrome_candidates:
            logger.warning("No Chrome candidates found in OmniParser results")
            # Check for any text containing 'g' (for debugging)
            g_items = [item for item in results if isinstance(item, dict) and 'g' in item.get('text', '').lower()]
            logger.info(f"Items containing 'g': {len(g_items)}")
            for item in g_items[:5]:  # Show first 5
                logger.info(f"  - {item}")
            return False
        
        # Try to extract coordinates from candidates
        valid_coordinates = []
        for candidate in chrome_candidates:
            logger.info(f"Processing candidate: {candidate}")
            
            # Check for different coordinate formats
            if 'bbox_normalized' in candidate:
                bbox = candidate['bbox_normalized']
                logger.info(f"Found bbox_normalized: {bbox}")
                
                if isinstance(bbox, list) and len(bbox) >= 4:
                    try:
                        # Convert normalized coordinates to screen coordinates
                        screen_width = desktop_utils.get_screen_width()
                        screen_height = desktop_utils.get_screen_height()
                        
                        x1, y1, x2, y2 = bbox[:4]
                        center_x = int((x1 + x2) / 2 * screen_width)
                        center_y = int((y1 + y2) / 2 * screen_height)
                        
                        valid_coordinates.append((center_x, center_y))
                        logger.info(f"Extracted coordinates: ({center_x}, {center_y})")
                        
                    except Exception as e:
                        logger.error(f"Error converting coordinates: {e}")
            
            elif 'bbox' in candidate:
                bbox = candidate['bbox']
                logger.info(f"Found bbox: {bbox}")
                
                if isinstance(bbox, list) and len(bbox) >= 4:
                    try:
                        x1, y1, x2, y2 = bbox[:4]
                        center_x = int((x1 + x2) / 2)
                        center_y = int((y1 + y2) / 2)
                        
                        valid_coordinates.append((center_x, center_y))
                        logger.info(f"Extracted coordinates: ({center_x}, {center_y})")
                        
                    except Exception as e:
                        logger.error(f"Error converting coordinates: {e}")
            
            else:
                logger.warning(f"No recognized coordinate format in candidate: {list(candidate.keys())}")
        
        logger.info(f"Extracted {len(valid_coordinates)} valid coordinate pairs")
        
        if valid_coordinates:
            # Test clicking on the first valid coordinate
            x, y = valid_coordinates[0]
            logger.info(f"Testing click at coordinates: ({x}, {y})")
            
            # Simulate the click
            desktop_utils.click(x, y)
            logger.info("Click executed")
            
            # Wait and check if Chrome opened
            import time
            time.sleep(3)
            
            # Check for Chrome processes
            import subprocess
            try:
                result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                                      capture_output=True, text=True)
                if 'chrome.exe' in result.stdout:
                    logger.info("✅ SUCCESS: Chrome process detected after click!")
                    return True
                else:
                    logger.warning("❌ FAILED: No Chrome process detected after click")
                    return False
            except Exception as e:
                logger.error(f"Error checking Chrome processes: {e}")
                return False
        else:
            logger.error("No valid coordinates extracted from Chrome candidates")
            return False
            
    except Exception as e:
        logger.error(f"Error in Chrome coordinate extraction test: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    print("=== Chrome Coordinate Extraction Debug Test ===")
    success = test_chrome_coordinate_extraction()
    print(f"\nTest Result: {'SUCCESS' if success else 'FAILED'}")
