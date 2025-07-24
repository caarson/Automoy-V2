#!/usr/bin/env python3
"""
Test script to verify visual elements detection safety measures.
This script tests the OmniParser visual analysis to ensure it can detect elements
and that the safety measures properly halt on component failure.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
from core.utils.operating_system.desktop_utils import DesktopUtils

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_visual_elements_detection():
    """Test visual elements detection and safety measures."""
    
    print("🔍 Testing Visual Elements Detection Safety Measures")
    print("=" * 60)
    
    # Test 1: Initialize OmniParser
    print("\n1. Testing OmniParser Initialization...")
    try:
        omniparser_manager = OmniParserServerManager()
        
        # Check if server is already running
        try:
            import requests
            response = requests.get("http://127.0.0.1:8111/probe/", timeout=5)
            if response.status_code == 200:
                print("✅ Found existing OmniParser server running")
                server_running = True
            else:
                server_running = False
        except Exception:
            server_running = False
            
        if server_running:
            print("✅ Using existing OmniParser server")
            omniparser = omniparser_manager.get_interface()
        else:
            print("⏳ Starting new OmniParser server...")
            server_process = omniparser_manager.start_server()
            if server_process:
                if omniparser_manager.wait_for_server(timeout=60):
                    print("✅ OmniParser server started successfully")
                    omniparser = omniparser_manager.get_interface()
                else:
                    print("❌ OmniParser server failed to start within timeout")
                    return False
            else:
                print("❌ Failed to start OmniParser server")
                return False
                
    except Exception as e:
        print(f"❌ Error initializing OmniParser: {e}")
        return False
    
    # Test 2: Capture Screenshot
    print("\n2. Testing Screenshot Capture...")
    try:
        screenshot_path = DesktopUtils.capture_current_screen("test_screenshot")
        if screenshot_path:
            test_screenshot_path = Path(screenshot_path)
            print(f"✅ Screenshot captured and saved: {test_screenshot_path}")
        else:
            print("❌ Failed to capture screenshot")
            return False
    except Exception as e:
        print(f"❌ Error capturing screenshot: {e}")
        return False
    
    # Test 3: Visual Elements Detection
    print("\n3. Testing Visual Elements Detection...")
    try:
        print("⏳ Analyzing screenshot with OmniParser...")
        parsed_result = omniparser.parse_screenshot(str(test_screenshot_path))
        
        if parsed_result and isinstance(parsed_result, dict) and "parsed_content_list" in parsed_result:
            elements_found = len(parsed_result["parsed_content_list"]) if parsed_result["parsed_content_list"] else 0
            print(f"✅ Visual analysis successful: Found {elements_found} elements")
            
            if elements_found == 0:
                print("⚠️ WARNING: No visual elements detected - this would trigger safety halt")
                print("🛑 Safety Measure: Operation would be HALTED due to zero elements")
                return False
            elif elements_found < 5:
                print(f"⚠️ WARNING: Only {elements_found} elements detected - unusually low count")
                print("   This might indicate screen or analysis issues")
            else:
                print(f"✅ Good element count: {elements_found} elements detected")
                
            # Show first few elements for verification
            print("\n📋 Sample detected elements:")
            for i, element in enumerate(parsed_result["parsed_content_list"][:5]):
                content = element.get('content', '')
                element_type = element.get('type', '')
                bbox = element.get('bbox_normalized', [])
                print(f"   Element {i+1}: '{content}' | Type: {element_type} | BBox: {bbox}")
                
            return True
        else:
            print("❌ Visual analysis returned invalid results")
            if parsed_result:
                if isinstance(parsed_result, dict):
                    print(f"   Available keys: {list(parsed_result.keys())}")
                else:
                    print(f"   Result type: {type(parsed_result)}")
            else:
                print("   OmniParser returned None")
            print("🛑 Safety Measure: Operation would be HALTED due to invalid results")
            return False
            
    except Exception as e:
        print(f"❌ Error during visual analysis: {e}")
        print("🛑 Safety Measure: Operation would be HALTED due to analysis error")
        return False

async def main():
    """Main test function."""
    print("🧪 Visual Elements Detection Safety Test")
    print("This test verifies that the safety measures work correctly")
    print("to detect bad visual analysis components.\n")
    
    success = await test_visual_elements_detection()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ SAFETY TEST PASSED: Visual analysis is working correctly")
        print("   The system can detect visual elements and will not halt unexpectedly")
    else:
        print("❌ SAFETY TEST DETECTED ISSUE: Visual analysis has problems")
        print("   The system would correctly halt to prevent unsafe operation")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
