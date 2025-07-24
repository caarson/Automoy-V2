#!/usr/bin/env python3

import sys
import os
import subprocess
import time
import requests
import pyautogui
from datetime import datetime
import json

def check_server():
    """Check if OmniParser server is running"""
    try:
        response = requests.get("http://localhost:8111", timeout=2)
        return True
    except:
        return False

def start_omniparser_server():
    """Start OmniParser server"""
    print("Starting OmniParser server...")
    try:
        # Start OmniParser in the background
        process = subprocess.Popen([
            sys.executable, "-m", "http.server", "8111"
        ], cwd="core", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        return process
    except Exception as e:
        print(f"Failed to start server: {e}")
        return None

def test_omniparser():
    """Test OmniParser with current desktop"""
    print("\n=== OMNIPARSER DESKTOP ANALYSIS ===")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Take screenshot
    screenshot_path = f"omniparser_analysis_{timestamp}.png"
    screenshot = pyautogui.screenshot()
    screenshot.save(screenshot_path)
    print(f"Screenshot saved: {screenshot_path}")
    
    # Check if server is running
    if not check_server():
        print("OmniParser server not running, attempting to start...")
        server_process = start_omniparser_server()
        if server_process:
            print("Server started, waiting for initialization...")
            time.sleep(5)
        else:
            print("Failed to start server, using fallback analysis...")
            return fallback_analysis(screenshot_path)
    
    # Test with OmniParser
    try:
        with open(screenshot_path, 'rb') as f:
            files = {'image': f}
            response = requests.post("http://localhost:8111/parse", files=files, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"OmniParser returned {len(result.get('parsed_content_list', []))} elements")
            
            # Save full results
            results_file = f"omniparser_results_{timestamp}.json"
            with open(results_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Full results saved to: {results_file}")
            
            # Look for browser-related terms
            browser_elements = []
            for element in result.get('parsed_content_list', []):
                text = element.get('text', '').lower()
                if any(term in text for term in ['chrome', 'google', 'browser', 'internet', 'edge', 'firefox', 'explorer']):
                    browser_elements.append(element)
            
            print(f"\nFound {len(browser_elements)} browser-related elements:")
            for i, element in enumerate(browser_elements):
                print(f"  {i+1}. Text: '{element.get('text', 'N/A')}'")
                print(f"      Coords: {element.get('coordinate', 'N/A')}")
            
            return result
            
        else:
            print(f"OmniParser error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"OmniParser request failed: {e}")
        return fallback_analysis(screenshot_path)

def fallback_analysis(screenshot_path):
    """Fallback analysis when OmniParser is unavailable"""
    print("\n=== FALLBACK COORDINATE ANALYSIS ===")
    
    # Common Chrome icon locations
    screen_width, screen_height = pyautogui.size()
    chrome_locations = [
        # Taskbar locations
        (50, screen_height - 40),   # Far left taskbar
        (100, screen_height - 40),  # Left taskbar
        (150, screen_height - 40),  # Left-center taskbar
        (200, screen_height - 40),  # Center-left taskbar
        
        # Desktop locations
        (50, 50),   # Top-left desktop
        (50, 100),  # Second row desktop
        (50, 150),  # Third row desktop
        
        # Start menu area
        (30, screen_height - 60),   # Start button area
    ]
    
    print(f"Screen dimensions: {screen_width}x{screen_height}")
    print("Testing common Chrome locations:")
    
    results = []
    for i, (x, y) in enumerate(chrome_locations):
        print(f"  Location {i+1}: ({x}, {y})")
        
        # Test click at this location
        try:
            pyautogui.click(x, y)
            time.sleep(0.5)  # Brief pause
            results.append({"location": (x, y), "clicked": True})
        except Exception as e:
            print(f"    Click failed: {e}")
            results.append({"location": (x, y), "clicked": False, "error": str(e)})
    
    # Check if Chrome opened
    time.sleep(2)
    try:
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                              capture_output=True, text=True, shell=True)
        chrome_processes = len([line for line in result.stdout.split('\n') 
                              if 'chrome.exe' in line.lower()])
        print(f"\nChrome processes after clicking: {chrome_processes}")
    except:
        print("Could not check Chrome processes")
    
    return {"fallback_results": results, "screenshot": screenshot_path}

if __name__ == "__main__":
    print("=== SIMPLE OMNIPARSER CHECK ===")
    print(f"Started: {datetime.now()}")
    
    result = test_omniparser()
    
    print(f"\nCompleted: {datetime.now()}")
    print("=== END ANALYSIS ===")
