#!/usr/bin/env python3

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

def test_omniparser_chrome_detection():
    """Test OmniParser Chrome detection with complete element analysis."""
    try:
        logger.info("=== Simple OmniParser Chrome Test ===")
        logger.info("1. Importing modules...")
        
        from core.utils.screenshot_utils import capture_screen_pil
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        
        logger.info("2. Initializing OmniParser...")
        omniparser_manager = OmniParserServerManager()
        
        if omniparser_manager.is_server_ready():
            logger.info("✓ OmniParser server is ready")
            omniparser = omniparser_manager.get_interface()
        else:
            logger.error("✗ OmniParser server is not ready")
            return False
        
        logger.info("3. Taking desktop screenshot...")
        screenshot = capture_screen_pil("omniparser_test_screenshot.png")
        
        if not screenshot:
            logger.error("✗ Failed to capture screenshot")
            return False
            
        logger.info("✓ Screenshot captured successfully")
        
        # Parse with OmniParser
        logger.info("4. Parsing screenshot with OmniParser...")
        parsed_result = omniparser.parse_screenshot(screenshot)
        
        if not parsed_result:
            logger.error("✗ OmniParser returned None")
            return False
        
        # Print the complete structure of OmniParser results
        logger.info("=== RAW OMNIPARSER RESULTS ===")
        logger.info(f"Result type: {type(parsed_result)}")
        logger.info(f"Result keys: {list(parsed_result.keys()) if isinstance(parsed_result, dict) else 'Not a dict'}")
        
        if isinstance(parsed_result, dict):
            for key, value in parsed_result.items():
                if key == "parsed_content_list":
                    logger.info(f"  {key}: List with {len(value) if isinstance(value, list) else 'Unknown'} items")
                else:
                    logger.info(f"  {key}: {type(value)} = {str(value)[:200]}")
            
        if "parsed_content_list" not in parsed_result:
            logger.error("✗ OmniParser result missing 'parsed_content_list'")
            logger.info(f"Available keys: {list(parsed_result.keys())}")
            return False
            
        elements = parsed_result.get("parsed_content_list", [])
        logger.info(f"✓ Found {len(elements)} UI elements")
        
        # Show ALL elements detected by OmniParser
        logger.info("=== ALL DETECTED ELEMENTS ===")
        for i, element in enumerate(elements):
            logger.info(f"Element {i+1}:")
            logger.info(f"  Full element: {element}")
            
            # Extract key information
            text = element.get("text", "").strip()
            elem_type = element.get("type", "unknown")
            interactable = element.get("interactable", False)
            
            logger.info(f"  Text: '{text}'")
            logger.info(f"  Type: {elem_type}")
            logger.info(f"  Interactable: {interactable}")
            
            if "box" in element or "bbox" in element:
                box = element.get("box") or element.get("bbox")
                logger.info(f"  Bounding box: {box}")
            
            logger.info("")  # Empty line for readability
        
        # Look for Chrome candidates with expanded criteria
        logger.info("=== SEARCHING FOR BROWSER CANDIDATES ===")
        chrome_candidates = []
        browser_terms = ["chrome", "google", "browser", "internet", "explorer", "edge", "firefox", "opera"]
        
        for i, element in enumerate(elements):
            text = element.get("text", "").lower().strip()
            elem_type = element.get("type", "").lower()
            
            # Check if any browser term appears in the text
            is_browser = any(term in text for term in browser_terms)
            
            if is_browser or "chrome" in elem_type:
                chrome_candidates.append((i, element))
                logger.info(f"BROWSER CANDIDATE {len(chrome_candidates)}: Element {i+1}")
                logger.info(f"  Text: '{element.get('text', '')}'")
                logger.info(f"  Type: {element.get('type', 'unknown')}")
                logger.info(f"  Interactable: {element.get('interactable', False)}")
                if "box" in element or "bbox" in element:
                    box = element.get("box") or element.get("bbox")
                    logger.info(f"  Box: {box}")
                logger.info("")
        
        if chrome_candidates:
            logger.info(f"✓ Found {len(chrome_candidates)} browser-related candidates")
        else:
            logger.warning("✗ No browser-related elements found")
            
        logger.info("=== TEST COMPLETE ===")
        return True
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("🔍 SIMPLE OMNIPARSER CHROME DETECTION TEST")
    logger.info("=" * 80)
    
    success = test_omniparser_chrome_detection()
    
    if success:
        logger.info("=" * 80)
        logger.info("✅ SIMPLE OMNIPARSER TEST COMPLETED SUCCESSFULLY!")
        logger.info("=" * 80)
    else:
        logger.info("=" * 80)
        logger.info("❌ SIMPLE OMNIPARSER TEST FAILED!")
        logger.info("=" * 80)
