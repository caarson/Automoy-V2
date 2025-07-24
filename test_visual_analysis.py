#!/usr/bin/env python3
"""
Test script to directly check what OmniParser detects on the current desktop
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.utils.omniparser.omniparser_interface import OmniParserInterface
from core.utils.screenshot_utils import take_screenshot

async def test_desktop_visual_analysis():
    """Test what OmniParser detects on the current desktop"""
    
    # Take a screenshot first
    print("📸 Taking screenshot of current desktop...")
    screenshot_path = await take_screenshot("test_desktop_analysis")
    print(f"✅ Screenshot saved: {screenshot_path}")
    
    # Initialize OmniParser
    print("🔧 Initializing OmniParser...")
    omniparser = OmniParserInterface()
    print("✅ OmniParser initialized")
    
    # Analyze the screenshot
    print("🔍 Analyzing screenshot with OmniParser...")
    analysis_result = await omniparser.parse_screenshot(
        screenshot_path=str(screenshot_path),
        query="Find all UI elements, buttons, icons, and clickable items on screen"
    )
    
    print(f"\n📊 Analysis Results:")
    print(f"Type: {type(analysis_result)}")
    
    if analysis_result:
        if isinstance(analysis_result, dict):
            print(f"Keys: {list(analysis_result.keys())}")
            
            if "parsed_content_list" in analysis_result:
                elements = analysis_result["parsed_content_list"]
                print(f"🔢 Number of elements found: {len(elements) if elements else 0}")
                
                if elements:
                    print(f"\n📋 First 10 elements:")
                    for i, element in enumerate(elements[:10]):
                        element_text = element.get("content", "")
                        element_type = element.get("type", "unknown")
                        bbox = element.get("bbox_normalized", [])
                        print(f"  {i+1}. Text: '{element_text}' | Type: {element_type} | BBox: {bbox}")
                        
                        # Check if it might be Chrome
                        if element_text and "chrome" in element_text.lower():
                            print(f"     🎯 CHROME FOUND: {element_text}")
                else:
                    print("❌ No elements found in parsed_content_list")
            else:
                print("❌ No 'parsed_content_list' key found")
        else:
            print(f"Analysis result: {analysis_result}")
    else:
        print("❌ No analysis result returned")

if __name__ == "__main__":
    asyncio.run(test_desktop_visual_analysis())
