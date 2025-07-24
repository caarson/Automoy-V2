#!/usr/bin/env python3
"""
Basic screenshot test - just capture desktop
"""

import logging
import sys
import os

# Add the project directory to sys.path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def basic_screenshot_test():
    """Just take a screenshot to test basic functionality."""
    try:
        logger.info("Starting basic screenshot test...")
        
        from core.utils.screenshot_utils import capture_screen_pil
        
        logger.info("Taking screenshot...")
        screenshot = capture_screen_pil("basic_test_screenshot.png")
        
        if screenshot:
            logger.info(f"✓ Screenshot successful! Size: {screenshot.size}")
            logger.info(f"Screenshot saved as: basic_test_screenshot.png")
            return True
        else:
            logger.error("✗ Screenshot failed")
            return False
            
    except Exception as e:
        logger.error(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("Basic Screenshot Test")
    success = basic_screenshot_test()
    if success:
        logger.info("✅ Success!")
    else:
        logger.info("❌ Failed!")
