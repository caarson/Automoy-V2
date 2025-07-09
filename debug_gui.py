#!/usr/bin/env python3
"""
Test script to verify Automoy GUI window creation works
"""
import os
import sys
import subprocess
import logging
import time

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_pywebview():
    """Test pywebview import and basic functionality"""
    try:
        import webview
        logger.info("✓ pywebview imported successfully")
        
        # Create a simple test window
        logger.info("Creating test window...")
        
        # Test if we can create a window object
        window = webview.create_window(
            'Automoy Test',
            'data:text/html,<h1>Test Window</h1><p>If you see this, pywebview is working!</p>',
            width=800,
            height=600
        )
        
        logger.info("✓ Window created successfully")
        logger.info("Starting webview... (Close the window to continue)")
        
        # Start the webview (this will block until window is closed)
        webview.start(debug=True)
        
        logger.info("✓ Webview finished normally")
        return True
        
    except ImportError as e:
        logger.error(f"✗ Failed to import pywebview: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Error with pywebview: {e}")
        return False

def main():
    logger.info("=== Testing pywebview functionality ===")
    
    if test_pywebview():
        logger.info("✓ pywebview test passed")
        logger.info("Now testing main Automoy application...")
        
        # Run the main application for a few seconds
        try:
            main_process = subprocess.Popen([
                sys.executable, "core/main.py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            logger.info("Main application started. Waiting 10 seconds...")
            time.sleep(10)
            
            if main_process.poll() is None:
                logger.info("✓ Main application is running")
                main_process.terminate()
                main_process.wait(timeout=5)
                logger.info("✓ Main application terminated cleanly")
            else:
                stdout, stderr = main_process.communicate()
                logger.error(f"✗ Main application exited early")
                logger.error(f"STDOUT: {stdout}")
                logger.error(f"STDERR: {stderr}")
                
        except Exception as e:
            logger.error(f"✗ Error running main application: {e}")
    else:
        logger.error("✗ pywebview test failed")

if __name__ == "__main__":
    main()
