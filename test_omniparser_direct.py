#!/usr/bin/env python3

"""
Direct test of OmniParser server to see if it's responding to requests.
"""

import requests
import json
import time
import sys
import os

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

from core.utils.omniparser.omniparser_interface import OmniParserInterface

def test_server_probe():
    """Test if server responds to probe endpoint."""
    print("=== Testing OmniParser Server Probe ===")
    
    try:
        response = requests.get("http://localhost:8111/probe/", timeout=5)
        print(f"✓ Probe successful! Status: {response.status_code}")
        print(f"Response content: {response.text}")
        return True
    except requests.exceptions.ConnectRefused:
        print("❌ Connection refused - server not accessible")
        return False
    except requests.exceptions.Timeout:
        print("❌ Request timed out - server may be hanging")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_omniparser_interface():
    """Test using the OmniParserInterface directly."""
    print("\n=== Testing OmniParserInterface ===")
    
    try:
        interface = OmniParserInterface()
        
        # Check if server is ready
        print("Checking if server is ready...")
        is_ready = interface._check_server_ready()
        print(f"Server ready: {is_ready}")
        
        if not is_ready:
            print("❌ Server not ready, cannot test screenshot parsing")
            return False
            
        # Take a screenshot and test parsing
        print("Taking screenshot for testing...")
        
        # Import desktop utils for screenshot
        from core.utils.operating_system.desktop_utils import DesktopUtils
        desktop_utils = DesktopUtils()
        
        # Take screenshot
        screenshot_path = "test_screenshot.png"
        success = desktop_utils.take_screenshot(screenshot_path)
        
        if not success:
            print("❌ Failed to take screenshot")
            return False
            
        print(f"✓ Screenshot saved to: {screenshot_path}")
        
        # Parse the screenshot
        print("Parsing screenshot with OmniParser...")
        start_time = time.time()
        
        try:
            result = interface.parse_screenshot(screenshot_path)
            parse_time = time.time() - start_time
            
            if result:
                print(f"✓ Parse successful! Time taken: {parse_time:.2f}s")
                
                # Extract key information
                elements = result.get('parsed_content_list', [])
                print(f"Found {len(elements)} elements")
                
                # Show first few elements
                for i, element in enumerate(elements[:3]):
                    element_type = element.get('type', 'unknown')
                    text = element.get('text', '')
                    bbox = element.get('bbox', [])
                    print(f"  Element {i+1}: {element_type} - '{text}' at {bbox}")
                    
                if len(elements) > 3:
                    print(f"  ... and {len(elements) - 3} more elements")
                    
                return True
            else:
                print(f"❌ Parse failed - no result returned (took {parse_time:.2f}s)")
                return False
                
        except Exception as e:
            parse_time = time.time() - start_time
            print(f"❌ Parse error after {parse_time:.2f}s: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Interface test error: {e}")
        return False

def main():
    print("OmniParser Direct Test")
    print("=" * 50)
    
    # Test 1: Server probe
    probe_success = test_server_probe()
    
    # Test 2: Interface test
    if probe_success:
        interface_success = test_omniparser_interface()
    else:
        print("\n❌ Skipping interface test due to probe failure")
        interface_success = False
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print(f"  Server Probe: {'✓ PASS' if probe_success else '❌ FAIL'}")
    print(f"  Interface Test: {'✓ PASS' if interface_success else '❌ FAIL'}")
    
    if probe_success and interface_success:
        print("\n🎉 OmniParser is working correctly!")
    else:
        print("\n⚠️ OmniParser has issues - check server status")

if __name__ == "__main__":
    main()
