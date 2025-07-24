#!/usr/bin/env python3
"""
Simple Chrome Detection Test - Just screenshot and OmniParser analysis
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

def test_omniparser_detection():
    """Simple test for OmniParser desktop analysis."""
    try:
        logger.info("=== Simple Chrome Detection Test ===")
        
        # Step 1: Show desktop first
        logger.info("1. Showing desktop...")
        import pyautogui
        pyautogui.FAILSAFE = False
        
        # Use Win+D to show desktop
        pyautogui.hotkey('win', 'd')
        time.sleep(3)  # Wait for desktop to be shown
        logger.info("✓ Desktop shown")
        
        # Step 2: Take screenshot
        logger.info("2. Taking screenshot...")
        from core.utils.screenshot_utils import capture_screen_pil
        
        screenshot = capture_screen_pil("simple_desktop_screenshot.png")
        if not screenshot:
            logger.error("✗ Failed to take screenshot")
            return False
            
        logger.info(f"✓ Screenshot captured: {screenshot.size}")
        
        # Step 3: Try OmniParser (check if server is running first)
        logger.info("3. Checking OmniParser server...")
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        
        omniparser_manager = OmniParserServerManager()
        
        if not omniparser_manager.is_server_ready():
            logger.warning("OmniParser server not running - attempting to start...")
            interface = omniparser_manager.get_interface()
            conda_path = "C:/Users/imitr/anaconda3/Scripts/conda.exe"
            
            if interface.launch_server(conda_path=conda_path, conda_env="automoy_env"):
                logger.info("Server started, waiting for ready...")
                omniparser_manager.server_process = interface.server_process
                
                if omniparser_manager.wait_for_server(timeout=45):
                    logger.info("✓ OmniParser server ready")
                    omniparser = interface
                else:
                    logger.error("✗ Server didn't become ready")
                    return False
            else:
                logger.error("✗ Failed to start server")
                return False
        else:
            logger.info("✓ OmniParser server already running")
            omniparser = omniparser_manager.get_interface()
        
        # Step 4: Parse the screenshot
        logger.info("4. Parsing screenshot with OmniParser...")
        parsed_result = omniparser.parse_screenshot(screenshot)
        
        if not parsed_result:
            logger.error("✗ OmniParser returned no results")
            return False
        
        logger.info("✓ OmniParser analysis completed")
        
        # Step 5: Show results
        logger.info("=== OMNIPARSER RESULTS ===")
        logger.info(f"Type: {type(parsed_result)}")
        
        if isinstance(parsed_result, dict):
            logger.info(f"Keys: {list(parsed_result.keys())}")
            
            if "parsed_content_list" in parsed_result:
                elements = parsed_result["parsed_content_list"]
                logger.info(f"Found {len(elements)} elements")
                
                # Look for Chrome specifically
                chrome_found = []
                
                logger.info("=== SEARCHING FOR CHROME ===")
                for i, element in enumerate(elements):
                    text = element.get("text", "").strip()
                    elem_type = element.get("type", "unknown")
                    
                    # Check for Chrome-related terms
                    if any(term in text.lower() for term in ["chrome", "google", "browser"]) or \
                       any(term in elem_type.lower() for term in ["chrome", "google", "browser"]):
                        chrome_found.append((i, element))
                        logger.info(f"*** CHROME CANDIDATE {len(chrome_found)} ***")
                        logger.info(f"  Element #{i}: {text}")
                        logger.info(f"  Type: {elem_type}")
                        logger.info(f"  Full data: {element}")
                        logger.info("")
                
                if chrome_found:
                    logger.info(f"✓ Found {len(chrome_found)} Chrome candidate(s)!")
                else:
                    logger.warning("✗ No Chrome candidates found")
                    
                    # Show first 5 elements for debugging
                    logger.info("First 5 elements found:")
                    for i, element in enumerate(elements[:5]):
                        text = element.get("text", "").strip()
                        if text:
                            logger.info(f"  {i+1}. '{text}' (type: {element.get('type', 'unknown')})")
            else:
                logger.error("No 'parsed_content_list' found")
        else:
            logger.error(f"Unexpected result type: {type(parsed_result)}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("🔍 SIMPLE CHROME DETECTION TEST")
    logger.info("=" * 50)
    
    success = test_omniparser_detection()
    
    if success:
        logger.info("✅ Test completed - check results above")
    else:
        logger.info("❌ Test failed")
