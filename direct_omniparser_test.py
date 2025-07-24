#!/usr/bin/env python3

import logging
import sys
import os
import subprocess

# Add the project directory to sys.path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def direct_omniparser_test():
    """Direct OmniParser server start without using the interface."""
    try:
        logger.info("=== Direct OmniParser Server Start ===")
        
        # Direct server startup command
        conda_path = "C:/Users/imitr/anaconda3/Scripts/conda.exe"
        server_dir = "c:/Users/imitr/OneDrive/Documentos/GitHub/Automoy-V2/dependencies/OmniParser-master/omnitool/omniparserserver"
        
        cmd = [
            conda_path, "run", "-n", "automoy_env",
            sys.executable, "omniparserserver.py",
            "--som_model_path", "../../../weights/icon_detect/model.pt",
            "--caption_model_name", "florence2", 
            "--caption_model_path", "../../../weights/icon_caption_florence",
            "--device", "cpu",
            "--BOX_TRESHOLD", "0.15",
            "--port", "8111"
        ]
        
        logger.info(f"Starting OmniParser server...")
        logger.info(f"Command: {' '.join(cmd)}")
        logger.info(f"Working directory: {server_dir}")
        
        # Start the server process
        process = subprocess.Popen(
            cmd,
            cwd=server_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        logger.info(f"Server process started with PID: {process.pid}")
        
        # Give it a moment to start
        import time
        time.sleep(5)
        
        # Check if process is still running
        if process.poll() is None:
            logger.info("✓ Server process is running")
            
            # Test connection to the server
            import requests
            try:
                response = requests.get("http://localhost:8111", timeout=5)
                logger.info(f"✓ Server responded with status: {response.status_code}")
            except requests.RequestException as e:
                logger.info(f"Server connection test: {e}")
                
            # Show some output
            try:
                stdout, stderr = process.communicate(timeout=2)
                if stdout:
                    logger.info(f"Server stdout: {stdout[:500]}")
                if stderr:
                    logger.info(f"Server stderr: {stderr[:500]}")
            except subprocess.TimeoutExpired:
                logger.info("Server is running (timeout on communicate)")
                
            # Keep process running for testing
            logger.info("Server is running. You can now test OmniParser functionality.")
            logger.info("Process will be terminated in background mode.")
            return True
            
        else:
            logger.error(f"✗ Server process terminated with code: {process.returncode}")
            stdout, stderr = process.communicate()
            if stdout:
                logger.error(f"Stdout: {stdout}")
            if stderr:
                logger.error(f"Stderr: {stderr}")
            return False
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("🔍 DIRECT OMNIPARSER SERVER START")
    logger.info("=" * 80)
    
    success = direct_omniparser_test()
    
    if success:
        logger.info("=" * 80)
        logger.info("✅ DIRECT OMNIPARSER SERVER START COMPLETED!")
        logger.info("=" * 80)
    else:
        logger.info("=" * 80)
        logger.info("❌ DIRECT OMNIPARSER SERVER START FAILED!")
        logger.info("=" * 80)
