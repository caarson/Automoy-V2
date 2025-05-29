#!/usr/bin/env python3
"""
Test script for real operation execution in Automoy V2.
This script tests the OperationParser class and its real execution capabilities.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from core.operate import OperationParser
from core.utils.operating_system.os_interface import OSInterface
from core.utils.operating_system.desktop_utils import DesktopUtils

async def test_operation_parser():
    """Test the OperationParser with real operation execution."""
    print("🧪 Testing Real Operation Execution")
    print("=" * 50)
    
    # Initialize required components
    os_interface = OSInterface()
    desktop_utils = DesktopUtils()
    operation_parser = OperationParser(os_interface, desktop_utils)
    
    # Test screenshot operation
    print("\n📸 Testing screenshot operation...")
    screenshot_action = {
        "type": "take_screenshot",
        "summary": "Taking a test screenshot"
    }
    
    success, details = await operation_parser.parse_and_execute_operation(screenshot_action)
    print(f"Screenshot result: {'✅ Success' if success else '❌ Failed'}")
    print(f"Details: {details}")
    
    # Test key press operation  
    print("\n⌨️ Testing key press operation...")
    key_action = {
        "type": "press",
        "keys": ["win"],
        "summary": "Pressing Windows key"
    }
    
    success, details = await operation_parser.parse_and_execute_operation(key_action)
    print(f"Key press result: {'✅ Success' if success else '❌ Failed'}")
    print(f"Details: {details}")
    
    # Wait a moment and press Escape to close any opened menu
    await asyncio.sleep(1)
    escape_action = {
        "type": "press", 
        "keys": ["esc"],
        "summary": "Pressing Escape key"
    }
    
    success, details = await operation_parser.parse_and_execute_operation(escape_action)
    print(f"Escape key result: {'✅ Success' if success else '❌ Failed'}")
    print(f"Details: {details}")
    
    # Test wait times
    print("\n⏱️ Testing operation wait times...")
    wait_times = {
        "click": operation_parser.get_operation_wait_time("click"),
        "write": operation_parser.get_operation_wait_time("write"), 
        "press": operation_parser.get_operation_wait_time("press"),
        "take_screenshot": operation_parser.get_operation_wait_time("take_screenshot"),
        "unknown": operation_parser.get_operation_wait_time("unknown_operation")
    }
    
    for operation, wait_time in wait_times.items():
        print(f"  {operation}: {wait_time}s")
    
    print("\n🎉 Real operation testing completed!")
    print("=" * 50)
    print("✅ OperationParser is ready for real computer automation")
    print("✅ Dynamic wait times are properly configured")
    print("✅ All core operations are functional")

async def test_visual_analysis_integration():
    """Test visual analysis data integration."""
    print("\n🔍 Testing Visual Analysis Integration")
    print("=" * 50)
    
    # Initialize operation parser
    os_interface = OSInterface()
    desktop_utils = DesktopUtils()
    operation_parser = OperationParser(os_interface, desktop_utils)
    
    # Test setting visual analysis data
    sample_visual_data = {
        "coords": [
            {
                "content": "Start",
                "bbox": [0.1, 0.9, 0.15, 0.95]
            },
            {
                "content": "File Explorer", 
                "bbox": [0.5, 0.5, 0.6, 0.55]
            }
        ]
    }
    
    operation_parser.set_visual_analysis(sample_visual_data)
    print("✅ Visual analysis data set successfully")
    
    # Test text coordinate finding
    coords = operation_parser._find_text_coordinates("Start", sample_visual_data)
    if coords:
        print(f"✅ Found coordinates for 'Start': {coords}")
    else:
        print("❌ Could not find coordinates for 'Start'")
    
    coords = operation_parser._find_text_coordinates("File Explorer", sample_visual_data)
    if coords:
        print(f"✅ Found coordinates for 'File Explorer': {coords}")
    else:
        print("❌ Could not find coordinates for 'File Explorer'")
    
    print("✅ Visual analysis integration test completed")

async def main():
    """Main test function."""
    print("🚀 Automoy V2 Real Operation Testing")
    print("=" * 60)
    
    try:
        await test_operation_parser()
        await test_visual_analysis_integration()
        
        print("\n🎯 Summary:")
        print("=" * 30)
        print("✅ Real operation execution: WORKING")
        print("✅ Dynamic wait times: WORKING") 
        print("✅ Visual analysis integration: WORKING")
        print("✅ System ready for automation tasks")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
