#!/usr/bin/env python3
"""
Debug script to test Automoy startup step by step
"""
import os
import sys
import subprocess
import time

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_main_import():
    """Test if we can import main module"""
    try:
        # Test basic imports
        print("Testing basic imports...")
        import asyncio
        import threading
        print("✓ Standard library imports OK")
        
        # Test pywebview
        import webview
        print("✓ pywebview import OK")
        
        # Test config imports
        from config.config import VERSION, GUI_HOST, GUI_PORT
        print(f"✓ Config imports OK - Version: {VERSION}, GUI: {GUI_HOST}:{GUI_PORT}")
        
        # Test core imports
        from core.data_models import get_initial_state
        print("✓ Core imports OK")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gui_health():
    """Test if GUI server can be reached"""
    try:
        from config.config import GUI_HOST, GUI_PORT
        import urllib.request
        
        url = f"http://{GUI_HOST}:{GUI_PORT}/health"
        print(f"Testing GUI health at: {url}")
        
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                if response.status == 200:
                    print("✓ GUI server is healthy")
                    return True
        except Exception:
            print("✗ GUI server not reachable")
            return False
    except Exception as e:
        print(f"✗ Error testing GUI health: {e}")
        return False

def test_gui_subprocess():
    """Test starting GUI subprocess"""
    try:
        from config.config import GUI_HOST, GUI_PORT
        
        gui_script_path = os.path.join("gui", "gui.py")
        gui_command = [sys.executable, "-u", gui_script_path, "--host", GUI_HOST, "--port", str(GUI_PORT)]
        
        print(f"Starting GUI subprocess: {' '.join(gui_command)}")
        
        gui_process = subprocess.Popen(
            gui_command, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        print(f"GUI process started with PID: {gui_process.pid}")
        
        # Wait a moment for startup
        time.sleep(3)
        
        # Check if process is still running
        if gui_process.poll() is None:
            print("✓ GUI process is running")
            
            # Test health
            if test_gui_health():
                print("✓ GUI subprocess test passed")
                gui_process.terminate()
                gui_process.wait(timeout=5)
                return True
            else:
                print("✗ GUI health check failed")
                gui_process.terminate()
                return False
        else:
            stdout, stderr = gui_process.communicate()
            print(f"✗ GUI process exited early")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing GUI subprocess: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=== Automoy Debug Test ===\n")
    
    # Test 1: Imports
    print("1. Testing imports...")
    if not test_main_import():
        print("✗ Import test failed")
        return
    
    print("\n2. Testing GUI subprocess...")
    if not test_gui_subprocess():
        print("✗ GUI subprocess test failed")
        return
    
    print("\n✓ All tests passed! The issue might be in the main application logic.")
    print("\nTrying to run main application for 10 seconds...")
    
    try:
        main_process = subprocess.Popen([
            sys.executable, "core/main.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        print("Main application started, waiting 10 seconds...")
        time.sleep(10)
        
        if main_process.poll() is None:
            print("✓ Main application is running")
            main_process.terminate()
            main_process.wait(timeout=5)
        else:
            stdout, stderr = main_process.communicate()
            print("✗ Main application exited early")
            print(f"STDOUT:\n{stdout}")
            print(f"STDERR:\n{stderr}")
            
    except Exception as e:
        print(f"✗ Error running main application: {e}")

if __name__ == "__main__":
    main()
