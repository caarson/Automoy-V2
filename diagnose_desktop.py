#!/usr/bin/env python3
"""
Desktop diagnostic - see what's actually on the desktop
"""

import os
import sys
import time
import tempfile
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def diagnose_desktop():
    """Diagnose what's on the desktop"""
    
    print("🔍 Desktop Diagnostic")
    print("=" * 50)
    
    try:
        # Import components
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.screenshot_utils import capture_screen_pil
        import pyautogui
        
        # Go to desktop
        print("1. Going to desktop...")
        pyautogui.hotkey('win', 'd')
        time.sleep(3)  # Give more time for desktop to show
        
        # Take screenshot
        print("2. Taking desktop screenshot...")
        screenshot = capture_screen_pil()
        screenshot.save("current_desktop.png")
        print("   📸 Desktop saved as current_desktop.png")
        
        # Process with OmniParser
        print("3. Analyzing desktop with OmniParser...")
        omniparser_manager = OmniParserServerManager()
        omniparser = omniparser_manager.get_interface()
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
            screenshot.save(temp_path)
        
        try:
            parsed_result = omniparser.parse_screenshot(temp_path)
            elements = parsed_result.get("parsed_content_list", [])
            print(f"   📊 Found {len(elements)} elements on desktop")
            
            # Categorize elements
            icons = [e for e in elements if e.get("type", "").lower() == "icon"]
            interactive = [e for e in elements if e.get("interactivity", False)]
            text_elements = [e for e in elements if e.get("type", "").lower() == "text"]
            
            print(f"   🎯 Icons: {len(icons)}")
            print(f"   🖱️  Interactive: {len(interactive)}")
            print(f"   📝 Text: {len(text_elements)}")
            
            # Look for Google/Chrome specifically
            print("\n4. Searching for Google/Chrome elements...")
            chrome_related = []
            for element in elements:
                content = element.get("content", "").lower()
                if any(keyword in content for keyword in ["google", "chrome", "browser"]):
                    chrome_related.append(element)
            
            if chrome_related:
                print(f"   🎯 Found {len(chrome_related)} Chrome/Google related elements:")
                for i, element in enumerate(chrome_related):
                    content = element.get("content", "")[:60]
                    elem_type = element.get("type", "")
                    interactive = element.get("interactivity", False)
                    bbox = element.get("bbox_normalized", [])
                    print(f"     {i+1}. '{content}' (type: {elem_type}, interactive: {interactive}, bbox: {bbox})")
            else:
                print("   ❌ No Chrome/Google elements found")
            
            # Show all icons
            print("\n5. All desktop icons found:")
            for i, icon in enumerate(icons[:15]):
                content = icon.get("content", "")[:40]
                interactive = icon.get("interactivity", False)
                print(f"   {i+1}. '{content}' (interactive: {interactive})")
            
            # Show all interactive elements
            print("\n6. All interactive elements:")
            for i, element in enumerate(interactive[:15]):
                content = element.get("content", "")[:40]
                elem_type = element.get("type", "")
                print(f"   {i+1}. '{content}' (type: {elem_type})")
            
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
    diagnose_desktop()
