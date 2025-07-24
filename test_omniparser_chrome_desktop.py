#!/usr/bin/env python3
"""
Test OmniParser visual analysis to detect Chrome on desktop
This test will:
1. Start OmniParser server if needed
2. Take a screenshot of the desktop
3. Analyze it for Chrome icons/elements
4. Report what it finds
"""

import sys
import os
import time
import logging

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_omniparser_chrome_detection():
    """Test OmniParser's ability to detect Chrome on desktop"""
    logger.info("=== OMNIPARSER CHROME DESKTOP TEST ===")
    
    try:
        # Import OmniParser components
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        logger.info("✓ Successfully imported OmniParserServerManager")
        
        # Initialize OmniParser manager
        omniparser_manager = OmniParserServerManager()
        logger.info("✓ OmniParserServerManager initialized")
        
        # Check if server is already running
        if omniparser_manager.is_server_ready():
            logger.info("✓ OmniParser server is already running")
            omniparser = omniparser_manager.get_interface()
        else:
            logger.info("⚠ OmniParser server not running, attempting to start...")
            
            # Start the server
            server_process = omniparser_manager.start_server()
            if server_process:
                logger.info(f"✓ OmniParser server process started (PID: {server_process.pid})")
                
                # Wait for server to become ready
                if omniparser_manager.wait_for_server(timeout=60):
                    logger.info("✓ OmniParser server is now ready")
                    omniparser = omniparser_manager.get_interface()
                else:
                    logger.error("✗ OmniParser server failed to become ready within timeout")
                    return False
            else:
                logger.error("✗ Failed to start OmniParser server")
                return False
        
        # Test the interface
        if omniparser:
            logger.info("✓ OmniParser interface obtained successfully")
            logger.info(f"Interface type: {type(omniparser)}")
            
            # Test server connectivity
            try:
                if hasattr(omniparser, 'is_server_ready'):
                    ready = omniparser.is_server_ready()
                    logger.info(f"Server ready status: {ready}")
                elif hasattr(omniparser, 'test_connection'):
                    connection_ok = omniparser.test_connection()
                    logger.info(f"Connection test: {connection_ok}")
                else:
                    logger.info("No direct connectivity test available")
            except Exception as conn_err:
                logger.warning(f"Connection test failed: {conn_err}")
            
            # Now test desktop screenshot and analysis
            logger.info("\n=== DESKTOP ANALYSIS TEST ===")
            
            try:
                # Take screenshot and analyze
                logger.info("Taking desktop screenshot and analyzing...")
                
                # Method 1: Try direct parse method if available
                if hasattr(omniparser, 'parse'):
                    logger.info("Using direct parse method...")
                    result = omniparser.parse()
                    logger.info(f"Parse result type: {type(result)}")
                    logger.info(f"Parse result: {result}")
                
                # Method 2: Try parse_screen if available  
                elif hasattr(omniparser, 'parse_screen'):
                    logger.info("Using parse_screen method...")
                    result = omniparser.parse_screen()
                    logger.info(f"Parse screen result type: {type(result)}")
                    logger.info(f"Parse screen result: {result}")
                
                # Method 3: Try analyze_screen if available
                elif hasattr(omniparser, 'analyze_screen'):
                    logger.info("Using analyze_screen method...")
                    result = omniparser.analyze_screen()
                    logger.info(f"Analyze screen result type: {type(result)}")
                    logger.info(f"Analyze screen result: {result}")
                
                else:
                    logger.error("No known analysis methods found on omniparser interface")
                    # List available methods
                    methods = [method for method in dir(omniparser) if not method.startswith('_')]
                    logger.info(f"Available methods: {methods}")
                    return False
                
                # Analyze the results for Chrome
                logger.info("\n=== CHROME DETECTION ANALYSIS ===")
                
                if isinstance(result, dict):
                    # Check elements
                    elements = result.get('elements', [])
                    logger.info(f"Found {len(elements)} UI elements")
                    
                    chrome_elements = []
                    for i, element in enumerate(elements):
                        element_text = str(element).lower()
                        if 'chrome' in element_text:
                            chrome_elements.append((i, element))
                            logger.info(f"🔍 CHROME FOUND in element {i}: {element}")
                    
                    # Check text snippets
                    text_snippets = result.get('text_snippets', [])
                    logger.info(f"Found {len(text_snippets)} text snippets")
                    
                    chrome_text = []
                    for i, text in enumerate(text_snippets):
                        text_str = str(text).lower()
                        if 'chrome' in text_str:
                            chrome_text.append((i, text))
                            logger.info(f"🔍 CHROME FOUND in text {i}: {text}")
                    
                    # Summary
                    if chrome_elements or chrome_text:
                        logger.info(f"✅ SUCCESS: Chrome detected!")
                        logger.info(f"Chrome elements: {len(chrome_elements)}")
                        logger.info(f"Chrome text mentions: {len(chrome_text)}")
                        
                        # Show coordinates if available
                        for idx, element in chrome_elements:
                            if isinstance(element, dict) and 'coordinate' in element:
                                coords = element['coordinate']
                                logger.info(f"Chrome element {idx} coordinates: {coords}")
                            elif isinstance(element, dict) and 'ClickCoordinates' in element:
                                coords = element['ClickCoordinates']
                                logger.info(f"Chrome element {idx} click coordinates: {coords}")
                    else:
                        logger.warning("⚠ Chrome NOT detected in visual analysis")
                        logger.info("This could mean:")
                        logger.info("- Chrome icon is not visible on current desktop")
                        logger.info("- Chrome icon is in taskbar/start menu (not desktop)")
                        logger.info("- OmniParser is not recognizing Chrome icon properly")
                        
                        # Show what WAS detected for debugging
                        if elements:
                            logger.info("Elements that WERE detected:")
                            for i, elem in enumerate(elements[:5]):  # Show first 5
                                logger.info(f"  Element {i}: {elem}")
                        
                        if text_snippets:
                            logger.info("Text snippets that WERE detected:")
                            for i, text in enumerate(text_snippets[:5]):  # Show first 5
                                logger.info(f"  Text {i}: {text}")
                
                elif result:
                    # Non-dict result
                    result_str = str(result).lower()
                    if 'chrome' in result_str:
                        logger.info("✅ Chrome detected in analysis result")
                    else:
                        logger.warning("⚠ Chrome NOT detected")
                    logger.info(f"Full result: {result}")
                    
                else:
                    logger.error("✗ No result returned from analysis")
                    return False
                    
            except Exception as analysis_err:
                logger.error(f"✗ Desktop analysis failed: {analysis_err}")
                import traceback
                traceback.print_exc()
                return False
        
        else:
            logger.error("✗ Failed to obtain OmniParser interface")
            return False
            
        logger.info("\n=== TEST COMPLETED ===")
        return True
        
    except ImportError as e:
        logger.error(f"✗ Import error: {e}")
        logger.error("Make sure OmniParser dependencies are installed")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting OmniParser Chrome Desktop Detection Test...")
    success = test_omniparser_chrome_detection()
    
    if success:
        print("\n✅ Test completed successfully")
    else:
        print("\n❌ Test failed")
        sys.exit(1)
