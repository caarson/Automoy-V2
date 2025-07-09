#!/usr/bin/env python3

import requests
import base64
import json
from PIL import Image
import io

def test_omniparser_server():
    try:
        # Test health endpoint
        print("Testing OmniParser health endpoint...")
        health_response = requests.get("http://localhost:5100/probe", timeout=5)
        print(f"Health check status: {health_response.status_code}")
        
        # Create a test image
        test_image = Image.new('RGB', (200, 100), color='blue')
        buffered = io.BytesIO()
        test_image.save(buffered, format="PNG")
        test_image_base64 = base64.b64encode(buffered.getvalue()).decode('ascii')
        
        # Test parse endpoint
        print("Testing OmniParser parse endpoint...")
        parse_data = {"base64_image": test_image_base64}
        parse_response = requests.post(
            "http://localhost:5100/parse/", 
            json=parse_data,
            timeout=10
        )
        
        print(f"Parse status: {parse_response.status_code}")
        if parse_response.status_code == 200:
            result = parse_response.json()
            print(f"Parse successful! Found {len(result.get('parsed_content_list', []))} elements")
            print(f"Response keys: {list(result.keys())}")
            return True
        else:
            print(f"Parse failed with status {parse_response.status_code}")
            print(f"Response: {parse_response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to OmniParser server on port 5100")
        return False
    except requests.exceptions.Timeout:
        print("✗ Request to OmniParser server timed out")
        return False
    except Exception as e:
        print(f"✗ Error testing OmniParser: {e}")
        return False

if __name__ == "__main__":
    test_omniparser_server()
