#!/usr/bin/env python3
"""
Simple Chrome detection test
"""

import os
import sys
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def simple_chrome_test():
    """Simple synchronous test for Chrome detection"""
    
    print("=== Simple Chrome Detection Test ===")
    
    try:
        # Import required modules
        print("1. Importing modules...")
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.screenshot_utils import capture_screen_pil
        import subprocess
        import time
        
        # Initialize OmniParser
        print("2. Setting up OmniParser...")
        omniparser_manager = OmniParserServerManager()
        
        if omniparser_manager.is_server_ready():
            print("✓ OmniParser server is ready")
            omniparser = omniparser_manager.get_interface()
        else:
            print("✗ OmniParser server is not ready")
            return False
            
        # Capture screenshot
        print("3. Capturing screenshot...")
        screenshot = capture_screen_pil()
        if not screenshot:
            print("✗ Failed to capture screenshot")
            return False
        print(f"✓ Screenshot captured: {screenshot.size}")
        
        # Parse with OmniParser
        print("4. Parsing screenshot with OmniParser...")
        try:
            parsed_result = omniparser.parse_screenshot(screenshot)
        except Exception as parse_error:
            print(f"✗ OmniParser parsing failed: {parse_error}")
            return False
        
        if not parsed_result:
            print("✗ OmniParser returned None")
            return False
            
        if "parsed_content_list" not in parsed_result:
            print("✗ OmniParser result missing 'parsed_content_list'")
            print(f"Available keys: {list(parsed_result.keys())}")
            return False
            
        elements = parsed_result.get("parsed_content_list", [])
        print(f"✓ Found {len(elements)} UI elements")
        
        # Search for Chrome
        print("5. Searching for Chrome elements...")
        chrome_elements = []
        
        for i, element in enumerate(elements[:20]):  # Limit to first 20 for brevity
            element_text = element.get("content", "").lower()
            element_type = element.get("type", "").lower()
            bbox = element.get("bbox_normalized", [])
            interactivity = element.get("interactivity", False)
            
            # Check for Chrome indicators
            is_chrome_candidate = (
                "chrome" in element_text or
                "google chrome" in element_text or
                "google" in element_text or
                ("browser" in element_text) or
                (element_type == "icon" and interactivity)
            )
            
            print(f"   Element {i}: '{element_text}' (type: {element_type}, interactive: {interactivity})")
            
            if is_chrome_candidate:
                print(f"   ★ CHROME CANDIDATE: '{element_text}'")
                if bbox and not all(x == 0 for x in bbox):
                    chrome_elements.append((i, element))
                    print(f"   ✓ Has valid coordinates: {bbox}")
                else:
                    print(f"   ⚠ No valid coordinates")
        
        if chrome_elements:
            print(f"\n✅ FOUND {len(chrome_elements)} CHROME ELEMENT(S) WITH COORDINATES!")
            for idx, (i, element) in enumerate(chrome_elements):
                print(f"Chrome option {idx+1}: '{element.get('content', '')}' (element {i})")
            return True
        else:
            print(f"\n❌ NO CHROME ELEMENTS FOUND WITH VALID COORDINATES")
            print("All interactive elements found:")
            for i, element in enumerate(elements[:10]):
                if element.get("interactivity", False):
                    print(f"   Interactive {i}: '{element.get('content', '')}' (type: {element.get('type', '')})")
            return False
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = simple_chrome_test()
    print("\n" + "="*60)
    if success:
        print("✅ CHROME DETECTION TEST PASSED!")
    else:
        print("❌ CHROME DETECTION TEST FAILED!")
    print("="*60)
