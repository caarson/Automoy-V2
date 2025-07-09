#!/usr/bin/env python3
"""
Setup script to install pywebview and run Automoy with native GUI
"""
import subprocess
import sys
import os
import time

def install_pywebview():
    """Install pywebview in the correct environment"""
    print("Installing pywebview...")
    
    conda_python = "C:\\Users\\imitr\\anaconda3\\envs\\automoy_env\\python.exe"
    
    try:
        cmd = [conda_python, "-m", "pip", "install", "pywebview"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print("✓ pywebview installed!")
            
            # Test import
            test_cmd = [conda_python, "-c", "import pywebview; print(f'pywebview {pywebview.__version__} ready')"]
            test_result = subprocess.run(test_cmd, capture_output=True, text=True)
            
            if test_result.returncode == 0:
                print("✓ pywebview import successful!")
                return True
            else:
                print("✗ pywebview import failed")
                return False
        else:
            print("✗ pywebview installation failed")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False

def run_app():
    """Run the Automoy application"""
    print("Starting Automoy...")
    
    conda_python = "C:\\Users\\imitr\\anaconda3\\envs\\automoy_env\\python.exe"
    
    try:
        cmd = [conda_python, "core/main.py"]
        print("This should open a native GUI window...")
        
        # Start the application
        process = subprocess.Popen(cmd)
        
        print("✓ Automoy started!")
        print("Check for the native GUI window or access: http://127.0.0.1:8001")
        return True
        
    except Exception as e:
        print(f"Error starting app: {e}")
        return False

if __name__ == "__main__":
    print("=== Automoy Native GUI Setup ===")
    
    if install_pywebview():
        if run_app():
            print("🎉 SUCCESS! Native GUI should be opening!")
        else:
            print("❌ Failed to start application")
    else:
        print("❌ Failed to install pywebview")
    
    input("Press Enter to exit...")
