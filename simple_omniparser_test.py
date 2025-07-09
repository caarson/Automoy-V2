import requests
import json

def test_omniparser_simple():
    """Simple test to check if OmniParser server is responding"""
    try:
        # Test health endpoint
        print("Testing OmniParser health...")
        response = requests.get("http://localhost:5100/probe/", timeout=5)
        print(f"Health check response: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ OmniParser server is running and healthy")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to connect to OmniParser: {e}")
        return False

if __name__ == "__main__":
    test_omniparser_simple()
