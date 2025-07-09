import os
import sys
import time
import requests
from pathlib import Path

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.utils.omniparser.omniparser_interface import OmniParserInterface

def test_omniparser():
    print("Testing OmniParser functionality...")
    
    # Test 1: Check if server is already running
    print("1. Checking if OmniParser server is running on port 5100...")
    omniparser = OmniParserInterface(server_url="http://localhost:5100")
    
    if omniparser._check_server_ready():
        print("✅ OmniParser server is already running on port 5100")
    else:
        print("❌ OmniParser server is not running on port 5100")
        print("2. Attempting to launch OmniParser server...")
        
        launch_success = omniparser.launch_server(
            port=5100,
            conda_env='automoy_env'
        )
        
        if launch_success:
            print("✅ OmniParser server launched successfully")
        else:
            print("❌ Failed to launch OmniParser server")
            return
    
    # Test 2: Test screenshot parsing
    print("3. Testing screenshot parsing...")
    
    # Find a screenshot to test with
    screenshot_dir = Path("debug/screenshots")
    if screenshot_dir.exists():
        screenshots = list(screenshot_dir.glob("*.png"))
        if screenshots:
            test_screenshot = screenshots[0]
            print(f"Found test screenshot: {test_screenshot}")
            
            try:
                result = omniparser.parse_screenshot(str(test_screenshot))
                if result:
                    print("✅ Screenshot parsing successful")
                    print(f"Keys in result: {list(result.keys())}")
                    if 'parsed_content_list' in result:
                        print(f"Number of parsed items: {len(result['parsed_content_list'])}")
                    if 'coords' in result:
                        print(f"Number of coords: {len(result['coords'])}")
                else:
                    print("❌ Screenshot parsing failed - no result returned")
            except Exception as e:
                print(f"❌ Screenshot parsing failed with exception: {e}")
        else:
            print("❌ No screenshots found in debug/screenshots")
    else:
        print("❌ Screenshot directory not found")

if __name__ == "__main__":
    test_omniparser()
