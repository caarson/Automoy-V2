#!/usr/bin/env python3
import sys
import os
import logging
import tempfile

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("omni_debug")

def debug_omniparser():
    try:
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.screenshot_utils import capture_screen_pil
        
        logger.info("🔍 Testing OmniParser...")
        
        # Get OmniParser
        manager = OmniParserServerManager()
        omniparser = manager.get_interface()
        
        # Take screenshot
        screenshot = capture_screen_pil()
        if not screenshot:
            logger.error("❌ Screenshot failed")
            return
            
        # Save screenshot
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
            screenshot.save(temp_path)
            logger.info(f"✅ Screenshot saved: {temp_path}")
        
        # Parse with OmniParser
        logger.info("📊 Parsing with OmniParser...")
        result = omniparser.parse_screenshot(temp_path)
        
        logger.info("=" * 60)
        logger.info("🔍 OMNIPARSER RESULT ANALYSIS:")
        logger.info(f"Type: {type(result)}")
        logger.info(f"Is None: {result is None}")
        logger.info(f"Is truthy: {bool(result)}")
        
        if result:
            if isinstance(result, dict):
                logger.info(f"Keys: {list(result.keys())}")
                
                if "parsed_content_list" in result:
                    elements = result["parsed_content_list"]
                    logger.info(f"Elements found: {len(elements) if elements else 0}")
                    
                    if elements:
                        logger.info("✅ FOUND ELEMENTS!")
                        for i, elem in enumerate(elements[:5]):
                            text = elem.get("content", "")
                            elem_type = elem.get("type", "unknown")
                            bbox = elem.get("bbox_normalized", [])
                            logger.info(f"  [{i+1}] '{text}' | {elem_type} | {bbox}")
                    else:
                        logger.warning("❌ Element list is empty")
                else:
                    logger.warning("❌ No 'parsed_content_list' key")
            else:
                logger.warning(f"❌ Result is not dict: {result}")
        else:
            logger.error("❌ OmniParser returned None/empty")
        
        # Cleanup
        os.unlink(temp_path)
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)

if __name__ == "__main__":
    debug_omniparser()
