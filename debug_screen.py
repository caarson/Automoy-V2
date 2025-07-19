#!/usr/bin/env python3
"""
Debug what OmniParser currently sees on screen
"""

import os
import sys
import tempfile
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def debug_screen_content():
    """Debug what's currently visible on screen"""
    
    print("🔍 Debug Screen Content")
    print("=" * 40)
    
    try:
        # Import components
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.screenshot_utils import capture_screen_pil
        
        # Get OmniParser
        omniparser_manager = OmniParserServerManager()
        if not omniparser_manager.is_server_ready():
            print("❌ OmniParser not ready")
            return
        
        omniparser = omniparser_manager.get_interface()
        
        # Take screenshot
        screenshot = capture_screen_pil()
        if not screenshot:
            print("❌ Screenshot failed")
            return
        
        print(f"✅ Screenshot captured: {screenshot.size}")
        
        # Save a copy for manual inspection
        screenshot.save("debug_screenshot.png")
        print("📸 Screenshot saved as debug_screenshot.png")
        
        # Process with OmniParser
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
            screenshot.save(temp_path)
        
        try:
            parsed_result = omniparser.parse_screenshot(temp_path)
            if not parsed_result:
                print("❌ OmniParser failed")
                return
            
            elements = parsed_result.get("parsed_content_list", [])
            print(f"✅ Found {len(elements)} total elements")
            
            # Look for Chrome-related elements
            chrome_elements = []
            interactive_elements = []
            
            for element in elements:
                content = element.get("content", "").lower()
                is_interactive = element.get("interactivity", False)
                elem_type = element.get("type", "")
                
                if is_interactive:
                    interactive_elements.append(element)
                
                # Check for Chrome-related content
                if any(keyword in content for keyword in ["chrome", "google", "browser"]):
                    chrome_elements.append(element)
            
            print(f"🔍 Interactive elements: {len(interactive_elements)}")
            print(f"🔍 Chrome-related elements: {len(chrome_elements)}")
            
            if chrome_elements:
                print("\n🎯 Chrome-related elements found:")
                for i, element in enumerate(chrome_elements):
                    content = element.get("content", "")[:50]
                    elem_type = element.get("type", "")
                    interactive = element.get("interactivity", False)
                    print(f"  {i+1}. '{content}' (type: {elem_type}, interactive: {interactive})")
            else:
                print("\n❌ No Chrome-related elements found")
                print("\n📋 Sample interactive elements:")
                for i, element in enumerate(interactive_elements[:15]):
                    content = element.get("content", "")[:40]
                    elem_type = element.get("type", "")
                    print(f"  {i+1}. '{content}' (type: {elem_type})")
                
                print(f"\n📋 All element types present:")
                types = {}
                for element in elements:
                    elem_type = element.get("type", "unknown")
                    types[elem_type] = types.get(elem_type, 0) + 1
                
                for elem_type, count in sorted(types.items()):
                    print(f"  {elem_type}: {count}")
        
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_screen_content()
