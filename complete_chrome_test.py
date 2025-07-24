#!/usr/bin/env python3
"""
Complete Chrome clicking test that works with the current Automoy system.
This test will show exactly what happens when we try to detect and click Chrome.
"""

import logging
import sys
import os
import requests
import json
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

def test_automoy_chrome_request():
    """Test Chrome opening through the Automoy API."""
    try:
        logger.info("=== Automoy Chrome Request Test ===")
        
        # Make sure we have a clean desktop first
        logger.info("1. Testing Automoy API connection...")
        automoy_api_url = "http://127.0.0.1:8001"
        
        try:
            response = requests.get(f"{automoy_api_url}/", timeout=5)
            logger.info(f"✓ Automoy API is accessible: {response.status_code}")
        except Exception as e:
            logger.error(f"✗ Cannot connect to Automoy API: {e}")
            return False
        
        # Create a goal request to open Chrome
        logger.info("2. Creating Chrome opening goal...")
        goal_request = {
            "goal": "Click on the Google Chrome icon on the desktop to open Chrome browser",
            "clarifying_question": "",
            "details": "I want you to use actual mouse clicking to click on the Chrome icon on the desktop, not keyboard shortcuts"
        }
        
        logger.info(f"Goal request: {goal_request['goal']}")
        
        # Send the goal request
        logger.info("3. Sending goal request to Automoy...")
        try:
            response = requests.post(
                f"{automoy_api_url}/api/goal",
                json=goal_request,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info("✓ Goal request accepted")
                response_data = response.json()
                logger.info(f"Response: {response_data}")
            else:
                logger.error(f"✗ Goal request failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Error sending goal request: {e}")
            return False
        
        # Monitor the goal execution
        logger.info("4. Monitoring goal execution...")
        
        # Wait for execution to start
        time.sleep(3)
        
        # Check status
        try:
            response = requests.get(f"{automoy_api_url}/api/status", timeout=10)
            if response.status_code == 200:
                status = response.json()
                logger.info(f"Current status: {status}")
                
                if "steps" in status:
                    logger.info("=== EXECUTION STEPS ===")
                    for i, step in enumerate(status["steps"], 1):
                        logger.info(f"Step {i}: {step}")
                        
        except Exception as e:
            logger.error(f"Error checking status: {e}")
        
        logger.info("5. Test completed - check the Automoy GUI for visual results")
        return True
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_manual_screenshot_analysis():
    """Take a screenshot and analyze what's visible on desktop."""
    try:
        logger.info("=== Manual Desktop Analysis ===")
        
        from core.utils.screenshot_utils import capture_screen_pil
        
        logger.info("1. Taking desktop screenshot...")
        screenshot = capture_screen_pil("manual_chrome_analysis.png")
        
        if screenshot:
            logger.info("✓ Screenshot captured successfully")
            logger.info(f"Screenshot saved as: manual_chrome_analysis.png")
            logger.info(f"Screenshot size: {screenshot.size}")
            
            # Show basic info about what we captured
            logger.info("2. Screenshot analysis:")
            logger.info(f"   - Width: {screenshot.size[0]} pixels")
            logger.info(f"   - Height: {screenshot.size[1]} pixels")
            logger.info("   - File saved for manual inspection")
            
            return True
        else:
            logger.error("✗ Failed to capture screenshot")
            return False
            
    except Exception as e:
        logger.error(f"✗ Screenshot analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("🔍 COMPLETE CHROME CLICKING TEST")
    logger.info("=" * 80)
    
    # Test 1: Screenshot analysis
    logger.info("\n" + "=" * 40)
    logger.info("TEST 1: MANUAL SCREENSHOT ANALYSIS")
    logger.info("=" * 40)
    screenshot_success = test_manual_screenshot_analysis()
    
    # Test 2: Automoy API request
    logger.info("\n" + "=" * 40)
    logger.info("TEST 2: AUTOMOY CHROME REQUEST")
    logger.info("=" * 40)
    api_success = test_automoy_chrome_request()
    
    # Summary
    logger.info("\n" + "=" * 80)
    if screenshot_success and api_success:
        logger.info("✅ COMPLETE CHROME CLICKING TEST SUCCEEDED!")
        logger.info("Check the Automoy GUI and manual_chrome_analysis.png for results")
    else:
        logger.info("❌ SOME TESTS FAILED!")
        logger.info(f"Screenshot test: {'✅' if screenshot_success else '❌'}")
        logger.info(f"API test: {'✅' if api_success else '❌'}")
    logger.info("=" * 80)
