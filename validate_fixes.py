#!/usr/bin/env python3
"""
Complete System Test - Test all fixes together
This script will:
1. Test OmniParser server connection
2. Test visual analysis with desktop
3. Test keyboard functionality
4. Test Chrome detection
"""

import os
import sys
import time
from datetime import datetime

# Add workspace to path
workspace = os.path.abspath(os.path.dirname(__file__))
if workspace not in sys.path:
    sys.path.insert(0, workspace)

# Results file
results_file = os.path.join(workspace, "debug", "logs", "system_test_complete.log")
os.makedirs(os.path.dirname(results_file), exist_ok=True)

def log_result(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    with open(results_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
        f.flush()
    print(f"[{timestamp}] {message}")

def test_omniparser_server():
    """Test OmniParser server connection and functionality"""
    log_result("=== TESTING OMNIPARSER SERVER ===")
    
    try:
        import requests
        
        # Test server connection
        response = requests.get("http://127.0.0.1:8111/probe/", timeout=5)
        if response.status_code == 200:
            log_result("✅ OmniParser server is responding")
            return True
        else:
            log_result(f"❌ OmniParser server responded with status: {response.status_code}")
            return False
    except Exception as e:
        log_result(f"❌ OmniParser server connection failed: {e}")
        return False

def test_visual_analysis():
    """Test visual analysis functionality"""
    log_result("=== TESTING VISUAL ANALYSIS ===")
    
    try:
        import requests
        import base64
        import pyautogui
        from io import BytesIO
        
        # Take screenshot
        screenshot = pyautogui.screenshot()
        log_result(f"✅ Screenshot captured: {screenshot.size[0]}x{screenshot.size[1]}")
        
        # Convert to base64
        buffer = BytesIO()
        screenshot.save(buffer, format="PNG")
        image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        log_result(f"✅ Image converted to base64: {len(image_data)} chars")
        
        # Send to OmniParser
        response = requests.post(
            "http://127.0.0.1:8111/parse/",
            json={"base64_image": image_data},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            elements = result.get("parsed_content_list", [])
            log_result(f"✅ Visual analysis successful: {len(elements)} elements detected")
            
            # Check for Chrome
            chrome_count = 0
            for element in elements:
                content = str(element.get("content", "")).lower()
                if "chrome" in content:
                    chrome_count += 1
            
            log_result(f"🎯 Chrome references found: {chrome_count}")
            return len(elements) > 0
        else:
            log_result(f"❌ Visual analysis failed: {response.status_code}")
            return False
            
    except Exception as e:
        log_result(f"❌ Visual analysis test failed: {e}")
        return False

def test_keyboard_functionality():
    """Test keyboard input functionality"""
    log_result("=== TESTING KEYBOARD FUNCTIONALITY ===")
    
    try:
        # Test PyAutoGUI
        import pyautogui
        pyautogui.press('f1')  # Safe key to test
        log_result("✅ PyAutoGUI key press successful")
        
        # Test keyboard library
        try:
            import keyboard
            # Note: Don't actually press keys in test, just verify import
            log_result("✅ Keyboard library available")
        except ImportError:
            log_result("⚠️ Keyboard library not available")
        
        # Test Windows API
        try:
            import ctypes
            user32 = ctypes.windll.user32
            log_result("✅ Windows API available for key input")
            return True
        except Exception as api_error:
            log_result(f"⚠️ Windows API test failed: {api_error}")
            return False
        
    except Exception as e:
        log_result(f"❌ Keyboard functionality test failed: {e}")
        return False

def test_main_integration():
    """Test the main system integration"""
    log_result("=== TESTING MAIN SYSTEM INTEGRATION ===")
    
    try:
        # Import main components
        from core.utils.omniparser.omniparser_server_manager import OmniParserServerManager
        from core.operate import ActionExecutor
        
        # Test OmniParser manager
        manager = OmniParserServerManager()
        server_ready = manager.is_server_ready()
        log_result(f"OmniParser manager server ready: {server_ready}")
        
        if server_ready:
            interface = manager.get_interface()
            log_result("✅ OmniParser interface obtained")
        
        # Test ActionExecutor
        executor = ActionExecutor()
        log_result("✅ ActionExecutor initialized")
        
        return server_ready
        
    except Exception as e:
        log_result(f"❌ Main system integration test failed: {e}")
        return False

def main():
    """Run complete system test"""
    log_result("=== COMPLETE SYSTEM TEST STARTED ===")
    
    # Clear log file
    with open(results_file, "w") as f:
        f.write("")
    
    results = {
        "omniparser_server": False,
        "visual_analysis": False, 
        "keyboard_functionality": False,
        "main_integration": False
    }
    
    # Run tests
    log_result("Starting comprehensive system test...")
    
    results["omniparser_server"] = test_omniparser_server()
    time.sleep(1)
    
    if results["omniparser_server"]:
        results["visual_analysis"] = test_visual_analysis()
        time.sleep(1)
    
    results["keyboard_functionality"] = test_keyboard_functionality()
    time.sleep(1)
    
    results["main_integration"] = test_main_integration()
    
    # Summary
    log_result("=== TEST RESULTS SUMMARY ===")
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        log_result(f"{test_name}: {status}")
        if result:
            passed += 1
    
    log_result(f"Overall: {passed}/{total} tests passed")
    
    if passed == total:
        log_result("🎉 ALL TESTS PASSED - System ready for Chrome goals!")
        log_result("You can now submit 'launch Chrome' goals to the GUI")
    else:
        log_result(f"⚠️ {total-passed} test(s) failed - system may have issues")
    
    log_result("=== COMPLETE SYSTEM TEST FINISHED ===")
    log_result(f"Full results saved to: {results_file}")

if __name__ == "__main__":
    main()
