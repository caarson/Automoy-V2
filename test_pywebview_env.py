#!/usr/bin/env python3
"""Test script to check if pywebview is available in the current environment."""

import sys
import os

print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Python path: {sys.path[:3]}...")  # Show first 3 paths

try:
    import pywebview
    print(f"✓ PyWebView successfully imported!")
    print(f"  Version: {pywebview.__version__}")
    print(f"  Module path: {pywebview.__file__}")
    
    # Test creating a simple window object
    try:
        window = pywebview.create_window(
            'Test Window',
            'https://www.google.com',
            width=400,
            height=300
        )
        print(f"✓ Window object created successfully: {type(window)}")
    except Exception as e:
        print(f"✗ Failed to create window object: {e}")
        
except ImportError as e:
    print(f"✗ PyWebView import failed: {e}")
    
    # Check if pywebview is installed but has issues
    try:
        import pip
        installed_packages = [pkg.project_name for pkg in pip.get_installed_distributions()]
        if 'pywebview' in installed_packages:
            print("  - pywebview appears to be installed but can't be imported")
        else:
            print("  - pywebview is not installed")
    except:
        print("  - Could not check installed packages")

print("\nEnvironment check complete.")
