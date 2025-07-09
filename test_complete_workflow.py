#!/usr/bin/env python3
"""
Test the complete Automoy workflow without file-based goal submission
"""
import sys
import os
from pathlib import Path
import asyncio

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_complete_workflow():
    """Test the complete workflow by directly calling operator methods"""
    print("=== Testing Complete Automoy Workflow ===")
    
    try:
        # Import required modules
        from core.operate import AutomoyOperator
        from core.utils.omniparser.omniparser_interface import OmniParserInterface
        from core.utils.operating_system.desktop_utils import DesktopUtils
        from core.data_models import write_state
        
        print("1. ✅ Successfully imported all modules")
        
        # Initialize OmniParser
        print("2. Initializing OmniParser...")
        omniparser = OmniParserInterface(server_url="http://localhost:5100")
        
        if omniparser._check_server_ready():
            print("   ✅ OmniParser server is ready")
        else:
            print("   ❌ OmniParser server is not ready")
            return False
            
        # Create mock dependencies
        print("3. Setting up operator dependencies...")
        
        async def mock_gui_update(payload):
            print(f"   GUI Update: {payload}")
            
        async def mock_window_manager(action):
            print(f"   Window action: {action}")
            return True
            
        # Initialize operator
        stop_event = asyncio.Event()
        pause_event = asyncio.Event()
        pause_event.set()
        
        operator = AutomoyOperator(
            stop_event=stop_event,
            webview_window=None,
            gui_host="127.0.0.1",
            gui_port=8001,
            objective="Take a screenshot and analyze what's on the desktop",
            pause_event=pause_event
        )
        
        # Set dependencies
        operator.manage_gui_window_func = mock_window_manager
        operator._update_gui_state_func = mock_gui_update
        operator.omniparser = omniparser
        operator.desktop_utils = DesktopUtils()
        
        print("   ✅ Operator initialized with all dependencies")
        
        # Test screenshot capture
        print("4. Testing screenshot capture...")
        try:
            # Take a screenshot
            screenshot_path = await operator._take_screenshot("test")
            if screenshot_path and screenshot_path.exists():
                print(f"   ✅ Screenshot captured: {screenshot_path}")
                print(f"   Screenshot size: {screenshot_path.stat().st_size} bytes")
            else:
                print("   ❌ Screenshot capture failed")
                return False
        except Exception as e:
            print(f"   ❌ Screenshot capture error: {e}")
            return False
            
        # Test visual analysis
        print("5. Testing visual analysis...")
        try:
            processed_path, analysis = await operator._perform_visual_analysis(
                screenshot_path, "Test analysis"
            )
            
            if analysis:
                print("   ✅ Visual analysis successful")
                print(f"   Analysis length: {len(analysis)} characters")
                print(f"   Analysis preview: {analysis[:200]}...")
                
                if processed_path:
                    print(f"   ✅ Processed screenshot: {processed_path}")
                else:
                    print("   ⚠️  No processed screenshot generated")
                    
                return True
            else:
                print("   ❌ Visual analysis failed - no result")
                return False
                
        except Exception as e:
            print(f"   ❌ Visual analysis error: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"❌ Workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Complete Workflow Test")
    print("=====================\n")
    
    result = asyncio.run(test_complete_workflow())
    
    print(f"\n=== Result ===")
    if result:
        print("🎉 Complete workflow test PASSED!")
        print("   The OmniParser and operator are working correctly.")
    else:
        print("💥 Complete workflow test FAILED!")
        print("   There's an issue with the core workflow components.")
