#!/usr/bin/env python3
"""
Test OmniParser startup and basic functionality.
This script will help diagnose what's preventing OmniParser from working.
"""

import os
import sys
import traceback
import subprocess
import time
import requests
from pathlib import Path

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_omniparser_imports():
    """Test if we can import OmniParser dependencies."""
    print("=== Testing OmniParser Imports ===")
    
    try:
        import torch
        print(f"✅ PyTorch: {torch.__version__}")
        print(f"   CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"   CUDA device count: {torch.cuda.device_count()}")
            print(f"   Current device: {torch.cuda.current_device()}")
    except ImportError as e:
        print(f"❌ PyTorch import failed: {e}")
        return False
    
    try:
        from PIL import Image
        print(f"✅ Pillow: {Image.__version__}")
    except ImportError as e:
        print(f"❌ Pillow import failed: {e}")
        return False
    
    try:
        import easyocr
        print(f"✅ EasyOCR imported successfully")
    except ImportError as e:
        print(f"❌ EasyOCR import failed: {e}")
        return False
    
    try:
        import ultralytics
        print(f"✅ Ultralytics YOLO imported successfully")
    except ImportError as e:
        print(f"❌ Ultralytics import failed: {e}")
        return False
    
    return True

def test_omniparser_module():
    """Test if we can import and initialize the OmniParser module."""
    print("\n=== Testing OmniParser Module ===")
    
    # Import torch first
    try:
        import torch
    except ImportError:
        print("❌ PyTorch not available for device check")
        return False
    
    # Change to OmniParser directory
    omni_root = PROJECT_ROOT / "dependencies" / "OmniParser-master"
    if not omni_root.exists():
        print(f"❌ OmniParser directory not found: {omni_root}")
        return False
    
    print(f"OmniParser root: {omni_root}")
    
    # Add OmniParser root to path
    sys.path.insert(0, str(omni_root))
    
    try:
        from util.omniparser import Omniparser
        print("✅ OmniParser class imported successfully")
        
        # Test configuration
        config = {
            'som_model_path': str(omni_root / "weights" / "icon_detect" / "model.pt"),
            'caption_model_name': 'florence2',
            'caption_model_path': str(omni_root / "weights" / "icon_caption_florence"),
            'device': 'cuda' if torch.cuda.is_available() else 'cpu',
            'BOX_TRESHOLD': 0.15
        }
        
        print("Config:")
        for key, value in config.items():
            print(f"  {key}: {value}")
        
        # Check if model files exist
        model_pt = Path(config['som_model_path'])
        caption_path = Path(config['caption_model_path'])
        
        if not model_pt.exists():
            print(f"❌ SOM model not found: {model_pt}")
            return False
        print(f"✅ SOM model found: {model_pt}")
        
        if not caption_path.exists():
            print(f"❌ Caption model not found: {caption_path}")
            return False
        print(f"✅ Caption model found: {caption_path}")
        
        # Try to initialize OmniParser
        print("Initializing OmniParser...")
        parser = Omniparser(config)
        print("✅ OmniParser initialized successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ OmniParser initialization failed: {e}")
        print("Full traceback:")
        traceback.print_exc()
        return False

def test_server_startup():
    """Test if we can start the OmniParser server."""
    print("\n=== Testing Server Startup ===")
    
    omni_server_dir = PROJECT_ROOT / "dependencies" / "OmniParser-master" / "omnitool" / "omniparserserver"
    conda_path = r"C:\Users\imitr\anaconda3\Scripts\conda.exe"
    
    if not omni_server_dir.exists():
        print(f"❌ Server directory not found: {omni_server_dir}")
        return False
    
    # Command to start server
    cmd = [
        conda_path, "run", "-n", "automoy_env",
        sys.executable, "omniparserserver.py",
        "--som_model_path", "../../weights/icon_detect/model.pt",
        "--caption_model_name", "florence2",
        "--caption_model_path", "../../weights/icon_caption_florence",
        "--device", "cuda",
        "--BOX_TRESHOLD", "0.15",
        "--port", "8111",
    ]
    
    print(f"Starting server with command: {' '.join(cmd)}")
    print(f"Working directory: {omni_server_dir}")
    
    try:
        # Start the server process
        process = subprocess.Popen(
            cmd,
            cwd=omni_server_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        
        print("Server process started, waiting for it to become ready...")
        
        # Monitor server output for a few seconds
        start_time = time.time()
        while time.time() - start_time < 30:  # Wait up to 30 seconds
            # Check if process is still running
            if process.poll() is not None:
                print("❌ Server process exited early")
                # Read any output
                stdout, stderr = process.communicate()
                if stdout:
                    print("STDOUT:", stdout)
                return False
            
            # Check if server is ready
            try:
                response = requests.get("http://localhost:8111/probe/", timeout=2)
                if response.status_code == 200:
                    print("✅ Server is ready!")
                    
                    # Try to read some output
                    if process.stdout:
                        import select
                        ready, _, _ = select.select([process.stdout], [], [], 0)
                        if ready:
                            output = process.stdout.read(1024)
                            if output:
                                print(f"Server output: {output}")
                    
                    # Stop the server
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    
                    return True
                    
            except requests.RequestException:
                pass  # Server not ready yet
            
            time.sleep(1)
        
        print("❌ Server did not become ready within 30 seconds")
        
        # Read any available output
        try:
            stdout, stderr = process.communicate(timeout=5)
            if stdout:
                print("STDOUT:", stdout)
            if stderr:
                print("STDERR:", stderr)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            if stdout:
                print("STDOUT:", stdout)
            if stderr:
                print("STDERR:", stderr)
        
        return False
        
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("OmniParser Diagnostic Test")
    print("=" * 50)
    
    # Test 1: Basic imports
    if not test_omniparser_imports():
        print("\n❌ Basic imports failed. Cannot continue.")
        return
    
    # Test 2: OmniParser module
    if not test_omniparser_module():
        print("\n❌ OmniParser module test failed. Cannot continue.")
        return
    
    # Test 3: Server startup
    if not test_server_startup():
        print("\n❌ Server startup test failed.")
        return
    
    print("\n✅ All tests passed! OmniParser should be working.")

if __name__ == "__main__":
    main()
