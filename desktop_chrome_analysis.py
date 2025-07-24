#!/usr/bin/env python3
"""
Chrome Icon Detection Test - Desktop Screenshot & OmniParser Analysis
This test will:
1. Show the desktop by minimizing all windows
2. Take a screenshot of the desktop
3. Use OmniParser to analyze the screenshot
4. Look specifically for Google Chrome icon
5. Report detailed findings
"""

import logging
import sys
import os
import time
import subprocess

# Add the project directory to sys.path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def show_desktop():
    """Minimize all windows to show the desktop."""
    try:
        logger.info("Showing desktop by minimizing all windows...")
        
        # Method 1: Win+D to show desktop
        import pyautogui
        pyautogui.hotkey('win', 'd')
        time.sleep(2)  # Wait for desktop to be shown
        
        logger.info("✓ Desktop shown using Win+D")
        return True
        
    except Exception as e:
        logger.error(f"✗ Error showing desktop: {e}")
        return False

def test_chrome_icon_detection():
    """Complete test for Chrome icon detection using OmniParser."""
    try:
        logger.info("=== Chrome Icon Detection Test ===")
        
        # Step 1: Show desktop
        logger.info("1. Showing desktop...")
        if not show_desktop():
            logger.error("Failed to show desktop")
            return False
        
        # Step 2: Import required modules
        logger.info("2. Importing modules...")
        from core.utils.screenshot_utils import capture_screen_pil
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        
        # Step 3: Initialize OmniParser
        logger.info("3. Initializing OmniParser...")
        omniparser_manager = OmniParserServerManager()
        
        # Check if server is ready or start it
        if omniparser_manager.is_server_ready():
            logger.info("✓ OmniParser server is already running")
            omniparser = omniparser_manager.get_interface()
        else:
            logger.info("Starting OmniParser server...")
            # Set explicit conda path to fix the issue
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
        
        # Step 4: Take desktop screenshot
        logger.info("4. Taking desktop screenshot...")
        screenshot_path = "desktop_chrome_analysis.png"
        screenshot = capture_screen_pil(screenshot_path)
        
        if not screenshot:
            logger.error("✗ Failed to capture desktop screenshot")
            return False
            
        logger.info(f"✓ Desktop screenshot captured: {screenshot_path}")
        logger.info(f"Screenshot size: {screenshot.size}")
        
        # Step 5: Analyze with OmniParser
        logger.info("5. Analyzing screenshot with OmniParser...")
        parsed_result = omniparser.parse_screenshot(screenshot)
        
        if not parsed_result:
            logger.error("✗ OmniParser returned no results")
            return False
        
        # Step 6: Print complete OmniParser results
        logger.info("=== COMPLETE OMNIPARSER RESULTS ===")
        logger.info(f"Result type: {type(parsed_result)}")
        
        if isinstance(parsed_result, dict):
            logger.info(f"Result keys: {list(parsed_result.keys())}")
            
            for key, value in parsed_result.items():
                if key == "parsed_content_list":
                    logger.info(f"  {key}: List with {len(value)} items")
                else:
                    logger.info(f"  {key}: {type(value)} - {str(value)[:200]}...")
        
        # Step 7: Analyze elements for Chrome
        if "parsed_content_list" not in parsed_result:
            logger.error("✗ No 'parsed_content_list' found in results")
            return False
        
        elements = parsed_result["parsed_content_list"]
        logger.info(f"✓ Found {len(elements)} UI elements to analyze")
        
        # Step 8: Print ALL detected elements
        logger.info("=== ALL DETECTED ELEMENTS ===")
        chrome_candidates = []
        
        for i, element in enumerate(elements, 1):
            logger.info(f"--- Element {i} ---")
            logger.info(f"  Full element data: {element}")
            
            # Extract key fields
            text = element.get("text", "").strip()
            elem_type = element.get("type", "unknown")
            interactable = element.get("interactable", False)
            
            logger.info(f"  Text: '{text}'")
            logger.info(f"  Type: {elem_type}")
            logger.info(f"  Interactable: {interactable}")
            
            # Check for bounding box
            box = element.get("box") or element.get("bbox") or element.get("coordinates")
            if box:
                logger.info(f"  Bounding box: {box}")
            
            # Check if this could be Chrome
            chrome_terms = ["chrome", "google", "browser"]
            text_lower = text.lower()
            type_lower = elem_type.lower()
            
            is_chrome_candidate = any(term in text_lower for term in chrome_terms) or any(term in type_lower for term in chrome_terms)
            
            if is_chrome_candidate:
                chrome_candidates.append((i, element))
                logger.info(f"  *** CHROME CANDIDATE DETECTED ***")
            
            logger.info("")  # Empty line for readability
        
        # Step 9: Report Chrome findings
        logger.info("=== CHROME DETECTION RESULTS ===")
        if chrome_candidates:
            logger.info(f"✓ Found {len(chrome_candidates)} Chrome candidate(s)!")
            
            for idx, (element_num, element) in enumerate(chrome_candidates, 1):
                logger.info(f"Chrome Candidate #{idx} (Element {element_num}):")
                logger.info(f"  Text: '{element.get('text', '')}'")
                logger.info(f"  Type: {element.get('type', 'unknown')}")
                logger.info(f"  Interactable: {element.get('interactable', False)}")
                
                box = element.get("box") or element.get("bbox") or element.get("coordinates")
                if box:
                    logger.info(f"  Location: {box}")
                    
                    # If we have coordinates, show where we could click
                    if isinstance(box, (list, tuple)) and len(box) >= 4:
                        x1, y1, x2, y2 = box[:4]
                        center_x = (x1 + x2) // 2
                        center_y = (y1 + y2) // 2
                        logger.info(f"  Click coordinates: ({center_x}, {center_y})")
                
                logger.info("")
        else:
            logger.warning("✗ No Chrome candidates found in the analysis")
            
            # Show some other elements for context
            logger.info("Sample of other detected elements:")
            for i, element in enumerate(elements[:10], 1):  # Show first 10 elements
                text = element.get("text", "").strip()
                if text:
                    logger.info(f"  {i}. '{text}' (type: {element.get('type', 'unknown')})")
        
        logger.info("=== ANALYSIS COMPLETE ===")
        return True
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("🔍 CHROME ICON DETECTION TEST - DESKTOP ANALYSIS")
    logger.info("=" * 80)
    
    # Install pyautogui if needed
    try:
        import pyautogui
        pyautogui.FAILSAFE = False  # Disable failsafe for automation
    except ImportError:
        logger.info("Installing pyautogui...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyautogui"])
        import pyautogui
        pyautogui.FAILSAFE = False
    
    success = test_chrome_icon_detection()
    
    logger.info("=" * 80)
    if success:
        logger.info("✅ CHROME ICON DETECTION TEST COMPLETED!")
        logger.info("Check the logs above for detailed OmniParser analysis results.")
        logger.info("Screenshot saved as: desktop_chrome_analysis.png")
    else:
        logger.info("❌ CHROME ICON DETECTION TEST FAILED!")
        logger.info("Check the error messages above for troubleshooting.")
    logger.info("=" * 80)
