#!/usr/bin/env python3
"""
Simple OmniParser Server Test
Check if the OmniParser server is accessible after fresh install
"""

import logging
import sys
import os
import requests
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_omniparser_server():
    """Test if OmniParser server is accessible."""
    try:
        logger.info("=== OMNIPARSER SERVER TEST ===")
        
        # Test if server is running on port 8111
        logger.info("1. Testing OmniParser server connection...")
        
        try:
            response = requests.get("http://localhost:8111/probe/", timeout=10)
            if response.status_code == 200:
                logger.info("✅ OmniParser server is running and accessible!")
                logger.info(f"Response: {response.json()}")
                return True
            else:
                logger.error(f"❌ Server responded with status {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            logger.error("❌ Cannot connect to OmniParser server on port 8111")
            logger.info("Server might not be running or not accessible")
            return False
        except requests.exceptions.Timeout:
            logger.error("❌ Connection to OmniParser server timed out")
            return False
        except Exception as e:
            logger.error(f"❌ Error connecting to server: {e}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

def test_basic_screenshot():
    """Test basic screenshot functionality."""
    try:
        logger.info("2. Testing basic screenshot functionality...")
        
        # Add project to path
        project_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, project_dir)
        
        from core.utils.screenshot_utils import capture_screen_pil
        
        screenshot = capture_screen_pil("simple_test_screenshot.png")
        if screenshot:
            logger.info(f"✅ Screenshot captured successfully: {screenshot.size}")
            return True
        else:
            logger.error("❌ Screenshot capture failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Screenshot test failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("🔍 SIMPLE OMNIPARSER & SCREENSHOT TEST")
    logger.info("=" * 50)
    
    # Test 1: Server connectivity
    server_ok = test_omniparser_server()
    
    # Test 2: Screenshot functionality
    screenshot_ok = test_basic_screenshot()
    
    logger.info("=" * 50)
    logger.info("RESULTS:")
    logger.info(f"OmniParser Server: {'✅ Working' if server_ok else '❌ Not accessible'}")
    logger.info(f"Screenshot: {'✅ Working' if screenshot_ok else '❌ Failed'}")
    
    if server_ok and screenshot_ok:
        logger.info("✅ Both components working - ready for Chrome detection test!")
    else:
        logger.info("❌ Some components need troubleshooting before Chrome test")
    
    logger.info("=" * 50)
