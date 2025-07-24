#!/usr/bin/env python3
"""
Simple Chrome Desktop Detection Test for OmniParser
"""

print("=== STARTING OMNIPARSER CHROME TEST ===")

import sys
import os

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print(f"Project root: {project_root}")
print("Python path updated")

try:
    print("Importing OmniParser components...")
    from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
    print("✓ OmniParserServerManager imported successfully")
    
    print("Creating OmniParser manager...")
    omniparser_manager = OmniParserServerManager()
    print("✓ OmniParserServerManager created")
    
    print("Checking if OmniParser server is ready...")
    if omniparser_manager.is_server_ready():
        print("✓ OmniParser server is already running")
        omniparser = omniparser_manager.get_interface()
        print(f"✓ Interface obtained: {type(omniparser)}")
        
        print("\n=== TESTING DESKTOP ANALYSIS ===")
        
        # Try to get available methods
        methods = [method for method in dir(omniparser) if not method.startswith('_')]
        print(f"Available methods: {methods}")
        
        # Try different analysis methods
        result = None
        
        if hasattr(omniparser, 'parse'):
            print("Trying parse() method...")
            try:
                result = omniparser.parse()
                print(f"Parse result type: {type(result)}")
                print(f"Parse result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
            except Exception as e:
                print(f"Parse failed: {e}")
        
        if hasattr(omniparser, 'parse_screen'):
            print("Trying parse_screen() method...")
            try:
                result = omniparser.parse_screen()
                print(f"Parse screen result type: {type(result)}")
                print(f"Parse screen result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
            except Exception as e:
                print(f"Parse screen failed: {e}")
        
        if result:
            print("\n=== ANALYZING RESULTS FOR CHROME ===")
            if isinstance(result, dict):
                elements = result.get('elements', [])
                text_snippets = result.get('text_snippets', [])
                
                print(f"Elements found: {len(elements)}")
                print(f"Text snippets found: {len(text_snippets)}")
                
                # Look for Chrome
                chrome_found = False
                
                for i, element in enumerate(elements):
                    element_str = str(element).lower()
                    if 'chrome' in element_str:
                        print(f"🎯 CHROME FOUND in element {i}: {element}")
                        chrome_found = True
                
                for i, text in enumerate(text_snippets):
                    text_str = str(text).lower()
                    if 'chrome' in text_str:
                        print(f"🎯 CHROME FOUND in text {i}: {text}")
                        chrome_found = True
                
                if not chrome_found:
                    print("❌ Chrome NOT detected")
                    print("First few elements detected:")
                    for i, elem in enumerate(elements[:3]):
                        print(f"  Element {i}: {elem}")
                    print("First few text snippets detected:")
                    for i, text in enumerate(text_snippets[:3]):
                        print(f"  Text {i}: {text}")
                else:
                    print("✅ Chrome detected successfully!")
            else:
                print(f"Non-dict result: {result}")
        else:
            print("❌ No results from analysis")
        
    else:
        print("❌ OmniParser server is not running")
        print("Attempting to start server...")
        
        server_process = omniparser_manager.start_server()
        if server_process:
            print(f"✓ Server process started (PID: {server_process.pid})")
            
            print("Waiting for server to become ready...")
            if omniparser_manager.wait_for_server(timeout=30):
                print("✓ Server is now ready!")
                
                omniparser = omniparser_manager.get_interface()
                print("✓ Interface obtained")
                
                # Now try the analysis
                if hasattr(omniparser, 'parse'):
                    result = omniparser.parse()
                    print(f"Analysis result: {result}")
                    
                    if isinstance(result, dict):
                        elements = result.get('elements', [])
                        print(f"Found {len(elements)} elements")
                        
                        for i, element in enumerate(elements):
                            if 'chrome' in str(element).lower():
                                print(f"🎯 Chrome found: {element}")
            else:
                print("❌ Server failed to become ready")
        else:
            print("❌ Failed to start server")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== TEST COMPLETED ===")
