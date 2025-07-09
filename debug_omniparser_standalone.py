#!/usr/bin/env python3
"""
Simple OmniParser debugging script to isolate the issue
"""
import sys
import os
import requests
import json
from pathlib import Path
import base64

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_omniparser_directly():
    """Test OmniParser server directly with HTTP requests"""
    print("=== Testing OmniParser Server Directly ===")
    
    server_url = "http://localhost:5100"
    
    # 1. Test server health
    print("1. Testing server health...")
    try:
        response = requests.get(f"{server_url}/probe/", timeout=5)
        print(f"   Health check: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Server is healthy")
        else:
            print(f"   ❌ Server returned: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        return False
    
    # 2. Find a screenshot to test with
    print("2. Finding test screenshot...")
    screenshot_paths = [
        "debug/screenshots",
        "core/utils/omniparser"
    ]
    
    test_image = None
    for path in screenshot_paths:
        if os.path.exists(path):
            images = list(Path(path).glob("*.png"))
            if images:
                test_image = images[0]
                break
    
    if not test_image:
        print("   ❌ No test images found")
        return False
    
    print(f"   Found test image: {test_image}")
    
    # 3. Test image encoding
    print("3. Testing image encoding...")
    try:
        with open(test_image, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()
        print(f"   Image encoded to {len(image_data)} base64 characters")
    except Exception as e:
        print(f"   ❌ Failed to encode image: {e}")
        return False
    
    # 4. Test OmniParser API call
    print("4. Testing OmniParser API call...")
    try:
        payload = {"base64_image": image_data}
        response = requests.post(
            f"{server_url}/parse/", 
            json=payload, 
            timeout=60
        )
        
        print(f"   Response status: {response.status_code}")
        print(f"   Response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"   ✅ Successfully got JSON response")
                print(f"   Response keys: {list(result.keys())}")
                
                if "parsed_content_list" in result:
                    print(f"   Found {len(result['parsed_content_list'])} parsed items")
                    return True
                else:
                    print(f"   ❌ No 'parsed_content_list' in response")
                    print(f"   Full response: {json.dumps(result, indent=2)[:500]}...")
                    return False
                    
            except json.JSONDecodeError as e:
                print(f"   ❌ Failed to decode JSON: {e}")
                print(f"   Raw response: {response.text[:500]}...")
                return False
        else:
            print(f"   ❌ Request failed with status {response.status_code}")
            print(f"   Response: {response.text[:500]}...")
            return False
            
    except Exception as e:
        print(f"   ❌ API call failed: {e}")
        return False

def test_omniparser_interface():
    """Test using the OmniParser interface class"""
    print("\n=== Testing OmniParser Interface Class ===")
    
    try:
        from core.utils.omniparser.omniparser_interface import OmniParserInterface
        
        # Initialize interface
        omniparser = OmniParserInterface(server_url="http://localhost:5100")
        
        # Check if server is ready
        print("1. Checking server readiness...")
        if omniparser._check_server_ready():
            print("   ✅ Server is ready")
        else:
            print("   ❌ Server is not ready")
            return False
        
        # Find test image
        print("2. Finding test screenshot...")
        screenshot_paths = [
            "debug/screenshots",
            "core/utils/omniparser"
        ]
        
        test_image = None
        for path in screenshot_paths:
            if os.path.exists(path):
                images = list(Path(path).glob("*.png"))
                if images:
                    test_image = images[0]
                    break
        
        if not test_image:
            print("   ❌ No test images found")
            return False
        
        print(f"   Using test image: {test_image}")
        
        # Test parsing
        print("3. Testing screenshot parsing...")
        result = omniparser.parse_screenshot(str(test_image))
        
        if result:
            print("   ✅ Parsing successful")
            print(f"   Result keys: {list(result.keys())}")
            if "parsed_content_list" in result:
                print(f"   Found {len(result['parsed_content_list'])} parsed items")
            if "coords" in result:
                print(f"   Found {len(result['coords'])} coordinate items")
            return True
        else:
            print("   ❌ Parsing failed - no result returned")
            return False
            
    except Exception as e:
        print(f"   ❌ Interface test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("OmniParser Debug Test")
    print("====================\n")
    
    # Test direct HTTP API
    direct_test = test_omniparser_directly()
    
    # Test interface class
    interface_test = test_omniparser_interface()
    
    print(f"\n=== Results ===")
    print(f"Direct API test: {'✅ PASS' if direct_test else '❌ FAIL'}")
    print(f"Interface test:  {'✅ PASS' if interface_test else '❌ FAIL'}")
    
    if direct_test and interface_test:
        print("\n🎉 All tests passed! OmniParser is working correctly.")
    else:
        print("\n💥 Some tests failed. Check the output above for details.")
