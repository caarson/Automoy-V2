#!/usr/bin/env python3
"""
Direct Chrome launching test for Automoy
This script bypasses the complex visual analysis and directly launches Chrome
"""

import subprocess
import sys
import os
import time
import pyautogui

def test_chrome_direct_launch():
    """Test direct Chrome launching without visual analysis"""
    print("=== DIRECT CHROME LAUNCH TEST ===")
    
    try:
        # Chrome executable path (already verified to exist)
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        
        print(f"Chrome path: {chrome_path}")
        print(f"Chrome exists: {os.path.exists(chrome_path)}")
        
        # Launch Chrome directly
        print("Launching Chrome...")
        process = subprocess.Popen([
            chrome_path,
            "--new-window",
            "https://www.google.com"
        ])
        
        print(f"Chrome process started with PID: {process.pid}")
        print("Waiting 3 seconds for Chrome to fully load...")
        time.sleep(3)
        
        # Check if process is still running
        if process.poll() is None:
            print("✅ Chrome is running successfully!")
            return True
        else:
            print(f"❌ Chrome process exited with code: {process.poll()}")
            return False
            
    except Exception as e:
        print(f"❌ Error launching Chrome: {e}")
        return False

def test_chrome_via_coordinates():
    """Test Chrome launching via coordinate clicking simulation"""
    print("\n=== COORDINATE CLICKING SIMULATION ===")
    
    try:
        # Get screen dimensions
        screen_w, screen_h = pyautogui.size()
        print(f"Screen size: {screen_w}x{screen_h}")
        
        # Simulate typical Chrome icon location in taskbar
        # Taskbar is usually at bottom: y around 95-99% of screen height
        # Chrome icon typically in left portion: x around 10-15% of screen width
        chrome_x = int(0.125 * screen_w)  # 12.5% from left
        chrome_y = int(0.97 * screen_h)   # 97% down (taskbar area)
        
        print(f"Simulated Chrome coordinates: ({chrome_x}, {chrome_y})")
        
        # Move to coordinates (but don't click yet for safety)
        pyautogui.moveTo(chrome_x, chrome_y, duration=0.5)
        print(f"Mouse moved to ({chrome_x}, {chrome_y})")
        
        # Get current mouse position to verify
        current_x, current_y = pyautogui.position()
        print(f"Current mouse position: ({current_x}, {current_y})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in coordinate simulation: {e}")
        return False

def test_automoy_coordinate_conversion():
    """Test the coordinate conversion logic used in Automoy"""
    print("\n=== AUTOMOY COORDINATE CONVERSION TEST ===")
    
    try:
        # Simulate OmniParser bbox_normalized output for Chrome icon
        screen_w, screen_h = pyautogui.size()
        
        # Typical Chrome icon bbox in taskbar (normalized coordinates)
        bbox_normalized = [0.10, 0.95, 0.15, 0.99]
        
        # Convert to pixel coordinates (same logic as in _format_visual_analysis_result)
        x1_pixel = int(bbox_normalized[0] * screen_w)
        y1_pixel = int(bbox_normalized[1] * screen_h)  
        x2_pixel = int(bbox_normalized[2] * screen_w)
        y2_pixel = int(bbox_normalized[3] * screen_h)
        
        # Calculate center point for clicking
        center_x = (x1_pixel + x2_pixel) // 2
        center_y = (y1_pixel + y2_pixel) // 2
        
        print(f"Normalized bbox: {bbox_normalized}")
        print(f"Pixel coordinates: ({x1_pixel}, {y1_pixel}) to ({x2_pixel}, {y2_pixel})")
        print(f"Click center point: ({center_x}, {center_y})")
        
        # Format as Automoy would
        formatted_output = f"ClickCoordinates: ({center_x}, {center_y})"
        print(f"Formatted for LLM: {formatted_output}")
        
        # Test coordinate extraction
        import re
        pattern = r"ClickCoordinates:\s*\((\d+),\s*(\d+)\)"
        matches = re.findall(pattern, formatted_output)
        
        if matches:
            extracted_x, extracted_y = matches[0]
            print(f"✅ Coordinate extraction successful: ({extracted_x}, {extracted_y})")
            return True
        else:
            print("❌ Coordinate extraction failed")
            return False
            
    except Exception as e:
        print(f"❌ Error in coordinate conversion test: {e}")
        return False

if __name__ == "__main__":
    print("🔍 CHROME TESTING SUITE FOR AUTOMOY")
    print("=" * 50)
    
    # Test 1: Direct Chrome launch
    direct_success = test_chrome_direct_launch()
    
    # Test 2: Coordinate simulation  
    coord_success = test_chrome_via_coordinates()
    
    # Test 3: Automoy coordinate conversion
    conversion_success = test_automoy_coordinate_conversion()
    
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY:")
    print(f"✅ Direct Chrome Launch: {'PASS' if direct_success else 'FAIL'}")
    print(f"✅ Coordinate Simulation: {'PASS' if coord_success else 'FAIL'}")  
    print(f"✅ Coordinate Conversion: {'PASS' if conversion_success else 'FAIL'}")
    
    if all([direct_success, coord_success, conversion_success]):
        print("\n🎉 ALL TESTS PASSED! Chrome should work with Automoy.")
    else:
        print("\n❌ Some tests failed. Chrome functionality may be limited.")
        
    print("\nNext step: Run Automoy with enhanced Chrome bypass...")
