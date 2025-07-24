#!/usr/bin/env python3

"""
Test OmniParser server startup to diagnose hanging issues.
"""

import os
import sys
import subprocess
import time
import requests

print("=" * 60)
print("OmniParser Startup Diagnostics")
print("=" * 60)

# Check if we're in the right environment
print(f"Python executable: {sys.executable}")
print(f"Current working directory: {os.getcwd()}")

# Check if conda environment is active
conda_env = os.environ.get('CONDA_DEFAULT_ENV', 'Not set')
print(f"Conda environment: {conda_env}")

# Check if required dependencies are available
print("\nChecking dependencies...")

required_modules = ['torch', 'torchvision', 'transformers', 'pillow', 'requests', 'uvicorn']
for module in required_modules:
    try:
        __import__(module)
        print(f"  ✓ {module}")
    except ImportError:
        print(f"  ❌ {module} - MISSING")

# Check model files
print("\nChecking model files...")
model_paths = [
    "dependencies/OmniParser-master/weights/icon_detect/model.pt",
    "dependencies/OmniParser-master/weights/icon_caption_florence"
]

for path in model_paths:
    if os.path.exists(path):
        print(f"  ✓ {path}")
    else:
        print(f"  ❌ {path} - NOT FOUND")

# Try to start server with detailed output
print("\nAttempting to start OmniParser server...")
print("Command: python omniparserserver.py --device cpu --port 8111")
print("-" * 40)

try:
    # Change to server directory
    server_dir = "dependencies/OmniParser-master/omnitool/omniparserserver"
    
    if not os.path.exists(server_dir):
        print(f"❌ Server directory not found: {server_dir}")
        sys.exit(1)
    
    os.chdir(server_dir)
    print(f"Changed to directory: {os.getcwd()}")
    
    # Check if server script exists
    if not os.path.exists("omniparserserver.py"):
        print("❌ omniparserserver.py not found in current directory")
        sys.exit(1)
    
    print("✓ omniparserserver.py found")
    
    # Start server with minimal args first
    cmd = [
        sys.executable, "omniparserserver.py",
        "--som_model_path", "../../weights/icon_detect/model.pt",
        "--caption_model_path", "../../weights/icon_caption_florence",
        "--device", "cpu",
        "--BOX_TRESHOLD", "0.15",
        "--port", "8111"
    ]
    
    print(f"Starting process: {' '.join(cmd)}")
    
    # Start server with timeout
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    print(f"Process started with PID: {process.pid}")
    
    # Wait for startup with timeout
    startup_timeout = 60  # seconds
    start_time = time.time()
    
    while time.time() - start_time < startup_timeout:
        # Check if process is still running
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print(f"\n❌ Process terminated early!")
            print(f"Exit code: {process.returncode}")
            print(f"STDOUT:\n{stdout}")
            print(f"STDERR:\n{stderr}")
            break
            
        # Check if server is responding
        try:
            response = requests.get("http://localhost:8111/probe/", timeout=1)
            if response.status_code == 200:
                print(f"\n✓ Server is responding! (took {time.time() - start_time:.1f}s)")
                print(f"Response: {response.text}")
                
                # Cleanup
                process.terminate()
                process.wait(5)
                print("✓ Server stopped cleanly")
                sys.exit(0)
        except requests.RequestException:
            pass
            
        print(f"  Waiting... ({time.time() - start_time:.1f}s)")
        time.sleep(2)
    
    # Timeout reached
    print(f"\n❌ Server startup timed out after {startup_timeout}s")
    
    # Get any output
    try:
        stdout, stderr = process.communicate(timeout=5)
        print(f"STDOUT:\n{stdout}")
        print(f"STDERR:\n{stderr}")
    except subprocess.TimeoutExpired:
        print("Process still running, forcing termination...")
        process.kill()
        stdout, stderr = process.communicate()
        print(f"STDOUT:\n{stdout}")
        print(f"STDERR:\n{stderr}")
    
except Exception as e:
    print(f"❌ Error during server startup test: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Diagnostics complete")
