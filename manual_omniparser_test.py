#!/usr/bin/env python3
"""
Quick test to start OmniParser manually and capture errors.
"""

import subprocess
import sys
import os
import time
from pathlib import Path

def start_omniparser_manual():
    """Start OmniParser manually to see errors."""
    # Set up paths
    project_root = Path(__file__).parent
    server_dir = project_root / "dependencies" / "OmniParser-master" / "omnitool" / "omniparserserver"
    conda_exe = r"C:\Users\imitr\anaconda3\Scripts\conda.exe"
    
    # Environment variables for better debugging
    env = os.environ.copy()
    env.update({
        'PYTHONUNBUFFERED': '1',
        'CUDA_VISIBLE_DEVICES': '0',  # Force single GPU if available
        'TORCH_USE_CUDA_DSA': '1',    # Enable CUDA debugging
    })
    
    # Command to start server
    cmd = [
        conda_exe, "run", "-n", "automoy_env",
        sys.executable, "omniparserserver.py",
        "--som_model_path", "../../weights/icon_detect/model.pt",
        "--caption_model_name", "florence2",
        "--caption_model_path", "../../weights/icon_caption_florence",
        "--device", "cpu",  # Start with CPU to avoid CUDA issues
        "--BOX_TRESHOLD", "0.15",
        "--port", "5100",
        "--host", "127.0.0.1"
    ]
    
    print("Starting OmniParser server manually...")
    print(f"Command: {' '.join(cmd)}")
    print(f"Working directory: {server_dir}")
    print(f"Environment variables added: PYTHONUNBUFFERED, CUDA_VISIBLE_DEVICES, TORCH_USE_CUDA_DSA")
    print("-" * 60)
    
    try:
        # Start the process with real-time output
        process = subprocess.Popen(
            cmd,
            cwd=server_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )
        
        print(f"Process started with PID: {process.pid}")
        print("Real-time output:")
        print("-" * 40)
        
        # Read output in real-time
        try:
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    print(f"[SERVER] {output.strip()}")
        except KeyboardInterrupt:
            print("\nInterrupted by user")
        
        # Get final status
        exit_code = process.wait()
        print(f"\nProcess exited with code: {exit_code}")
        
    except Exception as e:
        print(f"Error starting process: {e}")

if __name__ == "__main__":
    start_omniparser_manual()
