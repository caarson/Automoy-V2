#!/usr/bin/env python3
"""
Simplified version of Automoy main.py focused on GUI window creation
"""
import os
import sys
import subprocess
import time
import threading
import logging

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def simplified_main():
    """Simplified main function that focuses on GUI window creation"""
    try:
        # Import everything
        import webview
        from config.config import VERSION, GUI_HOST, GUI_PORT, GUI_WIDTH, GUI_HEIGHT, GUI_RESIZABLE, GUI_ON_TOP
        
        logger.info("=== Simplified Automoy GUI Test ===")
        logger.info(f"Version: {VERSION}")
        logger.info(f"GUI: {GUI_HOST}:{GUI_PORT}")
        logger.info(f"pywebview available: {webview is not None}")
        
        # Start GUI subprocess (simplified version)
        gui_script_path = os.path.join("gui", "gui.py")
        gui_command = [sys.executable, "-u", gui_script_path, "--host", GUI_HOST, "--port", str(GUI_PORT)]
        
        logger.info(f"Starting GUI subprocess: {' '.join(gui_command)}")
        
        gui_process = subprocess.Popen(
            gui_command, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        logger.info(f"GUI process started (PID: {gui_process.pid})")
        
        # Wait for GUI to be ready (simplified health check)
        logger.info("Waiting for GUI to be ready...")
        time.sleep(5)  # Simple wait instead of health check
        
        # Create window
        gui_url = f"http://{GUI_HOST}:{GUI_PORT}"
        window_title = f"Automoy GUI @ {VERSION} - {gui_url}"
        
        logger.info(f"Creating window: {window_title}")
        logger.info(f"URL: {gui_url}")
        
        # Mock JSBridge
        class MockJSBridge:
            def __init__(self):
                self.stop_event = threading.Event()
            def shutdown(self):
                self.stop_event.set()
        
        window = webview.create_window(
            title=window_title,
            url=gui_url,
            width=GUI_WIDTH,
            height=GUI_HEIGHT,
            resizable=GUI_RESIZABLE,
            on_top=GUI_ON_TOP,
            frameless=False,  # Use normal window for testing
            js_api=MockJSBridge()
        )
        
        logger.info(f"Window created: {window}")
        logger.info("Calling webview.start()...")
        
        # This should show the window
        webview.start(debug=True)
        
        logger.info("webview.start() returned - window was closed")
        
        # Cleanup
        if gui_process and gui_process.poll() is None:
            logger.info("Terminating GUI process...")
            gui_process.terminate()
            gui_process.wait(timeout=5)
            
        logger.info("✓ Test completed successfully")
        
    except Exception as e:
        logger.error(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Cleanup on error
        if 'gui_process' in locals() and gui_process and gui_process.poll() is None:
            gui_process.terminate()

if __name__ == "__main__":
    simplified_main()
