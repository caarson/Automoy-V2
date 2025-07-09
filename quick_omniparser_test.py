#!/usr/bin/env python3
"""
Quick test to check if OmniParser is working after our fixes.
"""
import requests
import time
import base64
from PIL import Image
import io

def test_omniparser_health():
    """Test if OmniParser server is running and responsive."""
    print("Testing OmniParser health...")
    
    try:
        response = requests.get("http://localhost:5100/probe/", timeout=5)
        if response.status_code == 200:
            print("✅ OmniParser server is running!")
            return True
        else:
            print(f"❌ Server responded with status {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"❌ Failed to connect to OmniParser server: {e}")
        return False

def test_omniparser_parsing():
    """Test OmniParser parsing with a simple image."""
    print("Testing OmniParser parsing...")
    
    try:
        # Create a simple test image
        img = Image.new('RGB', (200, 100), color='white')
        # Add some text-like rectangles to simulate UI elements
        draw = Image.ImageDraw.Draw(img)
        draw.rectangle([10, 10, 90, 40], fill='blue')
        draw.rectangle([110, 50, 190, 80], fill='green')
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_data = buffer.getvalue()
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        
        # Test the parsing endpoint
        response = requests.post(
            "http://localhost:5100/parse/",
            json={"image": img_base64},
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ OmniParser parsing successful!")
            result = response.json()
            print(f"   Response keys: {list(result.keys()) if isinstance(result, dict) else 'Non-dict response'}")
            return True
        else:
            print(f"❌ Parsing failed with status {response.status_code}")
            print(f"   Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error during parsing test: {e}")
        return False

def main():
    print("🔍 Testing OmniParser fixes...")
    print("=" * 50)
    
    # Test health first
    if not test_omniparser_health():
        print("❌ OmniParser server is not running. Please start it first.")
        return False
    
    # Wait a moment for server to be fully ready
    time.sleep(2)
    
    # Test parsing
    if test_omniparser_parsing():
        print("\n🎉 All tests passed! OmniParser is working correctly.")
        return True
    else:
        print("\n❌ Parsing test failed. Check the fixes.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
