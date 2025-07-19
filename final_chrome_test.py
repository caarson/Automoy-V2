#!/usr/bin/env python3
"""
Final Chrome test using the exact logic from operate.py
"""

import os
import sys
import time
import subprocess
import tempfile
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def final_chrome_test():
    """Final test using exact Chrome detection logic from operate.py"""
    
    print("🎯 Final Chrome Test - Using Exact operate.py Logic")
    print("=" * 60)
    
    try:
        # Step 1: Close Chrome
        print("1. Ensuring Chrome is closed...")
        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                      capture_output=True, text=True)
        time.sleep(1)
        
        result = subprocess.run(['powershell', '-Command', 'Get-Process chrome -ErrorAction SilentlyContinue'],
                              capture_output=True, text=True)
        if result.stdout.strip():
            print("   ⚠️  Some Chrome processes still running, trying again...")
            subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                          capture_output=True, text=True)
            time.sleep(2)
        print("   ✅ Chrome cleanup complete")
        
        # Step 2: Import components and configure
        print("2. Importing components and configuring for clicking only...")
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.screenshot_utils import capture_screen_pil
        import pyautogui
        
        # Configure pyautogui to be more reliable for clicking
        pyautogui.FAILSAFE = False  # Disable failsafe to prevent interruption
        pyautogui.PAUSE = 0.1  # Small pause between actions
        print("   ✅ All components imported and configured for mouse clicking")
        
        # Step 3: Get OmniParser
        print("3. Initializing OmniParser...")
        omniparser_manager = OmniParserServerManager()
        if omniparser_manager.is_server_ready():
            omniparser = omniparser_manager.get_interface()
            print("   ✅ OmniParser ready")
        else:
            print("   ❌ OmniParser not available")
            return False
        
        # Step 4: Go to desktop FIRST for screenshot
        print("4. Going to desktop and taking screenshot...")
        pyautogui.hotkey('win', 'd')  # Show desktop to see Chrome icon
        time.sleep(2)  # Wait for desktop to be visible
        
        screenshot = capture_screen_pil()
        if not screenshot:
            print("   ❌ Screenshot failed")
            return False
        print(f"   ✅ Desktop screenshot captured: {screenshot.size}")
        
        # Save desktop screenshot for verification
        screenshot.save("desktop_analysis.png")
        print("   📸 Desktop screenshot saved as desktop_analysis.png")
        
        # Step 5: OmniParser processing (exact logic from operate.py)
        print("5. Processing with OmniParser...")
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
            screenshot.save(temp_path)
        
        try:
            parsed_result = omniparser.parse_screenshot(temp_path)
            if not parsed_result or "parsed_content_list" not in parsed_result:
                print("   ❌ OmniParser failed to parse")
                return False
            
            elements = parsed_result.get("parsed_content_list", [])
            print(f"   ✅ OmniParser found {len(elements)} elements")
            
            # Step 6: Chrome detection (EXACT logic from operate.py)
            print("6. Chrome detection using operate.py logic...")
            screen_width, screen_height = pyautogui.size()
            chrome_candidates = []
            
            print("   🔍 Searching for Chrome icons on desktop...")
            for element in elements:
                element_text = element.get("content", "").lower()
                element_type = element.get("type", "").lower()
                bbox = element.get("bbox_normalized", [])
                interactive = element.get("interactivity", False)
                
                # Enhanced Chrome detection for desktop icons
                is_chrome = (
                    "chrome" in element_text or
                    "google chrome" in element_text or
                    "google" in element_text or
                    ("browser" in element_text) or
                    (element_type == "icon" and interactive and "google" in element_text) or
                    (element_type == "icon" and "chrome" in element_text)
                )
                
                if is_chrome and bbox and not all(x == 0 for x in bbox):
                    x1, y1, x2, y2 = bbox
                    center_x = int((x1 + x2) / 2 * screen_width)
                    center_y = int((y1 + y2) / 2 * screen_height)
                    
                    chrome_candidates.append({
                        'text': element_text,
                        'coordinates': (center_x, center_y),
                        'confidence': 1.0 if "chrome" in element_text else 0.8,
                        'type': element_type,
                        'interactive': interactive
                    })
                    print(f"   🎯 Chrome candidate: '{element_text}' at ({center_x}, {center_y}) [type: {element_type}]")
            
            if chrome_candidates:
                # Sort by confidence (highest first)
                chrome_candidates.sort(key=lambda x: x['confidence'], reverse=True)
                
                print(f"   🎯 Found {len(chrome_candidates)} Chrome candidates:")
                for i, candidate in enumerate(chrome_candidates):
                    print(f"     {i+1}. '{candidate['text']}' at {candidate['coordinates']} (type: {candidate['type']}, interactive: {candidate['interactive']})")
                
                # Step 7: Click best Chrome candidate (ACTUAL CLICKING)
                best_candidate = chrome_candidates[0]
                coords = best_candidate['coordinates']
                print(f"7. CLICKING Chrome icon at {coords} (NOT using keyboard shortcuts)...")
                print(f"   Target: '{best_candidate['text']}' of type '{best_candidate['type']}'")
                
                # Ensure we're clicking, not using keyboard shortcuts
                print("   🖱️  Performing MOUSE CLICK (no keyboard shortcuts)...")
                pyautogui.click(coords[0], coords[1])
                print("   ✅ Mouse click executed on Chrome icon")
                
                # Step 8: Wait and verify Chrome launch
                print("8. Verifying Chrome launch...")
                
                for attempt in range(5):
                    time.sleep(1)
                    result = subprocess.run(
                        ['powershell', '-Command', 'Get-Process chrome -ErrorAction SilentlyContinue'],
                        capture_output=True, text=True
                    )
                    
                    if result.stdout.strip():
                        print(f"   🎉 SUCCESS! Chrome detected after {attempt + 1} seconds!")
                        
                        # Count and display Chrome processes
                        lines = [line for line in result.stdout.strip().split('\n') if 'chrome' in line.lower()]
                        print(f"   📊 Chrome processes running: {len(lines)}")
                        
                        # Show sample processes
                        print("   Sample Chrome processes:")
                        for line in lines[:3]:
                            if line.strip():
                                print(f"     {line.strip()}")
                        
                        return True
                    
                    print(f"   ⏳ Attempt {attempt + 1}/5 - Chrome not yet detected...")
                
                print("   ❌ Chrome did not launch within 5 seconds")
                return False
                
            else:
                print("   ❌ No Chrome candidates found on desktop")
                print("   🔍 Debugging: Available desktop elements:")
                interactive_elements = [e for e in elements if e.get("interactivity", False)]
                desktop_icons = [e for e in elements if e.get("type", "").lower() == "icon"]
                
                print(f"     Total elements: {len(elements)}")
                print(f"     Interactive elements: {len(interactive_elements)}")
                print(f"     Desktop icons: {len(desktop_icons)}")
                
                print("   📋 Desktop icons found:")
                for i, element in enumerate(desktop_icons[:10]):
                    content = element.get("content", "")[:40]
                    interactive = element.get("interactivity", False)
                    print(f"     {i+1}. '{content}' (interactive: {interactive})")
                
                print("   🔍 Searching for any text containing 'google' or 'chrome'...")
                google_elements = []
                for element in elements:
                    content = element.get("content", "").lower()
                    if "google" in content or "chrome" in content:
                        google_elements.append(element)
                
                if google_elements:
                    print(f"   Found {len(google_elements)} elements with 'google' or 'chrome':")
                    for i, element in enumerate(google_elements):
                        content = element.get("content", "")[:50]
                        elem_type = element.get("type", "")
                        interactive = element.get("interactivity", False)
                        print(f"     {i+1}. '{content}' (type: {elem_type}, interactive: {interactive})")
                
                return False
                
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Final Chrome Test - Testing the complete Automoy workflow")
    print("This uses the exact same logic as operate.py for Chrome detection\n")
    
    success = final_chrome_test()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ FINAL TEST PASSED!")
        print("✅ Automoy Chrome detection and clicking works correctly!")
        print("✅ Chrome successfully launched and verified via terminal!")
    else:
        print("❌ FINAL TEST FAILED!")
        print("❌ Chrome detection or launching failed")
    print("=" * 60)
