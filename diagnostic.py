#!/usr/bin/env python3
"""
Simple diagnostic script to test Automoy V2 startup
"""
import sys
import os

print("=== Automoy V2 Diagnostic Test ===")
print(f"Python version: {sys.version}")
print(f"Current working directory: {os.getcwd()}")
print(f"Python path: {sys.path[:3]}...")  # Show first 3 entries

# Test basic imports
try:
    print("\n1. Testing basic Python modules...")
    import asyncio
    import json
    import signal
    import subprocess
    import threading
    import time
    print("   ✓ Basic modules imported successfully")
except ImportError as e:
    print(f"   ✗ Basic module import failed: {e}")
    sys.exit(1)

# Test external dependencies
try:
    print("\n2. Testing external dependencies...")
    import requests
    print("   ✓ requests imported")
    import httpx
    print("   ✓ httpx imported")
    import webview
    print("   ✓ pywebview imported")
except ImportError as e:
    print(f"   ✗ External dependency missing: {e}")
    print("   Run: pip install requests httpx pywebview")
    sys.exit(1)

# Test project path setup
try:
    print("\n3. Testing project structure...")
    PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    print(f"   ✓ Project root: {PROJECT_ROOT}")
    
    # Check for required directories
    required_dirs = ['config', 'core', 'gui']
    for dirname in required_dirs:
        dirpath = os.path.join(PROJECT_ROOT, dirname)
        if os.path.exists(dirpath):
            print(f"   ✓ Found directory: {dirname}")
        else:
            print(f"   ✗ Missing directory: {dirname}")
except Exception as e:
    print(f"   ✗ Project structure test failed: {e}")
    sys.exit(1)

# Test config import
try:
    print("\n4. Testing config import...")
    import config.config as app_config
    print("   ✓ Config imported successfully")
    
    # Try to access some config values
    try:
        gui_host = getattr(app_config, 'GUI_HOST', 'localhost')
        gui_port = getattr(app_config, 'GUI_PORT', 8888)
        print(f"   ✓ GUI config: {gui_host}:{gui_port}")
    except Exception as e:
        print(f"   ⚠ Config access warning: {e}")
        
except ImportError as e:
    print(f"   ✗ Config import failed: {e}")
    print("   Check if config/config.py exists and is properly formatted")
    sys.exit(1)

# Test core imports
try:
    print("\n5. Testing core module imports...")
    from core.data_models import AutomoyStatus, OperatorState
    print("   ✓ Data models imported")
    
    # Test if we can create instances
    status = AutomoyStatus.IDLE
    state = OperatorState()
    print(f"   ✓ Created test instances: {status}, {state.status}")
    
except ImportError as e:
    print(f"   ✗ Core module import failed: {e}")
    print("   Check if core/data_models.py exists")
    sys.exit(1)

print("\n=== All diagnostic tests passed! ===")
print("The Automoy V2 application should be able to start.")
print("Try running: python core/main.py")
