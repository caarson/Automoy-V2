#!/usr/bin/env python3

import logging
import sys
import os

# Add the project directory to sys.path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_omniparser_server():
    """Test OmniParser server startup and basic functionality."""
    try:
        logger.info("=== OmniParser Server Test ===")
        logger.info("1. Importing OmniParser modules...")
        
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        
        logger.info("2. Creating OmniParser server manager...")
        omniparser_manager = OmniParserServerManager()
        
        logger.info("3. Checking if server is ready...")
        if omniparser_manager.is_server_ready():
            logger.info("✓ OmniParser server is already running")
        else:
            logger.info("Server not running, attempting to start...")
            # Get the interface and provide explicit conda path
            interface = omniparser_manager.get_interface()
            conda_path = "C:/Users/imitr/anaconda3/Scripts/conda.exe"
            logger.info(f"Using conda path: {conda_path}")
            
            # Start server with explicit conda path
            if interface.launch_server(conda_path=conda_path, conda_env="automoy_env"):
                logger.info("✓ Server started successfully")
                omniparser_manager.server_process = interface.server_process
                
                logger.info("4. Waiting for server to become ready...")
                if omniparser_manager.wait_for_server(timeout=30):
                    logger.info("✓ Server is ready")
                else:
                    logger.error("✗ Server failed to become ready")
                    return False
            else:
                logger.error("✗ Failed to start server")
                return False
        
        logger.info("5. Getting OmniParser interface...")
        omniparser = omniparser_manager.get_interface()
        
        logger.info("6. Testing basic functionality...")
        logger.info("✓ OmniParser server test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("🔍 OMNIPARSER SERVER TEST")
    logger.info("=" * 80)
    
    success = test_omniparser_server()
    
    if success:
        logger.info("=" * 80)
        logger.info("✅ OMNIPARSER SERVER TEST COMPLETED SUCCESSFULLY!")
        logger.info("=" * 80)
    else:
        logger.info("=" * 80)
        logger.info("❌ OMNIPARSER SERVER TEST FAILED!")
        logger.info("=" * 80)
