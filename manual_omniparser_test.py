#!/usr/bin/env python3
"""
Manual OmniParser Chrome search - takes screenshot and searches ALL elements
"""

import os
import sys
import time
import subprocess
import tempfile
import json
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def manual_omniparser_chrome_search():
    """Use OmniParser to take screenshot and manually search for Chrome in ALL elements"""
    
    print("🔍 Manual OmniParser Chrome Search")
    print("=" * 60)
    
    try:
        # Step 1: Close Chrome first to ensure clean test
        print("1. Ensuring Chrome is closed...")
        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                      capture_output=True, text=True)
        time.sleep(1)
        
        # Step 2: Go to desktop to ensure Chrome icon is visible
        print("2. Going to desktop...")
        import pyautogui
        pyautogui.hotkey('win', 'd')
        time.sleep(3)
        
        # Step 3: Initialize OmniParser
        print("3. Initializing OmniParser...")
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        omniparser_manager = OmniParserServerManager()
        
        if not omniparser_manager.is_server_ready():
            print("   Starting OmniParser server...")
            server_process = omniparser_manager.start_server()
            if not omniparser_manager.wait_for_server(timeout=30):
                print("   ❌ OmniParser server failed to start")
                return
        
        omniparser = omniparser_manager.get_interface()
        print("   ✅ OmniParser initialized successfully")
        
        # Step 4: Take screenshot and save it
        print("4. Taking screenshot...")
        screenshot = pyautogui.screenshot()
        screenshot_path = "manual_chrome_search_screenshot.png"
        screenshot.save(screenshot_path)
        print(f"   ✅ Screenshot saved as: {screenshot_path}")
        
        # Step 5: Use OmniParser to analyze the screenshot
        print("5. Running OmniParser analysis...")
        try:
            parsed_result = omniparser.parse_screenshot(screenshot_path)
            
            if not parsed_result:
                print("   ❌ OmniParser returned no results")
                return
                
            elements = parsed_result.get("parsed_content_list", [])
            print(f"   ✅ OmniParser found {len(elements)} total elements")
            
            # Step 6: Manual search through ALL elements for Chrome-related content
            print("\n6. Searching ALL elements for Chrome-related content...")
            print("=" * 60)
            
            chrome_candidates = []
            interactive_elements = []
            all_text_elements = []
            
            for i, element in enumerate(elements):
                # Collect all text for analysis
                element_text = str(element.get("content", "")).lower()
                element_type = str(element.get("type", "")).lower()
                bbox = element.get("bbox_normalized", [])
                interactive = element.get("interactivity", False)
                
                all_text_elements.append({
                    "index": i,
                    "text": element_text,
                    "type": element_type,
                    "bbox": bbox,
                    "interactive": interactive,
                    "full_element": element
                })
                
                # Check if element is interactive
                if interactive or "icon" in element_type or "button" in element_type:
                    interactive_elements.append({
                        "index": i,
                        "text": element_text,
                        "type": element_type,
                        "bbox": bbox,
                        "interactive": interactive
                    })
                
                # Search for Chrome-related keywords
                chrome_keywords = [
                    "chrome", "google chrome", "google", "browser", 
                    "web browser", "internet", "chromium"
                ]
                
                for keyword in chrome_keywords:
                    if keyword in element_text:
                        chrome_candidates.append({
                            "index": i,
                            "text": element_text,
                            "type": element_type,
                            "bbox": bbox,
                            "matched_keyword": keyword,
                            "interactive": interactive,
                            "full_element": element
                        })
                        break
            
            print(f"\n📊 ANALYSIS RESULTS:")
            print(f"   Total elements found: {len(elements)}")
            print(f"   Interactive elements: {len(interactive_elements)}")
            print(f"   Chrome candidates found: {len(chrome_candidates)}")
            
            # Step 7: Display Chrome candidates
            if chrome_candidates:
                print(f"\n🎯 CHROME CANDIDATES FOUND ({len(chrome_candidates)}):")
                print("=" * 60)
                for candidate in chrome_candidates:
                    print(f"Index {candidate['index']}:")
                    print(f"   Text: '{candidate['text']}'")
                    print(f"   Type: '{candidate['type']}'")
                    print(f"   Bbox: {candidate['bbox']}")
                    print(f"   Matched Keyword: '{candidate['matched_keyword']}'")
                    print(f"   Interactive: {candidate['interactive']}")
                    print(f"   Full Element: {candidate['full_element']}")
                    print()
            else:
                print("\n❌ NO CHROME CANDIDATES FOUND")
            
            # Step 8: Display some interactive elements for context
            print(f"\n📱 SAMPLE INTERACTIVE ELEMENTS ({min(10, len(interactive_elements))}):")
            print("=" * 60)
            for i, element in enumerate(interactive_elements[:10]):
                print(f"Index {element['index']}: '{element['text']}' (Type: {element['type']}, Interactive: {element['interactive']})")
            
            # Step 9: Search for any text containing common desktop icons
            print(f"\n🏠 DESKTOP ICON ANALYSIS:")
            print("=" * 60)
            common_desktop_items = [
                "recycle", "bin", "this pc", "computer", "file", "folder", 
                "desktop", "shortcut", "exe", "app", "application"
            ]
            
            desktop_items = []
            for element in all_text_elements:
                for item in common_desktop_items:
                    if item in element["text"]:
                        desktop_items.append(element)
                        break
            
            print(f"Found {len(desktop_items)} desktop-related elements:")
            for item in desktop_items[:10]:  # Show first 10
                print(f"   '{item['text']}' (Type: {item['type']}, Interactive: {item['interactive']})")
            
            # Step 10: Save detailed results to file
            results_file = "omniparser_chrome_search_results.json"
            results_data = {
                "total_elements": len(elements),
                "interactive_elements_count": len(interactive_elements),
                "chrome_candidates_count": len(chrome_candidates),
                "chrome_candidates": chrome_candidates,
                "interactive_elements": interactive_elements[:20],  # First 20
                "all_elements": [{"index": i, "text": elem.get("content", ""), "type": elem.get("type", ""), "bbox": elem.get("bbox_normalized", []), "interactive": elem.get("interactivity", False)} for i, elem in enumerate(elements)]
            }
            
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(results_data, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Detailed results saved to: {results_file}")
            
            # Step 11: Final conclusion
            print(f"\n🎯 CONCLUSION:")
            print("=" * 60)
            if chrome_candidates:
                print(f"✅ Chrome WAS FOUND in OmniParser results!")
                print(f"   {len(chrome_candidates)} Chrome candidates detected")
                print(f"   Best candidate: Index {chrome_candidates[0]['index']} - '{chrome_candidates[0]['text']}'")
                
                # Try clicking the best candidate
                best_candidate = chrome_candidates[0]
                if best_candidate['bbox'] and len(best_candidate['bbox']) >= 4:
                    bbox = best_candidate['bbox']
                    # Convert normalized coordinates to pixel coordinates
                    screen_width, screen_height = pyautogui.size()
                    x1 = int(bbox[0] * screen_width)
                    y1 = int(bbox[1] * screen_height)
                    x2 = int(bbox[2] * screen_width)
                    y2 = int(bbox[3] * screen_height)
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2
                    
                    print(f"\n🖱️  ATTEMPTING TO CLICK BEST CHROME CANDIDATE:")
                    print(f"   Coordinates: ({center_x}, {center_y})")
                    
                    # Click the Chrome icon
                    pyautogui.click(center_x, center_y)
                    time.sleep(3)
                    
                    # Check if Chrome launched
                    result = subprocess.run(['powershell', '-Command', 'Get-Process chrome -ErrorAction SilentlyContinue'],
                                          capture_output=True, text=True)
                    if result.stdout.strip():
                        chrome_count = len([line for line in result.stdout.strip().split('\n') if line.strip()])
                        print(f"   ✅ SUCCESS! Chrome launched with {chrome_count} processes")
                        return True
                    else:
                        print(f"   ❌ Click failed - Chrome did not launch")
            else:
                print(f"❌ Chrome was NOT FOUND in OmniParser results")
                print(f"   This means Chrome icon is not visible on current desktop")
                print(f"   Or Chrome is not installed/accessible")
            
            return len(chrome_candidates) > 0
            
        except Exception as e:
            print(f"   ❌ Error during OmniParser analysis: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"❌ Error in manual Chrome search: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = manual_omniparser_chrome_search()
    if success:
        print("\n🎉 Manual Chrome search completed successfully!")
    else:
        print("\n💥 Manual Chrome search failed or Chrome not found")
