#!/usr/bin/env python3
"""
Direct element detection test to bypass file reading issues
"""
import sys
import os
import asyncio
import logging

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("direct_test")

async def test_visual_analysis_with_operator():
    """Test visual analysis directly through operator"""
    
    logger.info("🔍 DIRECT VISUAL ANALYSIS TEST")
    logger.info("=" * 60)
    
    try:
        # Import what we need
        from core.operate import AutomoyOperator
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        
        # Initialize OmniParser
        logger.info("1. Setting up OmniParser...")
        omniparser_manager = OmniParserServerManager()
        omniparser = omniparser_manager.get_interface()
        
        # Create operator
        logger.info("2. Creating AutomoyOperator...")
        
        async def dummy_gui_update(endpoint, payload):
            logger.info(f"GUI Update: {endpoint} -> {payload}")
        
        async def dummy_gui_window_func(action):
            logger.info(f"GUI Window: {action}")
            return True
        
        pause_event = asyncio.Event()
        pause_event.set()
        
        operator = AutomoyOperator(
            objective="Test visual analysis",
            manage_gui_window_func=dummy_gui_window_func,
            omniparser=omniparser,
            pause_event=pause_event,
            update_gui_state_func=dummy_gui_update
        )
        
        logger.info("3. Testing visual analysis...")
        
        # Try to call the visual analysis method directly
        if hasattr(operator, 'perform_visual_analysis'):
            logger.info("Calling perform_visual_analysis...")
            screenshot_path, visual_output = await operator.perform_visual_analysis()
            
            logger.info("=" * 60)
            logger.info("📸 SCREENSHOT PATH:")
            logger.info(f"{screenshot_path}")
            logger.info("=" * 60)
            logger.info("👁️ VISUAL OUTPUT:")
            logger.info(f"{visual_output[:2000]}...")  # First 2000 chars
            logger.info("=" * 60)
            
            # Search for "element" in the output
            if "element" in visual_output.lower():
                element_count = visual_output.lower().count("element")
                logger.info(f"✅ Found {element_count} element references in visual analysis!")
            else:
                logger.warning("❌ No 'element' references found in visual analysis output")
                
            # Check for coordinates
            if "ClickCoordinates" in visual_output:
                coord_count = visual_output.count("ClickCoordinates")
                logger.info(f"✅ Found {coord_count} ClickCoordinates in visual analysis!")
            else:
                logger.warning("❌ No 'ClickCoordinates' found in visual analysis output")
        
        else:
            logger.error("❌ perform_visual_analysis method not found on operator")
            
    except Exception as e:
        logger.error(f"❌ Error in direct test: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_visual_analysis_with_operator())
