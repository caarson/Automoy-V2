#!/usr/bin/env python3
"""
Direct test bypassing goal files to test visual analysis in isolation
"""
import sys
import os
import asyncio
import logging
import json

# Add project root to path  
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_visual_analysis():
    """Test visual analysis components directly"""
    try:
        # Import required modules
        from core.operate import AutomoyOperator
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.lm.lm_interface import MainInterface

        logger.info("🧪 Starting direct visual analysis component test...")
        
        # Initialize OmniParser
        logger.info("🔌 Initializing OmniParser...")
        omniparser_manager = OmniParserServerManager()
        omniparser = omniparser_manager.get_interface()
        if not omniparser:
            logger.error("❌ Failed to get OmniParser interface")
            return
        logger.info("✅ OmniParser initialized")
        
        # Create AutomoyOperator with minimal dependencies
        logger.info("🔧 Creating AutomoyOperator...")
        lm_interface = MainInterface(api_source="lmstudio")
        
        # Create dummy functions for dependencies
        def dummy_gui_manager(window_state):
            logger.info(f"GUI manager called with: {window_state}")
        
        async def dummy_state_updater(endpoint, data):
            logger.info(f"State updater called: {endpoint} -> {data}")
        
        def dummy_desktop_utils():
            logger.info("Desktop utils called")
        
        # Create operator
        operator = AutomoyOperator(lm_interface)
        operator.set_omniparser(omniparser)
        operator.set_manage_gui_window_func(dummy_gui_manager)
        operator.set_update_gui_state_func(dummy_state_updater)
        
        logger.info("✅ AutomoyOperator created")
        
        # Test visual analysis directly
        logger.info("🔍 Calling _perform_visual_analysis directly...")
        screenshot_info, analysis_result = await operator._perform_visual_analysis()
        
        logger.info(f"📊 Screenshot info: {screenshot_info}")
        logger.info(f"📊 Analysis result: {analysis_result}")
        
        # Test format_visual_analysis_result  
        if screenshot_info:
            logger.info("🔧 Testing _format_visual_analysis_result...")
            formatted_result = operator._format_visual_analysis_result(screenshot_info)
            logger.info(f"📋 Formatted result: {formatted_result}")
        
    except Exception as e:
        logger.error(f"💥 Error in visual analysis test: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_visual_analysis())
