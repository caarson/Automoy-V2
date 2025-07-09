"""Install pywebview and dependencies in the automoy_env environment."""

import subprocess
import sys
import os

def run_command(cmd):
    """Run a command and print the output."""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"SUCCESS: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {e.stderr}")
        return False

def main():
    # Path to the automoy_env Python executable
    automoy_python = r"C:\Users\imitr\anaconda3\envs\automoy_env\python.exe"
    
    if not os.path.exists(automoy_python):
        print(f"ERROR: Python executable not found at {automoy_python}")
        return False
    
    print(f"Installing packages using: {automoy_python}")
    
    # Install packages using pip in the automoy_env environment
    packages = [
        "pywebview",
        "PyQt5",
        "PyQtWebEngine"
    ]
    
    for package in packages:
        print(f"\n--- Installing {package} ---")
        if not run_command([automoy_python, "-m", "pip", "install", package]):
            print(f"Failed to install {package}")
        
    # Test the installation
    print(f"\n--- Testing pywebview import ---")
    test_script = '''
try:
    import pywebview
    print(f"SUCCESS: PyWebView {pywebview.__version__} imported successfully")
except ImportError as e:
    print(f"ERROR: Failed to import pywebview: {e}")
'''
    
    run_command([automoy_python, "-c", test_script])

if __name__ == "__main__":
    main()
