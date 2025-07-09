#!/usr/bin/env python3
"""
Simple test to manually start OmniParser server and check for errors.
"""

import os
import sys
import subprocess
import time
import requests
from pathlib import Path

# Get paths
PROJECT_ROOT = Path(__file__).parent
OMNI_ROOT = PROJECT_ROOT / "dependencies" / "OmniParser-master"
SERVER_DIR = OMNI_ROOT / "omnitool" / "omniparserserver"
CONDA_PATH = r"C:\Users\imitr\anaconda3\Scripts\conda.exe"

def test_basic_server_start():
    """Test basic server startup with minimal arguments."""
    print("=== Testing Basic OmniParser Server Startup ===")
    
    if not SERVER_DIR.exists():
        print(f"❌ Server directory not found: {SERVER_DIR}")
        return False
    
    # Start with minimal args first
    cmd = [
        CONDA_PATH, "run", "-n", "automoy_env",
        sys.executable, "omniparserserver.py",
        "--som_model_path", "../../weights/icon_detect/model.pt",
        "--caption_model_name", "florence2", 
        "--caption_model_path", "../../weights/icon_caption_florence",
        "--device", "cpu",  # Use CPU first to avoid CUDA issues
        "--BOX_TRESHOLD", "0.15",
        "--port", "5100",
        "--host", "0.0.0.0"
    ]
    
    print(f"Command: {' '.join(cmd)}")
    print(f"Working directory: {SERVER_DIR}")
    
    try:
        # Start the process
        process = subprocess.Popen(
            cmd,
            cwd=SERVER_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        
        print(f"Process started with PID: {process.pid}")
        print("Monitoring output for 30 seconds...")
        
        # Monitor for 30 seconds
        start_time = time.time()
        server_ready = False
        
        while time.time() - start_time < 30:
            # Check if process is still alive
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                print("❌ Process exited early!")
                print("STDOUT:")
                print(stdout)
                print("STDERR:")
                print(stderr)
                return False
            
            # Try to connect to server
            try:
                response = requests.get("http://localhost:5100/probe/", timeout=2)
                if response.status_code == 200:
                    print("✅ Server is responding!")
                    server_ready = True
                    break
            except requests.RequestException:
                pass
            
            # Check for any output
            try:
                # Non-blocking read from stdout
                import select
                ready, _, _ = select.select([process.stdout], [], [], 0.1)
                if ready:
                    line = process.stdout.readline()
                    if line:
                        print(f"[SERVER] {line.strip()}")
            except:
                pass
            
            time.sleep(1)
        
        if server_ready:
            print("✅ Server startup successful!")
        else:
            print("❌ Server did not become ready within 30 seconds")
            
        # Clean up
        print("Terminating server...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            
        return server_ready
        
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return False

def test_python_environment():
    """Test if the conda environment has the required packages."""
    print("\n=== Testing Python Environment ===")
    
    cmd = [
        CONDA_PATH, "run", "-n", "automoy_env",
        sys.executable, "-c", 
        "import torch; import PIL; import easyocr; import ultralytics; print('All packages available')"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("✅ All required packages are available")
            print(f"Output: {result.stdout.strip()}")
            return True
        else:
            print("❌ Missing packages or import errors")
            print(f"STDERR: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error checking environment: {e}")
        return False

def test_model_files():
    """Test if model files exist and are accessible."""
    print("\n=== Testing Model Files ===")
    
    som_model = OMNI_ROOT / "weights" / "icon_detect" / "model.pt"
    caption_model = OMNI_ROOT / "weights" / "icon_caption_florence"
    
    if not som_model.exists():
        print(f"❌ SOM model not found: {som_model}")
        return False
    else:
        print(f"✅ SOM model found: {som_model}")
    
    if not caption_model.exists():
        print(f"❌ Caption model directory not found: {caption_model}")
        return False
    else:
        print(f"✅ Caption model directory found: {caption_model}")
        
        # Check for required files in caption model
        config_file = caption_model / "config.json"
        model_file = caption_model / "model.safetensors"
        
        if not config_file.exists():
            print(f"❌ Caption model config not found: {config_file}")
            return False
        
        if not model_file.exists():
            print(f"❌ Caption model weights not found: {model_file}")
            return False
            
        print(f"✅ Caption model files are complete")
    
    return True

def main():
    print("OmniParser Server Test")
    print("=" * 40)
    
    # Test 1: Model files
    if not test_model_files():
        print("❌ Model files test failed")
        return
    
    # Test 2: Python environment
    if not test_python_environment():
        print("❌ Python environment test failed")
        return
    
    # Test 3: Server startup
    if not test_basic_server_start():
        print("❌ Server startup test failed")
        return
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    main()
