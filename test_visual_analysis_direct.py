#!/usr/bin/env python3
"""
Direct test of visual analysis pipeline to debug why "No visual elements detected"
"""
import sys
import os
import logging
import json

# Add the project root to Python path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    # Import OmniParser interface directly
    from core.utils.omniparser.omniparser_interface import OmniParserInterface
    
    # Test the visual analysis pipeline
    logger.info("🔬 Starting direct visual analysis test...")
    
    # Take a screenshot first
    import pyautogui
    screenshot_path = os.path.join(PROJECT_ROOT, "debug_screenshot_test.png")
    logger.info(f"📸 Taking screenshot and saving to: {screenshot_path}")
    pyautogui.screenshot(screenshot_path)
    logger.info("✅ Screenshot captured")
    
    # Initialize OmniParser
    logger.info("🔌 Initializing OmniParser interface...")
    omniparser = OmniParserInterface()
    logger.info("✅ OmniParser interface initialized")
    
    # Call parse_screenshot directly
    logger.info(f"🔍 Calling parse_screenshot on: {screenshot_path}")
    result = omniparser.parse_screenshot(screenshot_path)
    
    logger.info(f"📊 Raw result type: {type(result)}")
    if result:
        logger.info(f"📊 Raw result keys: {list(result.keys())}")
        
        if "parsed_content_list" in result:
            elements = result["parsed_content_list"]
            logger.info(f"🔢 Found {len(elements)} elements in parsed_content_list")
            
            # Show first few elements
            for i, element in enumerate(elements[:3]):
                logger.info(f"📦 Element {i}: {json.dumps(element, indent=2)}")
        else:
            logger.warning("⚠️ No 'parsed_content_list' key found in result")
            logger.warning(f"Available keys: {list(result.keys())}")
    else:
        logger.error("❌ parse_screenshot returned None or empty result")

except Exception as e:
    logger.error(f"💥 Error during visual analysis test: {e}")
    import traceback
    logger.error(traceback.format_exc())
