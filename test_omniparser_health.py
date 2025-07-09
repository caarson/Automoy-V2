#!/usr/bin/env python3
"""
Test script to verify OmniParser server is working correctly.
"""

import requests
import json
import os

def test_omniparser():
    base_url = "http://localhost:5100"
    
    print("Testing OmniParser server...")
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"✓ Health check: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False
    
    # Test with a screenshot if available
    screenshot_dir = "debug/screenshots"
    if os.path.exists(screenshot_dir):
        screenshots = [f for f in os.listdir(screenshot_dir) if f.endswith('.png')]
        if screenshots:
            latest_screenshot = sorted(screenshots)[-1]
            screenshot_path = os.path.join(screenshot_dir, latest_screenshot)
            
            print(f"Testing with screenshot: {screenshot_path}")
            
            try:
                with open(screenshot_path, 'rb') as f:
                    files = {'image': f}
                    response = requests.post(f"{base_url}/parse", files=files, timeout=30)
                
                print(f"Parse request status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✓ Parse successful. Found {len(result.get('elements', []))} elements")
                    
                    # Show first few elements
                    elements = result.get('elements', [])
                    for i, elem in enumerate(elements[:3]):
                        print(f"  Element {i+1}: {elem.get('label', 'No label')} - {elem.get('description', 'No description')}")
                    
                    return True
                else:
                    print(f"✗ Parse failed: {response.text}")
                    return False
                    
            except Exception as e:
                print(f"✗ Parse request failed: {e}")
                return False
        else:
            print("No screenshots found to test with")
    else:
        print("Screenshot directory not found")
    
    return True

if __name__ == "__main__":
    test_omniparser()
