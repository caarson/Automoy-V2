#!/usr/bin/env python3
"""
Simple script to install pywebview
"""
import subprocess
import sys

def install_pywebview():
    """Install pywebview using pip"""
    try:
        # Try installing pywebview
        result = subprocess.run([sys.executable, "-m", "pip", "install", "pywebview"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("SUCCESS: pywebview installed successfully!")
            print(result.stdout)
        else:
            print("ERROR: Failed to install pywebview")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            
        # Test the installation
        print("\nTesting import...")
        try:
            import pywebview
            print(f"SUCCESS: pywebview {pywebview.__version__} is now available!")
            return True
        except ImportError as e:
            print(f"ERROR: Failed to import pywebview: {e}")
            return False
            
    except Exception as e:
        print(f"ERROR: Exception during installation: {e}")
        return False

if __name__ == "__main__":
    install_pywebview()
