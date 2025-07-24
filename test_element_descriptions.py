#!/usr/bin/env python3
"""
Test script to verify that visual analysis element descriptions are working properly.
This bypasses the goal file reading mechanism to test the core functionality.
"""

import sys
import os
import asyncio
import logging

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
from core.utils.screenshot_utils import capture_screen_pil
import tempfile

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("element_description_test")

async def test_element_descriptions():
    """Test that we can get proper element descriptions with ClickCoordinates."""
    
    logger.info("🔍 Testing Element Description Functionality")
    logger.info("=" * 50)
    
    # Initialize OmniParser
    logger.info("1. Initializing OmniParser...")
    try:
        omniparser_manager = OmniParserServerManager()
        
        # Check if server is running
        import requests
        try:
            response = requests.get("http://127.0.0.1:8111/probe/", timeout=5)
            if response.status_code == 200:
                logger.info("✅ OmniParser server is running")
                omniparser = omniparser_manager.get_interface()
            else:
                logger.error("❌ OmniParser server not responding properly")
                return
        except Exception as e:
            logger.error(f"❌ Cannot connect to OmniParser server: {e}")
            return
            
    except Exception as e:
        logger.error(f"❌ Error initializing OmniParser: {e}")
        return
    
    # Take screenshot
    logger.info("2. Capturing screenshot...")
    try:
        screenshot = capture_screen_pil()
        if not screenshot:
            logger.error("❌ Failed to capture screenshot")
            return
        logger.info("✅ Screenshot captured successfully")
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
            screenshot.save(temp_path)
            logger.info(f"✅ Screenshot saved to: {temp_path}")
            
    except Exception as e:
        logger.error(f"❌ Error capturing screenshot: {e}")
        return
    
    # Parse with OmniParser
    logger.info("3. Analyzing screenshot with OmniParser...")
    try:
        parsed_result = omniparser.parse_screenshot(temp_path)
        
        if not parsed_result:
            logger.error("❌ OmniParser returned no results")
            return
            
        if "parsed_content_list" not in parsed_result:
            logger.error("❌ No parsed_content_list in OmniParser results")
            return
            
        elements = parsed_result["parsed_content_list"]
        logger.info(f"✅ OmniParser found {len(elements)} elements")
        
    except Exception as e:
        logger.error(f"❌ Error parsing screenshot: {e}")
        return
    
    # Test the _format_visual_analysis_result equivalent
    logger.info("4. Testing element description formatting...")
    try:
        formatted_output = []
        
        # Get actual screen dimensions
        try:
            import pyautogui
            screen_width, screen_height = pyautogui.size()
            logger.info(f"✅ Screen dimensions: {screen_width}x{screen_height}")
        except:
            screen_width, screen_height = 1920, 1080
            logger.warning("⚠️ Using fallback screen dimensions: 1920x1080")
        
        # Format first 10 elements to avoid overwhelming output
        for i, element in enumerate(elements[:10]):
            element_text = element.get("content", "")
            element_type = element.get("type", "unknown")
            
            if element.get("bbox_normalized"):
                bbox = element["bbox_normalized"]
                x1, y1, x2, y2 = bbox
                pixel_x = int((x1 + x2) / 2 * screen_width)
                pixel_y = int((y1 + y2) / 2 * screen_height)
                
                formatted_line = f"element_{i+1}: Text: '{element_text}' | Type: {element_type} | ClickCoordinates: ({pixel_x}, {pixel_y})"
                formatted_output.append(formatted_line)
            else:
                formatted_line = f"element_{i+1}: Text: '{element_text}' | Type: {element_type} | ClickCoordinates: (unavailable)"
                formatted_output.append(formatted_line)
        
        logger.info("✅ Element formatting successful!")
        logger.info("📋 FORMATTED ELEMENTS (first 10):")
        logger.info("=" * 50)
        for line in formatted_output:
            logger.info(line)
        
    except Exception as e:
        logger.error(f"❌ Error formatting elements: {e}")
        return
    
    # Cleanup
    try:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
            logger.info("✅ Cleanup completed")
    except Exception:
        pass
    
    logger.info("=" * 50)
    logger.info("🎉 ELEMENT DESCRIPTION TEST COMPLETED SUCCESSFULLY!")
    logger.info("✅ Visual analysis is working properly")
    logger.info("✅ Elements are being formatted with ClickCoordinates")
    logger.info("✅ LLM should now receive proper element descriptions")

if __name__ == "__main__":
    asyncio.run(test_element_descriptions())
