#!/usr/bin/env python3
"""
Final verification: Is Chrome available and can we click it?
"""

import os
import sys
import time
import subprocess
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def verify_chrome_availability():
    """Verify if Chrome is available and can be launched"""
    
    print("🔍 Chrome Availability Verification")
    print("=" * 50)
    
    # Test 1: Check if Chrome executable exists
    print("1. Checking Chrome installation...")
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
    ]
    
    chrome_found = False
    for path in chrome_paths:
        if os.path.exists(path):
            print(f"   ✅ Chrome found at: {path}")
            chrome_found = True
            break
    
    if not chrome_found:
        print("   ❌ Chrome executable not found")
        print("   This explains why clicking tests fail - Chrome may not be installed")
        return False
    
    # Test 2: Can we launch Chrome directly?
    print("2. Testing direct Chrome launch...")
    try:
        result = subprocess.run([path], timeout=5, capture_output=True)
        print("   ✅ Chrome can be launched directly")
    except subprocess.TimeoutExpired:
        print("   ✅ Chrome started (timeout expected)")
    except Exception as e:
        print(f"   ⚠️  Chrome launch issue: {e}")
    
    # Test 3: Check for Chrome shortcuts on desktop
    print("3. Checking for Chrome shortcuts...")
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    
    if os.path.exists(desktop_path):
        desktop_files = os.listdir(desktop_path)
        chrome_shortcuts = [f for f in desktop_files if "chrome" in f.lower()]
        
        if chrome_shortcuts:
            print(f"   ✅ Found Chrome shortcuts on desktop: {chrome_shortcuts}")
        else:
            print("   ❌ No Chrome shortcuts found on desktop")
            print("   This explains why desktop clicking fails")
    else:
        print("   ❌ Desktop folder not accessible")
    
    # Test 4: Check Windows Start Menu for Chrome
    print("4. Testing Start Menu Chrome access...")
    try:
        import pyautogui
        
        # Open start menu and search for Chrome
        pyautogui.press('win')
        time.sleep(1)
        pyautogui.typewrite('chrome')
        time.sleep(1)
        pyautogui.press('enter')
        time.sleep(3)
        
        # Check if Chrome launched
        result = subprocess.run(
            ['powershell', '-Command', 'Get-Process chrome -ErrorAction SilentlyContinue'],
            capture_output=True, text=True
        )
        
        if result.stdout.strip():
            print("   ✅ Chrome can be launched via Start Menu")
            chrome_count = len([line for line in result.stdout.strip().split('\n') if 'chrome' in line.lower()])
            print(f"   📊 Chrome processes launched: {chrome_count}")
            
            # Close Chrome for next test
            subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                          capture_output=True, text=True)
            time.sleep(1)
            return True
        else:
            print("   ❌ Chrome didn't launch via Start Menu")
            
    except Exception as e:
        print(f"   ❌ Start Menu test failed: {e}")
    
    # Test 5: Check taskbar for Chrome
    print("5. Checking taskbar for Chrome...")
    try:
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.utils.screenshot_utils import capture_screen_pil
        import tempfile
        
        omniparser_manager = OmniParserServerManager()
        omniparser = omniparser_manager.get_interface()
        
        # Take screenshot of current screen
        screenshot = capture_screen_pil()
        screenshot.save("availability_check.png")
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
            screenshot.save(temp_path)
        
        try:
            parsed_result = omniparser.parse_screenshot(temp_path)
            if parsed_result:
                elements = parsed_result.get("parsed_content_list", [])
                
                # Look for any Chrome-related elements
                chrome_elements = []
                for element in elements:
                    content = element.get("content", "").lower()
                    if any(keyword in content for keyword in ["chrome", "google"]):
                        chrome_elements.append(element)
                
                if chrome_elements:
                    print(f"   ✅ Found {len(chrome_elements)} Chrome-related UI elements")
                    for i, elem in enumerate(chrome_elements[:3]):
                        content = elem.get("content", "")[:40]
                        elem_type = elem.get("type", "")
                        interactive = elem.get("interactivity", False)
                        print(f"     {i+1}. '{content}' (type: {elem_type}, clickable: {interactive})")
                else:
                    print("   ❌ No Chrome-related UI elements found")
                    print("   This explains why OmniParser can't find Chrome to click")
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        print(f"   ❌ OmniParser test failed: {e}")
    
    return False

def main():
    print("🎯 FINAL CHROME VERIFICATION")
    print("Checking why Chrome clicking might not be working\n")
    
    success = verify_chrome_availability()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ CHROME IS AVAILABLE!")
        print("✅ Chrome can be launched programmatically")
        print("✅ The clicking system should work")
    else:
        print("❌ CHROME AVAILABILITY ISSUES FOUND!")
        print("❌ This explains why clicking tests fail")
        print("💡 Solutions:")
        print("   - Install Google Chrome if not installed")
        print("   - Create a Chrome desktop shortcut")
        print("   - Check if Chrome is pinned to taskbar")
    print("=" * 50)
    
    return success

if __name__ == "__main__":
    main()
