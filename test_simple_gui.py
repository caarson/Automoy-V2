#!/usr/bin/env python3
"""
Simplified test version of main.py to debug GUI window creation
"""
import os
import sys
import subprocess
import time
import logging

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import pywebview
try:
    import webview
    PYWEBVIEW_AVAILABLE = True
    logger.info("✓ pywebview imported successfully")
except ImportError as e:
    webview = None
    PYWEBVIEW_AVAILABLE = False
    logger.error(f"✗ Failed to import pywebview: {e}")

def test_gui_window():
    """Test creating a GUI window"""
    if not PYWEBVIEW_AVAILABLE:
        logger.error("pywebview not available - cannot create native window")
        return False
    
    # Start a simple GUI subprocess (just a basic HTTP server)
    logger.info("Starting simple HTTP server for testing...")
    try:
        # Simple HTTP server
        gui_process = subprocess.Popen([
            sys.executable, "-m", "http.server", "8080"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait a moment for server to start
        time.sleep(2)
        
        # Create webview window
        logger.info("Creating webview window...")
        window = webview.create_window(
            'Automoy Test GUI',
            'http://localhost:8080',
            width=1024,
            height=768,
            resizable=True
        )
        
        logger.info("Starting webview...")
        webview.start(debug=True)
        logger.info("Webview finished")
        
        # Clean up
        gui_process.terminate()
        return True
        
    except Exception as e:
        logger.error(f"Error creating GUI window: {e}")
        return False

if __name__ == "__main__":
    logger.info("=== Automoy GUI Test ===")
    success = test_gui_window()
    if success:
        logger.info("✓ GUI test completed successfully")
    else:
        logger.error("✗ GUI test failed")
        sys.exit(1)
