#!/usr/bin/env python3
"""
Targeted test for Automoy GUI window creation
"""
import os
import sys
import subprocess
import time
import threading

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_automoy_window():
    """Test creating the exact same window as Automoy"""
    try:
        # Import everything we need
        import webview
        from config.config import VERSION, GUI_HOST, GUI_PORT, GUI_WIDTH, GUI_HEIGHT, GUI_RESIZABLE, GUI_ON_TOP
        
        print(f"Config loaded - Version: {VERSION}")
        print(f"GUI Settings: {GUI_HOST}:{GUI_PORT}, Size: {GUI_WIDTH}x{GUI_HEIGHT}")
        print(f"Window options: resizable={GUI_RESIZABLE}, on_top={GUI_ON_TOP}")
        
        # Start a simple HTTP server to simulate the GUI backend
        print("Starting simple HTTP server...")
        server_process = subprocess.Popen([
            sys.executable, "-m", "http.server", str(GUI_PORT), "--bind", GUI_HOST
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=".")
        
        # Wait for server to start
        time.sleep(2)
        
        # Test if server is reachable
        import urllib.request
        try:
            with urllib.request.urlopen(f"http://{GUI_HOST}:{GUI_PORT}", timeout=2.0) as response:
                print(f"✓ HTTP server is reachable (status: {response.status})")
        except Exception as e:
            print(f"✗ Cannot reach HTTP server: {e}")
            server_process.terminate()
            return False
        
        # Create window exactly like Automoy does
        gui_url = f"http://{GUI_HOST}:{GUI_PORT}"
        window_title = f"Automoy GUI @ {VERSION} - {gui_url}"
        
        print(f"Creating window with URL: {gui_url}")
        print(f"Window title: {window_title}")
        
        # Create a simple JSBridge mock
        class MockJSBridge:
            def __init__(self):
                self.stop_event = threading.Event()
            def shutdown(self):
                self.stop_event.set()
        
        js_bridge = MockJSBridge()
        
        window = webview.create_window(
            title=window_title,
            url=gui_url,
            width=GUI_WIDTH,
            height=GUI_HEIGHT,
            resizable=GUI_RESIZABLE,
            on_top=GUI_ON_TOP,
            frameless=False,  # Use frameless=False for testing
            js_api=js_bridge
        )
        
        print(f"Window created: {window}")
        print("Starting webview... Window should appear now!")
        
        # Start the webview
        webview.start(debug=True)
        
        print("✓ Window test completed")
        
        # Cleanup
        server_process.terminate()
        server_process.wait(timeout=5)
        
        return True
        
    except Exception as e:
        print(f"✗ Error in window test: {e}")
        import traceback
        traceback.print_exc()
        if 'server_process' in locals():
            server_process.terminate()
        return False

def main():
    print("=== Automoy Window Test ===")
    print("This test creates the exact same window as Automoy should create.\n")
    
    if test_automoy_window():
        print("\n✓ Automoy window test passed!")
        print("If the window appeared, then pywebview is working correctly.")
        print("The issue might be in the Automoy application logic.")
    else:
        print("\n✗ Automoy window test failed!")

if __name__ == "__main__":
    main()
