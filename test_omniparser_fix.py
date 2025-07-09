#!/usr/bin/env python3
"""
Test script to start OmniParser server and verify the fixes work.
"""
import os
import sys
import subprocess
import time
import requests

def start_omniparser_server():
    """Start the OmniParser server in the background."""
    print("Starting OmniParser server...")
    
    # Change to the OmniParser directory
    omniparser_dir = os.path.join(os.getcwd(), "dependencies", "OmniParser-master")
    os.chdir(omniparser_dir)
    
    # Set PYTHONPATH to include the OmniParser directory
    env = os.environ.copy()
    env['PYTHONPATH'] = omniparser_dir
    
    # Start the server
    cmd = [
        "conda", "run", "-n", "automoy_env", "python", 
        "omnitool/omniparserserver/omniparserserver.py",
        "--host", "0.0.0.0", "--port", "5100"
    ]
    
    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait a bit for the server to start
    time.sleep(10)
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:5100/probe/", timeout=5)
        if response.status_code == 200:
            print("✅ OmniParser server started successfully!")
            return process
        else:
            print(f"❌ Server responded with status {response.status_code}")
            return None
    except requests.RequestException as e:
        print(f"❌ Failed to connect to server: {e}")
        # Print server output for debugging
        stdout, stderr = process.communicate(timeout=5)
        print(f"Server stdout: {stdout}")
        print(f"Server stderr: {stderr}")
        return None

def test_omniparser_parsing():
    """Test the OmniParser parsing functionality."""
    print("Testing OmniParser parsing...")
    
    try:
        # Create a simple test image (base64 encoded)
        import base64
        from PIL import Image
        import io
        
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='white')
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
            print("✅ OmniParser parsing test successful!")
            return True
        else:
            print(f"❌ Parsing failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error during parsing test: {e}")
        return False

if __name__ == "__main__":
    print("Testing OmniParser fixes...")
    
    # Start the server
    server_process = start_omniparser_server()
    
    if server_process:
        try:
            # Test parsing
            success = test_omniparser_parsing()
            
            if success:
                print("🎉 All tests passed! OmniParser is working correctly.")
            else:
                print("❌ Parsing test failed. Check the server logs.")
                
        finally:
            # Clean up
            print("Stopping server...")
            server_process.terminate()
            server_process.wait()
    else:
        print("❌ Failed to start OmniParser server.")
        sys.exit(1)
