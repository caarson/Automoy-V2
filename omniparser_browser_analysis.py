#!/usr/bin/env python3
"""
Comprehensive OmniParser analysis with detailed output
"""

import os
import sys
import pyautogui
import time
import json
from datetime import datetime

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def detailed_omniparser_analysis():
    """Analyze desktop with OmniParser and show all results"""
    
    print("=== DETAILED OMNIPARSER ANALYSIS ===")
    print(f"Started: {datetime.now()}")
    
    try:
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.operating_system.desktop_utils import DesktopUtils
        
        # Show desktop first
        print("\n1. Showing desktop...")
        desktop_utils = DesktopUtils()
        desktop_utils.show_desktop()
        time.sleep(3)  # Wait longer for desktop to settle
        
        # Take screenshot
        print("2. Taking desktop screenshot...")
        screenshot_path = f"detailed_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(screenshot_path)
        print(f"   Screenshot saved: {screenshot_path}")
        
        screen_width, screen_height = pyautogui.size()
        print(f"   Screen dimensions: {screen_width}x{screen_height}")
        
        # Initialize OmniParser
        print("\n3. Initializing OmniParser...")
        omniparser_manager = OmniParserServerManager()
        
        if not omniparser_manager.is_server_ready():
            print("   Starting OmniParser server...")
            server_process = omniparser_manager.start_server()
            if not omniparser_manager.wait_for_server(timeout=60):
                print("   ❌ OmniParser server failed to start")
                return False
        
        omniparser = omniparser_manager.get_interface()
        print("   ✅ OmniParser ready")
        
        # Process screenshot
        print("\n4. Processing screenshot with OmniParser...")
        results = omniparser.process_screenshot(screenshot_path)
        
        if not results:
            print("   ❌ OmniParser returned NO results")
            return False
        
        print(f"   ✅ OmniParser found {len(results)} elements")
        
        # Save raw results to file
        results_file = f"omniparser_detailed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"   Raw results saved to: {results_file}")
        
        # Analyze all results
        print("\n5. ANALYZING ALL DETECTED ELEMENTS:")
        print("="*60)
        
        browser_keywords = [
            'chrome', 'google', 'browser', 'internet', 'explorer', 'edge', 
            'firefox', 'safari', 'opera', 'web', 'search', 'www', 'http'
        ]
        
        app_keywords = [
            'app', 'application', 'program', 'exe', 'icon', 'shortcut',
            'desktop', 'folder', 'file', 'start', 'menu', 'taskbar'
        ]
        
        all_text_items = []
        browser_matches = []
        app_matches = []
        
        for i, item in enumerate(results):
            if isinstance(item, dict):
                text = item.get('text', '') if item.get('text') else ''
                
                if text.strip():  # Non-empty text
                    all_text_items.append((i, text))
                    
                    # Check for browser keywords
                    text_lower = text.lower()
                    for keyword in browser_keywords:
                        if keyword in text_lower:
                            browser_matches.append((i, text, keyword))
                            break
                    
                    # Check for app keywords
                    for keyword in app_keywords:
                        if keyword in text_lower:
                            app_matches.append((i, text, keyword))
                            break
        
        print(f"Total text elements found: {len(all_text_items)}")
        print(f"Browser-related matches: {len(browser_matches)}")
        print(f"App-related matches: {len(app_matches)}")
        
        # Show browser matches first
        if browser_matches:
            print("\n🌐 BROWSER-RELATED ELEMENTS:")
            print("-" * 40)
            for i, text, keyword in browser_matches:
                print(f"Element #{i}: '{text}' (matched: '{keyword}')")
                
                # Try to get coordinates
                element = results[i]
                if 'bbox_normalized' in element:
                    bbox = element['bbox_normalized']
                    if isinstance(bbox, list) and len(bbox) >= 4:
                        x1, y1, x2, y2 = bbox[:4]
                        center_x = int((x1 + x2) / 2 * screen_width)
                        center_y = int((y1 + y2) / 2 * screen_height)
                        print(f"   📍 Coordinates: ({center_x}, {center_y})")
                        print(f"   📦 BBox: {bbox}")
                elif 'bbox' in element:
                    bbox = element['bbox']
                    if isinstance(bbox, list) and len(bbox) >= 4:
                        x1, y1, x2, y2 = bbox[:4]
                        center_x = int((x1 + x2) / 2)
                        center_y = int((y1 + y2) / 2)
                        print(f"   📍 Coordinates: ({center_x}, {center_y})")
                        print(f"   📦 BBox: {bbox}")
                else:
                    print("   ❌ No coordinate data found")
                
                print(f"   🔧 Full element: {element}")
                print()
        
        # Show app matches
        if app_matches:
            print("\n📱 APPLICATION-RELATED ELEMENTS:")
            print("-" * 40)
            for i, text, keyword in app_matches[:10]:  # Show first 10
                print(f"Element #{i}: '{text}' (matched: '{keyword}')")
        
        # Show all text for debugging
        print(f"\n📋 ALL DETECTED TEXT ELEMENTS ({len(all_text_items)}):")
        print("-" * 50)
        for i, text in all_text_items[:30]:  # Show first 30
            print(f"#{i}: '{text}'")
        
        if len(all_text_items) > 30:
            print(f"... and {len(all_text_items) - 30} more elements")
        
        # Test clicking browser matches
        if browser_matches:
            print(f"\n6. TESTING CLICKS ON BROWSER ELEMENTS ({len(browser_matches)} found):")
            print("="*60)
            
            for idx, (i, text, keyword) in enumerate(browser_matches):
                print(f"\nTesting browser element #{idx+1}: '{text}'")
                
                element = results[i]
                coords = None
                
                if 'bbox_normalized' in element:
                    bbox = element['bbox_normalized']
                    if isinstance(bbox, list) and len(bbox) >= 4:
                        x1, y1, x2, y2 = bbox[:4]
                        center_x = int((x1 + x2) / 2 * screen_width)
                        center_y = int((y1 + y2) / 2 * screen_height)
                        coords = (center_x, center_y)
                elif 'bbox' in element:
                    bbox = element['bbox']
                    if isinstance(bbox, list) and len(bbox) >= 4:
                        x1, y1, x2, y2 = bbox[:4]
                        center_x = int((x1 + x2) / 2)
                        center_y = int((y1 + y2) / 2)
                        coords = (center_x, center_y)
                
                if coords:
                    x, y = coords
                    print(f"   🖱️ CLICKING at ({x}, {y})...")
                    
                    try:
                        pyautogui.click(x, y)
                        print(f"   ✅ Click executed")
                        
                        # Wait and check for Chrome
                        print("   ⏳ Waiting 4 seconds...")
                        time.sleep(4)
                        
                        import subprocess
                        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                                              capture_output=True, text=True)
                        if 'chrome.exe' in result.stdout:
                            print(f"   🎉 SUCCESS! Chrome launched from '{text}'!")
                            return True
                        else:
                            print(f"   ❌ No Chrome after clicking '{text}'")
                            
                    except Exception as e:
                        print(f"   ❌ Click error: {e}")
                else:
                    print(f"   ❌ No valid coordinates for '{text}'")
        
        print("\n7. FINAL SUMMARY:")
        print("="*40)
        print(f"✅ OmniParser detected {len(results)} elements")
        print(f"✅ Found {len(all_text_items)} text elements")
        print(f"✅ Found {len(browser_matches)} browser-related elements")
        print(f"✅ Found {len(app_matches)} app-related elements")
        
        if not browser_matches:
            print("⚠️  NO browser elements detected - Chrome may not be visible on desktop")
            print("💡 Possible solutions:")
            print("   - Check if Chrome is installed")
            print("   - Look for Chrome in Start menu or taskbar")
            print("   - Try different desktop locations")
            print("   - Check if Chrome shortcut exists on desktop")
        
        return len(browser_matches) > 0
        
    except Exception as e:
        print(f"❌ Error in analysis: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting comprehensive OmniParser analysis...")
    success = detailed_omniparser_analysis()
    print(f"\n🎯 ANALYSIS RESULT: {'Found browser elements' if success else 'No browser elements found'}")
    print(f"Completed: {datetime.now()}")
