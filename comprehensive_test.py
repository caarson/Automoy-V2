#!/usr/bin/env python3

import sys
import os
import subprocess
import time
import requests
import pyautogui
from datetime import datetime
import json

def count_chrome_processes():
    """Count current Chrome processes"""
    try:
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], 
                              capture_output=True, text=True, shell=True)
        lines = [line for line in result.stdout.split('\n') if 'chrome.exe' in line.lower()]
        return len(lines)
    except:
        return 0

def test_chrome_launch():
    """Test direct Chrome launching"""
    print("=== CHROME LAUNCH TEST ===")
    print(f"Started: {datetime.now()}")
    
    # Count initial Chrome processes
    initial_chrome = count_chrome_processes()
    print(f"Initial Chrome processes: {initial_chrome}")
    
    # Take screenshot before
    screenshot_before = f"chrome_test_before_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    pyautogui.screenshot().save(screenshot_before)
    print(f"Screenshot before: {screenshot_before}")
    
    # Get screen dimensions
    screen_width, screen_height = pyautogui.size()
    print(f"Screen dimensions: {screen_width}x{screen_height}")
    
    # Test locations systematically
    test_locations = [
        ("Taskbar left", 60, screen_height - 40),
        ("Taskbar center-left", 120, screen_height - 40),
        ("Desktop top-left", 60, 60),
        ("Desktop second icon", 60, 120),
        ("Start menu area", 40, screen_height - 50),
    ]
    
    print("\nTesting Chrome launch locations:")
    
    for name, x, y in test_locations:
        print(f"\n--- Testing {name}: ({x}, {y}) ---")
        
        # Click the location
        try:
            pyautogui.click(x, y)
            print(f"  Clicked successfully")
            time.sleep(2)  # Wait for potential launch
            
            # Count Chrome processes after click
            after_chrome = count_chrome_processes()
            print(f"  Chrome processes after: {after_chrome}")
            
            if after_chrome > initial_chrome:
                print(f"  ✅ SUCCESS: New Chrome process detected!")
                # Take screenshot after success
                screenshot_success = f"chrome_success_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                pyautogui.screenshot().save(screenshot_success)
                print(f"  Success screenshot: {screenshot_success}")
                return True
                
        except Exception as e:
            print(f"  ❌ Click failed: {e}")
            
        time.sleep(1)  # Brief pause between attempts
    
    # Try Windows key + typing approach as fallback
    print("\n--- Testing Windows Key Approach ---")
    try:
        pyautogui.press('win')
        time.sleep(1)
        pyautogui.typewrite('chrome')
        time.sleep(1)
        pyautogui.press('enter')
        time.sleep(3)
        
        final_chrome = count_chrome_processes()
        print(f"Chrome processes after Windows key: {final_chrome}")
        
        if final_chrome > initial_chrome:
            print("✅ Windows key approach worked!")
            return True
        else:
            print("❌ Windows key approach failed too")
            
    except Exception as e:
        print(f"Windows key approach error: {e}")
    
    # Take screenshot after all attempts
    screenshot_after = f"chrome_test_after_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    pyautogui.screenshot().save(screenshot_after)
    print(f"Screenshot after: {screenshot_after}")
    
    print(f"\nFinal Chrome processes: {count_chrome_processes()}")
    return False

def start_omniparser_properly():
    """Start the actual OmniParser server"""
    print("\n=== STARTING OMNIPARSER SERVER ===")
    
    # Check if we have the OmniParser directory
    omniparser_paths = [
        "core/omniparser",
        "omniparser", 
        "core/OmniParser",
        "OmniParser"
    ]
    
    omniparser_dir = None
    for path in omniparser_paths:
        if os.path.exists(path):
            omniparser_dir = path
            break
    
    if not omniparser_dir:
        print("❌ OmniParser directory not found")
        return False
    
    print(f"Found OmniParser at: {omniparser_dir}")
    
    # Try to start the server
    try:
        server_script = os.path.join(omniparser_dir, "server.py")
        if os.path.exists(server_script):
            print(f"Starting server from: {server_script}")
            process = subprocess.Popen([
                sys.executable, server_script
            ], cwd=omniparser_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            time.sleep(5)  # Wait for startup
            
            # Test if server is responding
            try:
                response = requests.get("http://localhost:8111", timeout=2)
                print(f"✅ Server responding: {response.status_code}")
                return True
            except:
                print("❌ Server not responding")
                return False
        else:
            print(f"❌ server.py not found in {omniparser_dir}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return False

if __name__ == "__main__":
    print("=== COMPREHENSIVE CHROME TEST ===")
    
    # First test Chrome launching
    launch_success = test_chrome_launch()
    
    if launch_success:
        print("\n✅ Chrome launching works!")
    else:
        print("\n❌ Chrome launching failed")
    
    # Then try to start OmniParser
    server_success = start_omniparser_properly()
    
    if server_success:
        print("\n✅ OmniParser server started successfully!")
    else:
        print("\n❌ OmniParser server failed to start")
    
    print(f"\nCompleted: {datetime.now()}")
